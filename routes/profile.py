from datetime import datetime, date
import os
import uuid
from flask import (
    Blueprint, render_template, request, redirect, url_for, flash, current_app
)
from flask_login import login_required, current_user
from models.notification import Notification
from extensions import db

profile_bp = Blueprint("profile", __name__, url_prefix="/profile")

PHONE_CHANGES_PER_MONTH = 2


def _month_key():
    return date.today().strftime("%Y-%m")


def _phone_changes_left(user):
    month = _month_key()
    if (user.phone_change_month or "") != month:
        return PHONE_CHANGES_PER_MONTH
    used = int(user.phone_change_count or 0)
    return max(0, PHONE_CHANGES_PER_MONTH - used)


def _avatar_url(user):
    if getattr(user, "profile_image", None):
        return url_for("static", filename=f"uploads/avatars/{user.profile_image}")
    name = (user.full_name or user.username or "U")
    return f"https://ui-avatars.com/api/?name={name.replace(' ', '+')}&background=6366f1&color=fff&size=256"


@profile_bp.route("/", methods=["GET", "POST"])
@login_required
def index():
    left = _phone_changes_left(current_user)

    if request.method == "POST":
        action = (request.form.get("action") or "phone").strip()

        if action == "phone":
            phone = (request.form.get("phone") or "").strip()
            if not phone:
                flash("Enter a phone number.", "danger")
                return redirect(url_for("profile.index"))
            if phone == (current_user.phone or ""):
                flash("That is already your phone number.", "info")
                return redirect(url_for("profile.index"))
            if left <= 0:
                flash("Phone number can only be changed twice per month.", "danger")
                return redirect(url_for("profile.index"))

            month = _month_key()
            if (current_user.phone_change_month or "") != month:
                current_user.phone_change_month = month
                current_user.phone_change_count = 0
            current_user.phone = phone
            current_user.phone_change_count = int(current_user.phone_change_count or 0) + 1
            db.session.commit()
            flash(f"Phone updated. {_phone_changes_left(current_user)} change(s) left this month.", "success")
            return redirect(url_for("profile.index"))

        if action == "avatar":
            f = request.files.get("avatar")
            if not f or not f.filename:
                flash("Choose an image file.", "danger")
                return redirect(url_for("profile.index"))
            name = f.filename.rsplit(".", 1)
            ext = name[1].lower() if len(name) == 2 else "png"
            if ext not in {"png", "jpg", "jpeg", "webp", "gif"}:
                flash("Use png, jpg, webp, or gif.", "danger")
                return redirect(url_for("profile.index"))
            folder = os.path.join(current_app.static_folder, "uploads", "avatars")
            os.makedirs(folder, exist_ok=True)
            fname = f"{current_user.id}_{uuid.uuid4().hex[:12]}.{ext}"
            f.save(os.path.join(folder, fname))
            # remove old
            try:
                old = current_user.profile_image
                if old:
                    op = os.path.join(folder, old)
                    if os.path.isfile(op):
                        os.remove(op)
            except Exception:
                pass
            current_user.profile_image = fname
            db.session.commit()
            flash("Profile photo updated.", "success")
            return redirect(url_for("profile.index"))

        flash("Invalid action.", "danger")
        return redirect(url_for("profile.index"))

    return render_template(
        "profile.html",
        avatar_url=_avatar_url(current_user),
        phone_changes_left=left,
        phone_changes_max=PHONE_CHANGES_PER_MONTH,
    )


@profile_bp.route("/notifications")
@login_required
def notifications():
    notifications = (
        Notification.query.filter_by(user_id=current_user.id)
        .order_by(Notification.created_at.desc())
        .all()
    )
    for n in notifications:
        n.is_read = True
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
    return render_template("profile/notifications.html", notifications=notifications)


@profile_bp.route("/notifications/read-all", methods=["POST"])
@login_required
def mark_all_read():
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update({"is_read": True})
    db.session.commit()
    flash("All notifications marked as read.", "success")
    return redirect(url_for("profile.notifications"))


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
        return redirect(url_for("profile.index"))
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



