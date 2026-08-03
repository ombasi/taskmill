
"""Lightweight JSON API for future mobile clients."""
from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user, login_user
from extensions import db

api_bp = Blueprint("api", __name__, url_prefix="/api/v1")


def _user_payload(u):
    return {
        "id": u.id,
        "username": u.username,
        "full_name": u.full_name,
        "email": u.email,
        "phone": u.phone,
        "country": u.country,
        "balance": float(u.available_balance or 0),
        "pending_balance": float(u.pending_balance or 0),
        "membership": u.membership.name if u.membership else None,
        "referral_code": u.referral_code,
        "tasks_today": int(u.tasks_completed_today or 0),
        "sets_today": int(u.daily_sets_completed or 0),
    }


@api_bp.route("/health")
def health():
    return jsonify({"ok": True, "service": "taskmill"})


@api_bp.route("/me")
@login_required
def me():
    return jsonify(_user_payload(current_user))


@api_bp.route("/wallet")
@login_required
def wallet():
    from services.wallet_service import WalletService
    txs = WalletService.history(current_user) or []
    return jsonify({
        "balance": float(current_user.available_balance or 0),
        "pending": float(current_user.pending_balance or 0),
        "combo": float(current_user.combo_balance or 0),
        "transactions": [
            {
                "id": t.id,
                "type": t.transaction_type,
                "amount": float(t.amount or 0),
                "description": t.description,
                "created_at": t.created_at.isoformat() if t.created_at else None,
            }
            for t in txs[:50]
        ],
    })


@api_bp.route("/tasks/progress")
@login_required
def task_progress():
    from services.task_service import TaskService
    return jsonify(TaskService.progress(current_user))


@api_bp.route("/notifications")
@login_required
def notifications():
    from models.notification import Notification
    rows = (
        Notification.query.filter_by(user_id=current_user.id)
        .order_by(Notification.created_at.desc())
        .limit(50)
        .all()
    )
    return jsonify([
        {
            "id": n.id,
            "title": n.title,
            "message": getattr(n, "message", None) or getattr(n, "body", None),
            "is_read": bool(n.is_read),
            "created_at": n.created_at.isoformat() if n.created_at else None,
        }
        for n in rows
    ])


@api_bp.route("/badges")
@login_required
def badges():
    try:
        from app import _ensure_notification_broadcast_column
        _ensure_notification_broadcast_column()
    except Exception:
        pass

    """Live counts for nav badges (polled every few seconds)."""
    from models.notification import Notification
    from models.chat import ChatMessage

    data = {
        "notifications": 0,
        "chat": 0,
        "pending_deposits": 0,
        "pending_withdrawals": 0,
        "pending_tasks": 0,
    }

    try:
        data["notifications"] = Notification.query.filter_by(
            user_id=current_user.id, is_read=False
        ).count()
    except Exception:
        pass

    try:
        if current_user.is_admin:
            data["chat"] = ChatMessage.query.filter_by(
                is_from_admin=False, is_read=False
            ).count()
            try:
                from models.deposit import Deposit
                data["pending_deposits"] = Deposit.query.filter(
                    Deposit.status.in_(["Pending", "pending"])
                ).count()
            except Exception:
                data["pending_deposits"] = 0
            try:
                from models.withdraw import Withdrawal
                data["pending_withdrawals"] = Withdrawal.query.filter(
                    Withdrawal.status.in_(["Pending", "pending"])
                ).count()
            except Exception:
                try:
                    from models.withdraw import Withdraw
                    data["pending_withdrawals"] = Withdraw.query.filter(
                        Withdraw.status.in_(["Pending", "pending"])
                    ).count()
                except Exception:
                    data["pending_withdrawals"] = 0
        else:
            data["chat"] = ChatMessage.query.filter_by(
                user_id=current_user.id, is_from_admin=True, is_read=False
            ).count()
            try:
                from models.task import Task
                data["pending_tasks"] = Task.query.filter(
                    Task.user_id == current_user.id,
                    Task.status.in_(["assigned", "frozen"]),
                ).count()
            except Exception:
                data["pending_tasks"] = 0
    except Exception as e:
        print("badges:", e)

    data["total"] = int(data["notifications"]) + int(data["chat"])
    if getattr(current_user, "is_admin", False):
        data["total"] += int(data["pending_deposits"]) + int(data["pending_withdrawals"])
    return jsonify(data)


@api_bp.route("/popups")
@login_required
def popups():
    try:
        from app import _ensure_notification_broadcast_column
        _ensure_notification_broadcast_column()
    except Exception:
        pass

    """Unread toasts + active broadcasts for the current user."""
    from models.notification import Notification
    q = Notification.query.filter_by(user_id=current_user.id, is_read=False)
    rows = q.order_by(Notification.created_at.desc()).limit(20).all()
    toasts = []
    broadcasts = []
    for n in rows:
        item = {
            "id": n.id,
            "title": n.title,
            "message": n.message,
            "created_at": n.created_at.isoformat() if n.created_at else None,
        }
        if getattr(n, "is_broadcast", False):
            broadcasts.append(item)
        else:
            toasts.append(item)
    return jsonify({"toasts": toasts[:5], "broadcasts": broadcasts[:1]})


@api_bp.route("/popups/<int:nid>/dismiss", methods=["POST"])
@login_required
def dismiss_popup(nid):
    from models.notification import Notification
    n = Notification.query.get_or_404(nid)
    if n.user_id != current_user.id:
        return jsonify({"ok": False}), 403
    n.is_read = True
    db.session.commit()
    return jsonify({"ok": True})
