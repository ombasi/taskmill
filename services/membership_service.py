from extensions import db
from models.membership import Membership


class MembershipService:

    # =====================================
    # CURRENT MEMBERSHIP
    # =====================================

    @staticmethod
    def current(user):
        return user.membership

    # =====================================
    # ALL MEMBERSHIPS
    # =====================================

    @staticmethod
    def all():
        return (
            Membership.query
            .filter_by(active=True)
            .order_by(Membership.price.asc())
            .all()
        )

    # =====================================
    # GET MEMBERSHIP
    # =====================================

    @staticmethod
    def get(membership_id):
        return Membership.query.get(membership_id)

    # =====================================
    # DAILY TASK LIMIT
    # =====================================

    @staticmethod
    def daily_limit(user):
        membership = user.membership
        return membership.daily_tasks if membership else 0

    # =====================================
    # TASKS PER SET
    # =====================================

    @staticmethod
    def tasks_per_set(user):
        membership = user.membership
        return membership.tasks_per_set if membership else 0

    # =====================================
    # DAILY SETS
    # =====================================

    @staticmethod
    def daily_sets(user):
        membership = user.membership
        return membership.daily_sets if membership else 0

    # =====================================
    # COMBO PROBABILITY
    # =====================================

    @staticmethod
    def combo_probability(user):
        membership = user.membership
        return membership.combo_probability if membership else 0

    # =====================================
    # MAX PRODUCT PRICE
    # =====================================

    @staticmethod
    def max_product_price(user):
        membership = user.membership
        return membership.max_product_price if membership else 0

    # =====================================
    # WITHDRAW LIMIT
    # =====================================

    @staticmethod
    def withdrawal_limit(user):
        membership = user.membership
        return membership.withdrawal_limit if membership else 0

    # =====================================
    # REFERRAL BONUS
    # =====================================

    @staticmethod
    def referral_bonus(user):
        membership = user.membership
        return membership.referral_bonus if membership else 0

    # =====================================
    # MINIMUM BALANCE
    # =====================================

    @staticmethod
    def minimum_balance(user):
        membership = user.membership

        if not membership:
            return 70

        return max(70, membership.minimum_deposit)

    # =====================================
    # CAN UPGRADE
    # =====================================

    @staticmethod
    def can_upgrade(user, membership):

        if not user.membership:
            return True

        return membership.price > user.membership.price

    # =====================================
    # UPGRADE
    # =====================================

    @staticmethod
    def upgrade(user, membership):
        """
        Upgrade membership by debiting available balance.
        Fires referral activation once when leaving free/starter tier.
        """
        from services.wallet_service import WalletService
        from services.referral_service import ReferralService
        from services.notification_service import NotificationService

        price = float(membership.price or 0)
        previous = user.membership
        previous_price = float(previous.price or 0) if previous else 0

        if price > 0 and price > previous_price:
            if float(user.available_balance) < price:
                return False, "Insufficient balance for this membership."
            # Charge difference for upgrades
            charge = price if previous_price == 0 else (price - previous_price)
            # For simplicity charge full plan price when upgrading
            charge = price
            if float(user.available_balance) < charge:
                return False, "Insufficient balance for this membership."
            WalletService.debit(
                user,
                charge,
                f"Membership upgrade to {membership.name}",
                transaction_type="membership",
            )

        user.membership = membership
        db.session.commit()

        # Referral activation once when moving onto a paid plan
        if price > 0 and previous_price == 0 and user.referred_by_id:
            try:
                ReferralService.activate(user)
            except Exception:
                pass
        elif price > 0 and user.referred_by_id and previous_price > 0:
            # Already activated path – skip
            pass

        try:
            NotificationService.send(
                user,
                "Membership Updated",
                f"You are now on the {membership.name} plan."
            )
        except Exception:
            pass

        return True, f"Upgraded to {membership.name}."
