from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from models.task import Task
from models.notification import Notification
from extensions import db

profile_bp = Blueprint("profile", __name__, url_prefix="/profile")

@profile_bp.route("/")
@login_required
def index():
    completed = Task.query.filter_by(
    user_id=current_user.id,
    status="completed"
).count()
    total = Task.query.filter_by(user_id=current_user.id).count()
    
    return render_template("profile.html", 
                         completed=completed, 
                         total=total)

@profile_bp.route("/notifications")
@login_required
def notifications():

    notifications = Notification.query.filter_by(
        user_id=current_user.id
    ).order_by(
        Notification.created_at.desc()
    ).all()

    for notification in notifications:
        notification.is_read = True

    db.session.commit()

    return render_template(
        "profile/notifications.html",
        notifications=notifications
    )


@profile_bp.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    from flask import request, redirect, url_for, flash
    if request.method == "POST":
        current = request.form.get("current_password") or ""
        new = request.form.get("new_password") or ""
        confirm = request.form.get("confirm_password") or ""

        # After admin reset, current password is the temp one
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
        current_user.set_withdraw_pin(pin)
        db.session.commit()
        flash("Withdraw PIN saved.", "success")
        return redirect(url_for("wallet.withdraw"))
    return render_template("profile/withdraw_pin.html")
