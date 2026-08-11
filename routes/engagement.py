
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from utils.security import csrf_protect
from extensions import db
from datetime import date

engagement_bp = Blueprint("engagement", __name__, url_prefix="/engagement")


@engagement_bp.route("/check-in", methods=["GET", "POST"])
@login_required
@csrf_protect
def check_in():
    from services.engagement_service import do_checkin, month_calendar, progress_in_level
    if request.method == "POST":
        ok, msg, data = do_checkin(current_user)
        flash(msg if ok else msg, "success" if ok else "warning")
        if ok and data.get("cash"):
            try:
                from helpers.currency import money
                flash(f"Bonus {money(current_user, data['cash'])} credited!", "success")
            except Exception:
                pass
        return redirect(url_for("engagement.check_in"))
    cal = month_calendar(current_user)
    prog = progress_in_level(current_user)
    today_done = any(d.get("is_today") and d.get("checked") for d in cal)
    return render_template(
        "engagement/checkin.html",
        calendar=cal,
        progress=prog,
        today_done=today_done,
        streak=int(getattr(current_user, "checkin_streak", 0) or 0),
        quality=float(getattr(current_user, "quality_score", 50) or 50),
    )


@engagement_bp.route("/kyc", methods=["GET", "POST"])
@login_required
@csrf_protect
def kyc():
    from models.engagement import KycDocument
    import os, uuid
    from werkzeug.utils import secure_filename
    if request.method == "POST":
        f = request.files.get("document")
        doc_type = (request.form.get("doc_type") or "id").strip()[:40]
        if not f or not f.filename:
            flash("Choose a document image.", "danger")
            return redirect(url_for("engagement.kyc"))
        ext = secure_filename(f.filename).rsplit(".", 1)[-1].lower() if "." in f.filename else "jpg"
        if ext not in ("jpg", "jpeg", "png", "webp", "pdf"):
            flash("Use JPG, PNG, or PDF.", "danger")
            return redirect(url_for("engagement.kyc"))
        folder = os.path.join("static", "uploads", "kyc")
        os.makedirs(folder, exist_ok=True)
        fname = f"{current_user.id}_{uuid.uuid4().hex}.{ext}"
        f.save(os.path.join(folder, fname))
        row = KycDocument(user_id=current_user.id, doc_type=doc_type, file_path=f"uploads/kyc/{fname}", status="Pending")
        db.session.add(row)
        current_user.kyc_status = "Pending"
        db.session.commit()
        flash("Document submitted. We will review shortly.", "success")
        return redirect(url_for("engagement.kyc"))
    docs = KycDocument.query.filter_by(user_id=current_user.id).order_by(KycDocument.id.desc()).limit(10).all()
    return render_template("engagement/kyc.html", docs=docs)


@engagement_bp.route("/notify-prefs", methods=["POST"])
@login_required
@csrf_protect
def notify_prefs():
    current_user.telegram_chat_id = (request.form.get("telegram_chat_id") or "").strip() or None
    current_user.whatsapp_number = (request.form.get("whatsapp_number") or "").strip() or None
    db.session.commit()
    flash("Notification preferences saved.", "success")
    return redirect(url_for("profile.index"))
