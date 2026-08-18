CANNED_REPLIES = [
    ("Clear combo", "Deposit enough to bring your balance to 0 or above, then open Tasks and submit the frozen product to earn combo commission."),
    ("Set payout", "Go to Wallet → Withdraw, add your payout method once. Admin will confirm it before you can withdraw."),
    ("Withdraw PIN", "Set your withdraw PIN under Profile. If you forgot it, ask admin to reset it."),
    ("Pending deposit", "Deposits are reviewed by admin. Please share your transaction ID and wait for approval."),
]

import os
import uuid
from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    flash,
    request,
    current_app,
)
from flask_login import login_required, current_user
from sqlalchemy import func
from werkzeug.utils import secure_filename

from extensions import db
from models.chat import ChatMessage
from models.user import User
from models.notification import Notification

chat_bp = Blueprint("chat", __name__, url_prefix="/chat")

ALLOWED_EXTENSIONS = {
    "png", "jpg", "jpeg", "gif", "webp",
    "pdf", "doc", "docx", "txt", "zip",
    "xls", "xlsx", "csv",
}
MAX_CHAT_FILE_MB = 5


def admin_required_view():
    if not current_user.is_authenticated:
        flash("Admins only.", "danger")
        return False
    if getattr(current_user, "is_admin", False) or getattr(current_user, "is_agent", False):
        return True
    flash("Admins only.", "danger")
    return False


def _allowed(filename):
    if not filename or "." not in filename:
        return False
    return filename.rsplit(".", 1)[-1].lower() in ALLOWED_EXTENSIONS


def _save_chat_file(file_storage):
    """Save uploaded file to static/uploads/chat/. Returns (rel_path, original_name) or (None, None)."""
    if not file_storage or not file_storage.filename:
        return None, None
    original = secure_filename(file_storage.filename)
    if not original or not _allowed(original):
        return None, None

    upload_root = current_app.config.get("UPLOAD_FOLDER") or os.path.join(
        current_app.root_path, "static", "uploads"
    )
    chat_dir = os.path.join(upload_root, "chat")
    os.makedirs(chat_dir, exist_ok=True)

    ext = original.rsplit(".", 1)[-1].lower()
    stored = f"{uuid.uuid4().hex}.{ext}"
    full = os.path.join(chat_dir, stored)
    file_storage.save(full)
    # path relative to static/
    rel = f"uploads/chat/{stored}"
    return rel, original


def _parse_message_and_file():
    text = (request.form.get("message") or "").strip()
    if len(text) > 2000:
        text = text[:2000]
    file = request.files.get("attachment")
    rel, original = _save_chat_file(file)
    if file and file.filename and not rel:
        return None, None, "File type not allowed. Use images, PDF, Word, Excel, TXT or ZIP (max 5MB)."
    if not text and not rel:
        return None, None, "Type a message or attach a file."
    if not text and rel:
        text = f"[Attachment: {original}]"
    return text, (rel, original), None


# ---------- USER ----------
@chat_bp.route("/", methods=["GET", "POST"])
@login_required
def inbox():
    if current_user.is_admin:
        return redirect(url_for("chat.admin_inbox"))

    if request.method == "POST":
        text, att, err = _parse_message_and_file()
        if err:
            flash(err, "warning")
            return redirect(url_for("chat.inbox"))
        rel, original = att if att else (None, None)
        msg = ChatMessage(
            user_id=current_user.id,
            is_from_admin=False,
            message=text,
            attachment=rel,
            attachment_name=original,
            is_read=False,
        )
        db.session.add(msg)
        db.session.commit()
        try:
            from services.admin_alerts import alert_chat
            _preview = getattr(msg, "message", None) or getattr(msg, "body", None) or getattr(message, "message", None) or ""
            alert_chat(current_user, str(_preview))
        except Exception as _ac:
            print("admin alert chat:", _ac)
        flash("Message sent.", "success")
        return redirect(url_for("chat.inbox"))

    messages = (
        ChatMessage.query
        .filter_by(user_id=current_user.id)
        .order_by(ChatMessage.created_at.asc())
        .all()
    )
    ChatMessage.query.filter_by(
        user_id=current_user.id, is_from_admin=True, is_read=False
    ).update({"is_read": True})
    db.session.commit()

    return render_template("chat/user_chat.html", messages=messages)


# ---------- ADMIN ----------
@chat_bp.route("/admin")
@login_required
def admin_inbox():
    if not admin_required_view():
        return redirect(url_for("dashboard.index"))

    last_map = dict(
        db.session.query(
            ChatMessage.user_id,
            func.max(ChatMessage.created_at),
        ).group_by(ChatMessage.user_id).all()
    )
    unread_map = dict(
        db.session.query(
            ChatMessage.user_id,
            func.count(ChatMessage.id),
        )
        .filter(
            ChatMessage.is_from_admin == False,
            ChatMessage.is_read == False,
        )
        .group_by(ChatMessage.user_id)
        .all()
    )
    user_ids = list(last_map.keys())
    users = User.query.filter(User.id.in_(user_ids)).all() if user_ids else []
    users_by_id = {u.id: u for u in users}
    # Agents only see downline chats
    allowed_ids = None
    if getattr(current_user, "is_agent", False) and not getattr(current_user, "is_admin", False):
        from routes.admin import get_downline_ids
        allowed_ids = get_downline_ids(current_user.id)
    conversations = []
    for uid, last_at in sorted(last_map.items(), key=lambda x: x[1] or 0, reverse=True):
        if allowed_ids is not None and uid not in allowed_ids:
            continue
        u = users_by_id.get(uid)
        if u:
            conversations.append((u, last_at, unread_map.get(uid, 0)))

    return render_template("chat/admin_inbox.html", conversations=conversations)


@chat_bp.route("/admin/<int:user_id>", methods=["GET", "POST"])
@login_required
def admin_thread(user_id):
    if not admin_required_view():
        return redirect(url_for("dashboard.index"))

    user = User.query.get_or_404(user_id)
    if getattr(current_user, "is_agent", False) and not getattr(current_user, "is_admin", False):
        from routes.admin import get_downline_ids, can_manage_user
        if not can_manage_user(current_user, user):
            flash("You can only chat with users in your referral tree.", "danger")
            return redirect(url_for("chat.admin_inbox"))

    if request.method == "POST":
        text, att, err = _parse_message_and_file()
        if err:
            flash(err, "warning")
            return redirect(url_for("chat.admin_thread", user_id=user_id))
        rel, original = att if att else (None, None)
        msg = ChatMessage(
            user_id=user.id,
            is_from_admin=True,
            admin_id=current_user.id,
            message=text,
            attachment=rel,
            attachment_name=original,
            is_read=False,
        )
        db.session.add(msg)
        preview = text[:200] if text else (original or "Attachment")
        db.session.add(Notification(
            user_id=user.id,
            title="Support replied",
            message=preview,
            is_read=False,
        ))
        db.session.commit()
        flash("Reply sent.", "success")
        return redirect(url_for("chat.admin_thread", user_id=user_id))

    messages = (
        ChatMessage.query
        .filter_by(user_id=user.id)
        .order_by(ChatMessage.created_at.asc())
        .all()
    )
    ChatMessage.query.filter_by(
        user_id=user.id, is_from_admin=False, is_read=False
    ).update({"is_read": True})
    db.session.commit()

    return render_template(
        "chat/admin_thread.html",
        messages=messages,
        canned=CANNED_REPLIES,
        chat_user=user,
    )
