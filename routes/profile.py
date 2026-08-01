from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from models.task import Task
from models.notification import Notification
from extensions import db

profile_bp = Blueprint("profile", __name__, url_prefix="/profile")


def _ensure_membership(user):
    if user.membership_id and getattr(user, "membership", None):
        return
    try:
        from models.membership import Membership
        starter = (
            Membership.query.filter_by(name="Starter").first()
            or Membership.query.order_by(Membership.price.asc()).first()
        )
        if starter:
            user.membership_id = starter.id
            db.session.commit()
    except Exception:
        db.session.rollback()


@profile_bp.route("/", methods=["GET", "POST"])
@login_required
def index():
    _ensure_membership(current_user)

    if request.method == "POST":
        full_name = (request.form.get("full_name") or "").strip()
        username = (request.form.get("username") or "").strip()
        email = (request.form.get("email") or "").strip().lower()
        phone = (request.form.get("phone") or "").strip()
        password = request.form.get("password") or ""
        confirm = request.form.get("confirm_password") or ""

        if full_name:
            current_user.full_name = full_name

        if username and username != current_user.username:
            from models.user import User
            if User.query.filter(User.username == username, User.id != current_user.id).first():
                flash("Username already taken.", "danger")
                return redirect(url_for("profile.index"))
            current_user.username = username

        if email and email != (current_user.email or "").lower():
            from models.user import User
            if User.query.filter(User.email == email, User.id != current_user.id).first():
                flash("Email already in use.", "danger")
                return redirect(url_for("profile.index"))
            current_user.email = email

        current_user.phone = phone or current_user.phone

        if password:
            if password != confirm:
                flash("Passwords do not match.", "danger")
                return redirect(url_for("profile.index"))
            if len(password) < 6:
                flash("Password must be at least 6 characters.", "danger")
                return redirect(url_for("profile.index"))
            current_user.set_password(password)

        try:
            db.session.commit()
            flash("Profile updated.", "success")
        except Exception:
            db.session.rollback()
            flash("Could not update profile. Try again.", "danger")
        return redirect(url_for("profile.index"))

    try:
        completed = Task.query.filter_by(
            user_id=current_user.id, status="completed"
        ).count()
        total = Task.query.filter_by(user_id=current_user.id).count()
    except Exception:
        completed, total = 0, 0

    return render_template(
        "profile.html",
        completed=completed,
        total=total,
    )


@profile_bp.route("/notifications")
@login_required
def notifications():
    notifications = (
        Notification.query.filter_by(user_id=current_user.id)
        .order_by(Notification.created_at.desc())
        .all()
    )
    for notification in notifications:
        notification.is_read = True
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()

    return render_template(
        "profile/notifications.html",
        notifications=notifications,
    )


@profile_bp.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    if request.method == "POST":
        current = request.form.get("current_password") or ""
        new = request.form.get("new_password") or ""
        confirm = request.form.get("confirm_password") or ""

        if not current_user.check_password(current):
            flash("Current password is incorrect.", "danger")
            return render_template("profile/change_password.html")

        if len(new) < 6:
            flash("New password must be at least 6 characters.", "danger")
            return render_template("profile/change_password.html")

        if new != confirm:
            flash("New passwords do not match.", "danger")
            return render_template("profile/change_password.html")

        current_user.set_password(new)
        if hasattr(current_user, "must_change_password"):
            current_user.must_change_password = False
        db.session.commit()
        flash("Password updated successfully.", "success")

        if current_user.is_admin:
            return redirect(url_for("admin.dashboard"))
        return redirect(url_for("dashboard.index"))

    return render_template("profile/change_password.html")


@profile_bp.route("/withdraw-pin", methods=["GET", "POST"])
@login_required
def set_withdraw_pin():
    if request.method == "POST":
        pin = (request.form.get("pin") or "").strip()
        confirm = (request.form.get("confirm_pin") or "").strip()
        if not pin.isdigit() or len(pin) < 4 or len(pin) > 6:
            flash("PIN must be 4–6 digits.", "danger")
            return redirect(url_for("profile.set_withdraw_pin"))
        if pin != confirm:
            flash("PINs do not match.", "danger")
            return redirect(url_for("profile.set_withdraw_pin"))
        if not hasattr(current_user, "set_withdraw_pin"):
            flash("Withdraw PIN is not available yet. Restart the app after update.", "danger")
            return redirect(url_for("profile.index"))
        current_user.set_withdraw_pin(pin)
        db.session.commit()
        flash("Withdraw PIN saved.", "success")
        return redirect(url_for("wallet.withdraw"))
    return render_template("profile/withdraw_pin.html")


@profile_bp.route("/notifications/read-all", methods=["POST"])
@login_required
def mark_all_read():
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update({"is_read": True})
    db.session.commit()
    flash("All notifications marked as read.", "success")
    return redirect(url_for("profile.notifications"))
