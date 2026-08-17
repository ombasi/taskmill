
"""Daily balance interest — settings-driven threshold/rate."""
from datetime import datetime, timedelta

DEFAULT_MIN_UGX = 30000.0
DEFAULT_RATE = 0.10
INTERVAL_HOURS = 24


def _settings():
    try:
        from models.settings import Settings
        s = Settings.query.first()
        if not s:
            return None
        return s
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
                # store as percent e.g. 10 => 0.10
                r = float(s.interest_rate)
                rate = r / 100.0 if r > 1 else r
        except Exception:
            pass
    return enabled, min_ugx, rate


def _balance_as_ugx(user) -> float:
    return float(getattr(user, "available_balance", 0) or 0)


def _last_interest_at(user):
    return getattr(user, "last_balance_interest_at", None)


def can_claim(user):
    enabled, min_ugx, rate = _cfg()
    if not enabled:
        return False, "Interest paused by admin"
    if getattr(user, "is_admin", False) or getattr(user, "is_blocked", False):
        return False, "Not eligible"
    if getattr(user, "wallet_frozen", False):
        return False, "Wallet frozen"
    ugx = _balance_as_ugx(user)
    if ugx < min_ugx:
        return False, f"Balance must be at least base {min_ugx:,.0f} UGX"
    last = _last_interest_at(user)
    if last:
        try:
            if datetime.utcnow() < last + timedelta(hours=INTERVAL_HOURS):
                left = last + timedelta(hours=INTERVAL_HOURS) - datetime.utcnow()
                hrs = max(0, int(left.total_seconds() // 3600))
                mins = max(0, int((left.total_seconds() % 3600) // 60))
                return False, f"Next interest in {hrs}h {mins}m"
        except Exception:
            pass
    return True, "ok"


def preview(user):
    enabled, min_ugx, rate = _cfg()
    ugx = _balance_as_ugx(user)
    ok, reason = can_claim(user)
    interest = round(ugx * rate, 0) if ugx >= min_ugx and enabled else 0
    return {
        "eligible_balance_ugx": ugx,
        "min_ugx": min_ugx,
        "rate": rate,
        "interest_ugx": interest,
        "can_claim": ok,
        "reason": reason,
        "last_at": _last_interest_at(user),
        "enabled": enabled,
    }


def apply_interest(user, commit=True):
    ok, reason = can_claim(user)
    if not ok:
        return False, reason, 0.0
    enabled, min_ugx, rate = _cfg()
    ugx = _balance_as_ugx(user)
    amount = round(ugx * rate, 0)
    if amount <= 0:
        return False, "Interest amount is zero", 0.0

    from services.wallet_service import WalletService
    from extensions import db

    before = float(user.available_balance or 0)
    WalletService.credit(
        user,
        amount,
        description=f"Daily balance interest {rate*100:.0f}% (min {min_ugx:,.0f} UGX)",
        transaction_type="balance_interest",
    )
    user.last_balance_interest_at = datetime.utcnow()
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
            user, "Daily balance interest",
            f"{money(user, amount)} credited ({rate*100:.0f}% of held balance).",
        )
    except Exception:
        pass
    try:
        from services.engagement_service import send_outbound_alert
        from helpers.currency import money
        send_outbound_alert(user, "Balance interest", f"{money(user, amount)} daily interest credited.")
    except Exception:
        pass
    return True, "Interest credited", amount
