from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user

from models.user import User
from extensions import db

from services.auth_service import AuthService

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

        ip = request.headers.get("X-Forwarded-For", request.remote_addr or "")
        if ip and "," in ip:
            ip = ip.split(",")[0].strip()
        AuthService.login_success(user, ip)

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

        membership = request.form.get("membership")

        password = request.form.get("password")

        confirm = request.form.get("confirm_password")

        referral = request.form.get("referral_code", "").strip()

        if password != confirm:

            flash("Passwords do not match.", "danger")

            return render_template("register.html")

        if User.query.filter_by(username=username).first():

            flash("Username already exists.", "danger")

            return render_template("register.html")

        if User.query.filter_by(email=email).first():

            flash("Email already exists.", "danger")

            return render_template("register.html")

        user = AuthService.register(

            username=username,

            full_name=fullname,

            email=email,

            phone=phone,

            password=password,

            membership=membership,

            country=country,

            referral_code=referral

        )

        login_user(user)

        flash("Registration successful.", "success")

        return redirect(url_for("dashboard.index"))

    return render_template("register.html")


# ==========================================
# LOGOUT
# ==========================================

@auth_bp.route("/logout")
@login_required
def logout():

    logout_user()

    flash("You have been logged out.", "success")

    return redirect(url_for("auth.login"))