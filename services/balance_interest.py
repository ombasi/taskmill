"""
Daily balance interest:
- Qualifies when available balance >= 30,000 UGX (base).
- Credits 10% of current available balance once every 24 hours.
"""
from datetime import datetime, timedelta

MIN_UGX = 30000.0
RATE = 0.10  # 10%
INTERVAL_HOURS = 24


def _balance_as_ugx(user) -> float:
    bal = float(getattr(user, "available_balance", 0) or 0)
    # Balances are stored in UGX base across the app; display converts via helpers.currency
    return bal


def _last_interest_at(user):
    return getattr(user, "last_balance_interest_at", None)


def can_claim(user):
    if getattr(user, "is_admin", False) or getattr(user, "is_blocked", False):
        return False, "Not eligible"
    if getattr(user, "wallet_frozen", False):
        return False, "Wallet frozen"
    ugx = _balance_as_ugx(user)
    if ugx < MIN_UGX:
        return False, f"Balance must be at least base {MIN_UGX:,.0f} UGX"
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
    ugx = _balance_as_ugx(user)
    ok, reason = can_claim(user)
    interest = round(ugx * RATE, 0) if ugx >= MIN_UGX else 0
    return {
        "eligible_balance_ugx": ugx,
        "min_ugx": MIN_UGX,
        "rate": RATE,
        "interest_ugx": interest,
        "can_claim": ok,
        "reason": reason,
        "last_at": _last_interest_at(user),
    }


def apply_interest(user, commit=True):
    """Credit 10% if eligible. Returns (ok, message, amount)."""
    ok, reason = can_claim(user)
    if not ok:
        return False, reason, 0.0

    ugx = _balance_as_ugx(user)
    amount = round(ugx * RATE, 0)
    if amount <= 0:
        return False, "Interest amount is zero", 0.0

    from services.wallet_service import WalletService
    from extensions import db

    WalletService.credit(
        user,
        amount,
        description=f"Daily balance interest 10% (balance ≥ {MIN_UGX:,.0f} UGX)",
        transaction_type="balance_interest",
    )
    user.last_balance_interest_at = datetime.utcnow()
    try:
        user.total_earned = float(user.total_earned or 0) + amount
    except Exception:
        pass
    if commit:
        db.session.commit()

    try:
        from services.notification_service import NotificationService
        from helpers.currency import money
        NotificationService.send(
            user,
            "Daily balance interest",
            f"{money(user, amount)} credited (10% of your held balance).",
        )
    except Exception:
        pass
    try:
        from services.engagement_service import send_outbound_alert
        from helpers.currency import money
        send_outbound_alert(
            user,
            "Balance interest",
            f"{money(user, amount)} daily interest credited to your wallet.",
        )
    except Exception:
        pass

    return True, "Interest credited", amount
