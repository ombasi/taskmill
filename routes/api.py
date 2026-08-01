
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
