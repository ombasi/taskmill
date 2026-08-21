"""
Post-withdrawal balance interest.

Rules:
- Only scheduled AFTER a successful withdrawal, on the balance left in the account.
- Credited the NEXT calendar day (not same day).
- Does not run on task completion or random dashboard visits before a withdraw.
"""
from datetime import datetime, timedelta, date

DEFAULT_MIN_UGX = 30000.0
DEFAULT_RATE = 0.05


def _settings():
    try:
        from models.settings import Settings
        return Settings.query.first()
    except Exception:
        return None


def _cfg():
    s = _settings()
    enabled = True
    min_ugx = DEFAULT_MIN_UGX
    rate = DEFAULT_RATE
    if s:
        if getattr(s, "interest_enabled", None) is False:
            enabled = False
        try:
            if getattr(s, "interest_min_ugx", None) is not None:
                min_ugx = float(s.interest_min_ugx)
        except Exception:
            pass
        try:
            if getattr(s, "interest_rate", None) is not None:
                r = float(s.interest_rate)
                rate = r / 100.0 if r > 1 else r
        except Exception:
            pass
    return enabled, min_ugx, rate


def _today():
    return datetime.utcnow().date()


def schedule_after_withdraw(user):
    """
    Call after a withdrawal is successfully created.
    Locks in remaining balance; interest pays next calendar day.
    """
    enabled, min_ugx, rate = _cfg()
    if not enabled:
        return False, "Interest paused"

    bal = float(getattr(user, "available_balance", 0) or 0)
    if bal < min_ugx:
        # clear any pending so they don't get old schedule
        try:
            user.interest_pending_base = 0
            user.interest_due_date = None
        except Exception:
            pass
        return False, "Remaining balance below threshold"

    due = _today() + timedelta(days=1)  # next calendar day
    user.interest_pending_base = bal
    user.interest_due_date = due
    try:
        from extensions import db
        db.session.commit()
    except Exception:
        pass

    try:
        from services.notification_service import NotificationService
        from helpers.currency import money
        interest = round(bal * rate, 0)
        NotificationService.send(
            user,
            "Balance interest scheduled",
            f"After your withdrawal, {money(user, interest)} (10% of remaining balance) will be credited tomorrow.",
        )
    except Exception:
        pass
    return True, f"Interest scheduled for {due.isoformat()}"


def can_claim(user):
    enabled, min_ugx, rate = _cfg()
    if not enabled:
        return False, "Interest paused by admin"
    if getattr(user, "is_admin", False) or getattr(user, "is_blocked", False):
        return False, "Not eligible"
    if getattr(user, "wallet_frozen", False):
        return False, "Wallet frozen"

    base = float(getattr(user, "interest_pending_base", 0) or 0)
    due = getattr(user, "interest_due_date", None)
    if base <= 0 or not due:
        return False, "Interest starts after you withdraw and leave a qualifying balance"

    # due may be date or datetime
    if isinstance(due, datetime):
        due_d = due.date()
    else:
        due_d = due

    if _today() < due_d:
        return False, f"Interest pays on {due_d.isoformat()} (next day after withdraw)"

    # already paid for this cycle?
    last = getattr(user, "last_balance_interest_at", None)
    if last:
        last_d = last.date() if isinstance(last, datetime) else last
        if last_d >= due_d:
            return False, "Interest for this cycle already paid"

    if base < min_ugx:
        return False, "Scheduled base below threshold"

    return True, "ok"


def preview(user):
    enabled, min_ugx, rate = _cfg()
    base = float(getattr(user, "interest_pending_base", 0) or 0)
    due = getattr(user, "interest_due_date", None)
    ok, reason = can_claim(user)
    interest = round(base * rate, 0) if base > 0 and enabled else 0
    return {
        "eligible_balance_ugx": base,
        "min_ugx": min_ugx,
        "rate": rate,
        "interest_ugx": interest,
        "can_claim": ok,
        "reason": reason,
        "due_date": due,
        "enabled": enabled,
        "mode": "post_withdraw_next_day",
    }


def apply_interest(user, commit=True):
    """Credit scheduled post-withdraw interest (only on/after due date)."""
    ok, reason = can_claim(user)
    if not ok:
        return False, reason, 0.0

    enabled, min_ugx, rate = _cfg()
    base = float(getattr(user, "interest_pending_base", 0) or 0)
    amount = round(base * rate, 0)
    if amount <= 0:
        return False, "Interest amount is zero", 0.0

    from services.wallet_service import WalletService
    from extensions import db

    before = float(user.available_balance or 0)
    WalletService.credit(
        user,
        amount,
        description=f"Post-withdraw balance interest {rate*100:.0f}% on {base:,.0f} held",
        transaction_type="balance_interest",
    )
    user.last_balance_interest_at = datetime.utcnow()
    # clear schedule until next withdraw
    user.interest_pending_base = 0
    user.interest_due_date = None
    try:
        user.total_earned = float(user.total_earned or 0) + amount
    except Exception:
        pass

    try:
        from models.interest_log import InterestLog
        InterestLog.__table__.create(db.engine, checkfirst=True)
        db.session.add(InterestLog(
            user_id=user.id,
            amount=amount,
            balance_before=before,
            rate=rate,
        ))
    except Exception as e:
        print("interest log:", e)

    if commit:
        db.session.commit()

    try:
        from services.notification_service import NotificationService
        from helpers.currency import money
        NotificationService.send(
            user,
            "Balance interest paid",
            f"{money(user, amount)} credited from your post-withdraw balance.",
        )
    except Exception:
        pass
    try:
        from services.engagement_service import send_outbound_alert
        from helpers.currency import money
        send_outbound_alert(user, "Balance interest", f"{money(user, amount)} interest credited.")
    except Exception:
        pass

    return True, "Interest credited", amount


def process_due_interest(user):
    """Auto-pay if due (for cron / dashboard)."""
    ok, _ = can_claim(user)
    if not ok:
        return False, 0.0
    return apply_interest(user)
