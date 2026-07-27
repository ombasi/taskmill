from datetime import datetime

from extensions import db
from models.user import User

from services.referral_service import ReferralService
from services.notification_service import NotificationService


class AuthService:

    # =====================================
    # Register User
    # =====================================

    @staticmethod
    def register(

        username,

        full_name,

        email,

        phone,

        password,

        membership,

        country,

        referral_code=None

    ):

        from models.membership import Membership

        # Default to Starter if none provided
        membership_id = membership
        if not membership_id:
            starter = Membership.query.filter_by(name="Starter").first()
            membership_id = starter.id if starter else None

        user = User(
            username=username,
            full_name=full_name,
            email=email,
            phone=phone,
            membership_id=membership_id,
            country=country or "Uganda",
            currency="UGX",
            currency_symbol="UGX",
        )

        user.set_password(password)
        user.referral_code = ReferralService.generate_code()

        db.session.add(user)
        db.session.commit()

        if referral_code:

            ReferralService.register(

                user,

                referral_code

            )

        NotificationService.send(

            user,

            "Welcome",

            "Welcome to Taskmill."

        )

        return user

    # =====================================
    # Login Success
    # =====================================

    @staticmethod
    def login_success(user, ip_address=None):
        from models.login_history import LoginHistory
        from flask import request

        user.last_login = datetime.utcnow()
        user.ip_address = ip_address or user.ip_address
        db.session.add(user)

        ua = ""
        try:
            ua = request.headers.get("User-Agent", "")[:250]
        except Exception:
            pass

        entry = LoginHistory(
            user_id=user.id,
            ip_address=ip_address,
            browser=ua,
            device=ua[:100] if ua else None,
            status="Online",
        )
        # login_time may be auto
        if hasattr(entry, "login_time"):
            entry.login_time = datetime.utcnow()
        db.session.add(entry)
        db.session.commit()

    # =====================================
    # Block Check
    # =====================================

    @staticmethod
    def can_login(user):

        if not user.is_active:

            return False, "Account inactive."

        if user.is_blocked:

            return False, "Account blocked."

        return True, ""

    # =====================================
    # Change Password
    # =====================================

    @staticmethod
    def change_password(

        user,

        password

    ):

        user.set_password(password)

        db.session.commit()

        NotificationService.send(

            user,

            "Password Changed",

            "Your password has been updated."

        )