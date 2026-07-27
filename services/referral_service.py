import random
import string

from extensions import db

from models.user import User
from models.settings import Settings

from services.wallet_service import WalletService
from services.notification_service import NotificationService


class ReferralService:

    # =====================================
    # Generate Referral Code
    # =====================================

    @staticmethod
    def generate_code():

        while True:

            code = ''.join(
                random.choices(
                    string.ascii_uppercase + string.digits,
                    k=8
                )
            )

            exists = User.query.filter_by(
                referral_code=code
            ).first()

            if not exists:
                return code

    # =====================================
    # Validate Referral
    # =====================================

    @staticmethod
    def validate(referral_code):

        if not referral_code:
            return None

        return User.query.filter_by(
            referral_code=referral_code
        ).first()

    # =====================================
    # Register Referral
    # =====================================

    @staticmethod
    def register(new_user, referral_code):

        referrer = ReferralService.validate(
            referral_code
        )

        if not referrer:
            return

        new_user.referred_by_id = referrer.id

        referrer.referral_count += 1

        db.session.commit()

    # =====================================
    # Activate Referral
    # =====================================

    @staticmethod
    def activate(user):

        if not user.referred_by_id:
            return

        settings = Settings.query.first()

        if not settings:
            return

        referrer = User.query.get(
            user.referred_by_id
        )

        if not referrer:
            return

        # Prevent double payout for same referred user
        from models.wallet_transaction import WalletTransaction
        already = WalletTransaction.query.filter_by(
            user_id=referrer.id,
            transaction_type="referral_bonus",
            description=f"Referral bonus for {user.username}"
        ).first()
        if already:
            return

        bonus = float(settings.referral_bonus or 0)
        if bonus <= 0:
            # fallback from membership
            if user.membership and user.membership.referral_bonus:
                bonus = float(user.membership.referral_bonus)
            else:
                bonus = 2000

        WalletService.credit(
            referrer,
            bonus,
            f"Referral bonus for {user.username}",
            transaction_type="referral_bonus",
        )

        referrer.referral_income = (referrer.referral_income or 0) + bonus
        db.session.commit()

        NotificationService.send(
            referrer,
            "Referral Bonus",
            f"You earned UGX {bonus:,.0f} for referring {user.username}."
        )