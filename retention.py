
"""Comeback gift + milestones."""
from datetime import datetime, timedelta

def maybe_comeback(user):
    last = getattr(user, "last_login", None)
    if not last:
        return None
    try:
        if datetime.utcnow() - last < timedelta(days=7):
            return None
    except Exception:
        return None
    # one-time per return window flag
    if getattr(user, "comeback_claimed_at", None):
        try:
            if datetime.utcnow() - user.comeback_claimed_at < timedelta(days=30):
                return None
        except Exception:
            pass
    amount = 500  # UGX base small gift
    try:
        from services.wallet_service import WalletService
        from extensions import db
        WalletService.credit(user, amount, "Welcome back gift", transaction_type="comeback")
        user.comeback_claimed_at = datetime.utcnow()
        db.session.commit()
        return amount
    except Exception as e:
        print("comeback:", e)
        return None


def check_milestones(user, event):
    """event: first_withdraw, first_referral, first_combo"""
    try:
        from services.badge_service import award
        award(user.id, event)
    except Exception:
        pass
