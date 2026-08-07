from flask import session, Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user

from models.user import User
from extensions import db

from services.auth_service import AuthService

from datetime import datetime, date as date_cls

def _parse_dob(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except Exception:
        return None

def _age(dob):
    today = date_cls.today()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))

def _max_dob():
    today = date_cls.today()
    try:
        return date_cls(today.year - 20, today.month, today.day).isoformat()
    except ValueError:
        return date_cls(today.year - 20, today.month, 28).isoformat()

def _world_countries():
    try:
        from utils.world_currencies import all_country_names
        return all_country_names()
    except Exception:
        return ["Uganda", "Kenya", "Tanzania", "Germany", "United States", "Canada", "United Kingdom", "Nigeria"]


auth_bp = Blueprint("auth", __name__)


# ==========================================
# LOGIN
# ==========================================

@auth_bp.route("/login", methods=["GET", "POST"])
def login():

    if current_user.is_authenticated:

        if current_user.is_admin:
            return redirect(url_for("admin.dashboard"))

        return redirect(url_for("dashboard.index"))

    if request.method == "POST":

        username = request.form.get("username", "").strip()

        password = request.form.get("password", "")

        remember = bool(request.form.get("remember"))

        user = User.query.filter(

            (User.username == username) |
            (User.email == username)

        ).first()

        if not user:

            flash("Invalid username or password.", "danger")

            return render_template("login.html")

        if not user.check_password(password):

            flash("Invalid username or password.", "danger")

            return render_template("login.html")

        allowed, message = AuthService.can_login(user)

        if not allowed:

            flash(message, "danger")

            return render_template("login.html")

        # 2FA for admin / agent when enabled
        needs_2fa = (
            (getattr(user, "is_admin", False) or getattr(user, "is_agent", False))
            and getattr(user, "totp_enabled", False)
            and getattr(user, "totp_secret", None)
        )
        if needs_2fa:
            from flask import session
            session["pending_2fa_uid"] = user.id
            session["pending_2fa_remember"] = remember
            flash("Enter the 6-digit code from your authenticator app.", "info")
            return redirect(url_for("auth.two_factor"))

        # Admins and agents without 2FA yet — force setup
        if (getattr(user, "is_admin", False) or getattr(user, "is_agent", False)) and not getattr(user, "totp_enabled", False):
            login_user(user, remember=remember)
            AuthService.login_success(user, AuthService.get_client_ip())
            try:
                from utils.location import get_client_ip, apply_geo_currency
                apply_geo_currency(user, ip=get_client_ip(request), force=True)
                db.session.commit()
            except Exception as _geo_e:
                print("geo currency:", _geo_e)
            flash("Please set up authenticator app 2FA for your staff account.", "warning")
            return redirect(url_for("auth.setup_2fa"))

        login_user(user, remember=remember)

        AuthService.login_success(user, AuthService.get_client_ip())
        try:
            from utils.location import get_client_ip, apply_geo_currency
            apply_geo_currency(user, ip=get_client_ip(request), force=True)
            db.session.commit()
        except Exception as _geo_e:
            print("geo currency:", _geo_e)

        # Fix users who registered without membership
        if not user.membership_id:
            from models.membership import Membership
            starter = Membership.query.filter_by(name="Starter").first()
            if starter:
                user.membership_id = starter.id
                db.session.commit()

        # Admin-forced password reset
        if getattr(user, "must_change_password", False):
            flash(
                "Your password was reset by admin. Please set a new password.",
                "warning"
            )
            return redirect(url_for("profile.change_password"))

        flash("Welcome back.", "success")

        if user.is_admin:
            return redirect(url_for("admin.dashboard"))
        if getattr(user, "is_agent", False):
            return redirect(url_for("admin.users"))

        return redirect(url_for("dashboard.index"))

    return render_template("login.html")


# ==========================================
# REGISTER
# ==========================================

@auth_bp.route("/register", methods=["GET", "POST"])
def register():

    if current_user.is_authenticated:

        return redirect(url_for("dashboard.index"))

    if request.method == "POST":

        username = request.form.get("username", "").strip()

        fullname = request.form.get("full_name", "").strip()

        email = request.form.get("email", "").strip().lower()

        phone = request.form.get("phone", "").strip()

        country = request.form.get("country", "").strip()
        sex = (request.form.get("sex") or "").strip()
        dob_raw = request.form.get("date_of_birth") or ""
        accept_terms = request.form.get("accept_terms") == "1"

        membership = request.form.get("membership")

        password = request.form.get("password")

        confirm = request.form.get("confirm_password")

        referral = request.form.get("referral_code", "").strip()

        if password != confirm:
            flash("Passwords do not match.", "danger")
            return render_template("register.html", world_countries=_world_countries(), max_dob=_max_dob())

        if not country:
            flash("Please select your country.", "danger")
            return render_template("register.html", world_countries=_world_countries(), max_dob=_max_dob())
        if sex not in ("Male", "Female", "Other"):
            flash("Please select your sex.", "danger")
            return render_template("register.html", world_countries=_world_countries(), max_dob=_max_dob())
        if not accept_terms:
            flash("You must accept the Terms & Conditions.", "danger")
            return render_template("register.html", world_countries=_world_countries(), max_dob=_max_dob())
        dob = _parse_dob(dob_raw)
        if not dob or _age(dob) < 20:
            flash("You must be at least 20 years old to register.", "danger")
            return render_template("register.html", world_countries=_world_countries(), max_dob=_max_dob())

        if User.query.filter_by(username=username).first():

            flash("Username already exists.", "danger")

            return render_template("register.html", world_countries=_world_countries(), max_dob=_max_dob())

        if User.query.filter_by(email=email).first():

            flash("Email already exists.", "danger")

            return render_template("register.html", world_countries=_world_countries(), max_dob=_max_dob())

        user = AuthService.register(
            username=username,
            full_name=fullname,
            email=email,
            phone=phone,
            password=password,
            membership=membership,
            country=country,
            referral_code=referral,
            ip_address=AuthService.get_client_ip(),
        )

        user.sex = sex
        user.date_of_birth = dob
        user.accepted_terms_at = datetime.utcnow()
        from extensions import db as _db
        _db.session.commit()

        login_user(user)
        session["sv"] = int(getattr(user, "session_version", 0) or 0)
        AuthService.login_success(user, AuthService.get_client_ip())
        try:
            from utils.location import get_client_ip, apply_geo_currency
            apply_geo_currency(user, ip=get_client_ip(request), force=True)
            db.session.commit()
        except Exception as _geo_e:
            print("geo currency:", _geo_e)

        flash("Registration successful.", "success")

        return redirect(url_for("dashboard.index"))

    return render_template("register.html", world_countries=_world_countries(), max_dob=_max_dob())


# ==========================================
# LOGOUT
# ==========================================

@auth_bp.route("/logout")
@login_required
def logout():

    logout_user()

    flash("You have been logged out.", "success")

    return redirect(url_for("auth.login"))

@auth_bp.route("/forgot-password")
def forgot_password():
    return render_template("forgot_password.html")


# ==========================================
# TWO-FACTOR (Authenticator app)
# ==========================================

@auth_bp.route("/2fa", methods=["GET", "POST"])
def two_factor():
    from flask import session
    from utils.totp_util import verify_code

    uid = session.get("pending_2fa_uid")
    if not uid:
        return redirect(url_for("auth.login"))
    user = User.query.get(uid)
    if not user:
        session.pop("pending_2fa_uid", None)
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        code = request.form.get("code") or ""
        if verify_code(user.totp_secret, code):
            remember = bool(session.pop("pending_2fa_remember", False))
            session.pop("pending_2fa_uid", None)
            login_user(user, remember=remember)
            AuthService.login_success(user, AuthService.get_client_ip())
        try:
            from utils.location import get_client_ip, apply_geo_currency
            apply_geo_currency(user, ip=get_client_ip(request), force=True)
            db.session.commit()
        except Exception as _geo_e:
            print("geo currency:", _geo_e)
            flash("2FA verified. Welcome.", "success")
            if user.is_admin:
                return redirect(url_for("admin.dashboard"))
            if getattr(user, "is_agent", False):
                return redirect(url_for("admin.users"))
            return redirect(url_for("dashboard.index"))
        flash("Invalid or expired code. Try again.", "danger")

    return render_template("auth/two_factor.html")


@auth_bp.route("/2fa/setup", methods=["GET", "POST"])
@login_required
def setup_2fa():
    """Enable authenticator app 2FA (required for admins)."""
    from utils.totp_util import new_secret, provisioning_uri, qr_data_url, verify_code
    from flask import session

    if not (current_user.is_admin or getattr(current_user, "is_agent", False)):
        flash("2FA setup is for staff accounts.", "warning")
        return redirect(url_for("dashboard.index"))

    # Prepare pending secret
    if not session.get("totp_setup_secret") or request.args.get("reset"):
        session["totp_setup_secret"] = new_secret()

    secret = session["totp_setup_secret"]
    uri = provisioning_uri(secret, current_user.username, issuer="Taskmill")
    qr = None
    try:
        qr = qr_data_url(uri)
    except Exception as e:
        print("qr_data_url:", e)
        flash("QR image unavailable — enter the manual key in your authenticator app.", "warning")

    if request.method == "POST":
        code = request.form.get("code") or ""
        if verify_code(secret, code):
            current_user.totp_secret = secret
            current_user.totp_enabled = True
            db.session.commit()
            session.pop("totp_setup_secret", None)
            flash("Authenticator app linked successfully.", "success")
            if current_user.is_admin:
                return redirect(url_for("admin.dashboard"))
            return redirect(url_for("admin.users"))
        flash("Code did not match. Scan the QR again and enter a fresh code.", "danger")

    return render_template(
        "auth/setup_2fa.html",
        secret=secret,
        qr_data_url=qr,
        otpauth_uri=uri,
        enabled=bool(getattr(current_user, "totp_enabled", False)),
    )


@auth_bp.route("/2fa/disable", methods=["POST"])
@login_required
def disable_2fa():
    """Full admins only can disable their own 2FA after code check — discourage."""
    from utils.totp_util import verify_code
    if not current_user.is_admin:
        flash("Not allowed.", "danger")
        return redirect(url_for("dashboard.index"))
    code = request.form.get("code") or ""
    if not verify_code(current_user.totp_secret, code):
        flash("Invalid code.", "danger")
        return redirect(url_for("auth.setup_2fa"))
    current_user.totp_enabled = False
    current_user.totp_secret = None
    db.session.commit()
    flash("2FA disabled. Re-enable before next sensitive actions.", "warning")
    return redirect(url_for("auth.setup_2fa"))
