from flask import Blueprint, render_template, request, redirect, url_for, flash
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

        login_user(user, remember=remember)

        AuthService.login_success(user, AuthService.get_client_ip())

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
            return render_template("register.html", max_dob=_max_dob())

        if not country:
            flash("Please select your country.", "danger")
            return render_template("register.html", max_dob=_max_dob())
        if sex not in ("Male", "Female", "Other"):
            flash("Please select your sex.", "danger")
            return render_template("register.html", max_dob=_max_dob())
        if not accept_terms:
            flash("You must accept the Terms & Conditions.", "danger")
            return render_template("register.html", max_dob=_max_dob())
        dob = _parse_dob(dob_raw)
        if not dob or _age(dob) < 20:
            flash("You must be at least 20 years old to register.", "danger")
            return render_template("register.html", max_dob=_max_dob())

        if User.query.filter_by(username=username).first():

            flash("Username already exists.", "danger")

            return render_template("register.html", max_dob=_max_dob())

        if User.query.filter_by(email=email).first():

            flash("Email already exists.", "danger")

            return render_template("register.html", max_dob=_max_dob())

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
        AuthService.login_success(user, AuthService.get_client_ip())

        flash("Registration successful.", "success")

        return redirect(url_for("dashboard.index"))

    return render_template("register.html", max_dob=_max_dob())


# ==========================================
# LOGOUT
# ==========================================

@auth_bp.route("/logout")
@login_required
def logout():

    logout_user()

    flash("You have been logged out.", "success")

    return redirect(url_for("auth.login"))