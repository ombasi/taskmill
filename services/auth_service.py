from datetime import datetime

from flask import request
from extensions import db
from models.user import User
from services.referral_service import ReferralService
from services.notification_service import NotificationService


class AuthService:

    @staticmethod
    def get_client_ip():
        """
        Best-effort client IP (works behind Render / proxies).
        Checks common proxy headers, then remote_addr.
        """
        try:
            headers = request.headers
        except Exception:
            return None

        candidates = []
        for key in (
            "X-Forwarded-For",
            "X-Real-IP",
            "CF-Connecting-IP",
            "True-Client-IP",
            "X-Client-IP",
        ):
            val = headers.get(key)
            if val:
                # X-Forwarded-For may be "client, proxy1, proxy2"
                candidates.append(val.split(",")[0].strip())

        try:
            if request.remote_addr:
                candidates.append(request.remote_addr.strip())
        except Exception:
            pass

        for ip in candidates:
            if not ip:
                continue
            # Skip empty / obvious placeholders
            if ip.lower() in ("unknown", "null", "none", "-"):
                continue
            return ip[:100]
        return None

    @staticmethod
    def register(
        username,
        full_name,
        email,
        phone,
        password,
        membership,
        country,
        referral_code=None,
        ip_address=None,
    ):
        from models.membership import Membership

        membership_id = None
        if membership:
            try:
                membership_id = int(membership)
            except (TypeError, ValueError):
                m = Membership.query.filter_by(name=str(membership)).first()
                membership_id = m.id if m else None
            if membership_id and not Membership.query.get(membership_id):
                membership_id = None

        if not membership_id:
            starter = (
                Membership.query.filter_by(name="Starter").first()
                or Membership.query.filter_by(active=True)
                .order_by(Membership.price.asc())
                .first()
            )
            membership_id = starter.id if starter else None

        ip = ip_address or AuthService.get_client_ip()

        user = User(
            username=username,
            full_name=full_name,
            email=email,
            phone=phone,
            membership_id=membership_id,
            country=country or "Uganda",
            currency="UGX",
            currency_symbol="UGX",
            is_active=True,
            ip_address=ip,
        )
        user.set_password(password)
        user.referral_code = ReferralService.generate_code()

        db.session.add(user)
        db.session.commit()

        # First history row at signup
        try:
            from models.login_history import LoginHistory
            entry = LoginHistory(
                user_id=user.id,
                ip_address=ip,
                browser=(request.headers.get("User-Agent") or "")[:250],
                device="Signup",
                status="Registered",
            )
            if hasattr(entry, "login_time"):
                entry.login_time = datetime.utcnow()
            db.session.add(entry)
            db.session.commit()
        except Exception:
            db.session.rollback()

        if referral_code:
            try:
                ReferralService.register(user, referral_code)
            except Exception:
                pass

        try:
            NotificationService.send(user, "Welcome", "Welcome to Taskmill.")
        except Exception:
            pass

        return user

    @staticmethod

    @staticmethod
    def _parse_user_agent(ua: str):
        """Rough device / browser / OS from User-Agent."""
        ua = ua or ""
        u = ua.lower()
        # Device
        if "ipad" in u:
            device = "iPad"
        elif "iphone" in u:
            device = "iPhone"
        elif "android" in u and "mobile" in u:
            device = "Android phone"
        elif "android" in u:
            device = "Android tablet"
        elif "mobile" in u:
            device = "Mobile"
        else:
            device = "Desktop"
        # OS
        if "windows nt 10" in u or "windows nt 11" in u:
            os_name = "Windows 10/11"
        elif "windows" in u:
            os_name = "Windows"
        elif "mac os x" in u or "macintosh" in u:
            os_name = "macOS"
        elif "android" in u:
            os_name = "Android"
        elif "iphone" in u or "ipad" in u or "ios" in u:
            os_name = "iOS"
        elif "linux" in u:
            os_name = "Linux"
        else:
            os_name = "Unknown"
        # Browser
        if "edg/" in u:
            browser = "Edge"
        elif "chrome/" in u and "edg/" not in u:
            browser = "Chrome"
        elif "firefox/" in u:
            browser = "Firefox"
        elif "safari/" in u and "chrome/" not in u:
            browser = "Safari"
        elif "opr/" in u or "opera" in u:
            browser = "Opera"
        else:
            browser = (ua[:40] + "…") if len(ua) > 40 else (ua or "Unknown")
        return device, os_name, browser

    @staticmethod
    def _lookup_location(ip: str):
        if not ip or ip in ("127.0.0.1", "::1", "localhost"):
            return "Local / private"
        try:
            from utils.location import detect_location
            data = detect_location(ip)
            if not data or data.get("status") == "fail":
                return None
            city = data.get("city") or ""
            region = data.get("regionName") or data.get("region") or ""
            country = data.get("country") or ""
            parts = [p for p in (city, region, country) if p]
            return ", ".join(parts) if parts else None
        except Exception:
            return None

    def login_success(user, ip_address=None):
        """Update last IP on user + append login_history (always)."""
        from models.login_history import LoginHistory

        ip = ip_address or AuthService.get_client_ip()
        ua = ""
        try:
            ua = (request.headers.get("User-Agent") or "")[:250]
        except Exception:
            pass

        user.last_login = datetime.utcnow()
        if ip:
            user.ip_address = ip

        device, os_name, browser = AuthService._parse_user_agent(ua)
        location = AuthService._lookup_location(ip) if ip else None

        entry = LoginHistory(
            user_id=user.id,
            ip_address=ip,
            browser=browser,
            device=device,
            operating_system=os_name,
            status="Online",
        )
        if hasattr(entry, "location"):
            entry.location = location
        if hasattr(entry, "login_time"):
            entry.login_time = datetime.utcnow()

        # Alert on IP change
        try:
            prev = getattr(user, "ip_address", None)
            if ip and prev and prev != ip:
                from services.notification_service import NotificationService
                NotificationService.send(
                    user,
                    "New login",
                    f"New login from IP {ip}. If this wasn't you, change your password.",
                )
        except Exception:
            pass

        try:
            db.session.add(user)
            db.session.add(entry)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            # Still try to save IP on user alone
            try:
                if ip:
                    user.ip_address = ip
                    db.session.add(user)
                    db.session.commit()
            except Exception:
                db.session.rollback()
            print("login_success history error:", e)

    @staticmethod
    def can_login(user):
        if not user.is_active:
            return False, "Account inactive."
        if user.is_blocked:
            return False, "Account blocked."
        return True, ""

    @staticmethod
    def change_password(user, password):
        user.set_password(password)
        if hasattr(user, "must_change_password"):
            user.must_change_password = False
        db.session.commit()
        try:
            NotificationService.send(
                user, "Password Changed", "Your password has been updated."
            )
        except Exception:
            pass
