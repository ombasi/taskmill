
"""Simple scheduled jobs (call from Render Cron or external ping)."""
import os
from datetime import datetime
from flask import Blueprint, jsonify, request
from extensions import db

jobs_bp = Blueprint("jobs", __name__, url_prefix="/jobs")


def _authorized():
    secret = os.getenv("CRON_SECRET") or os.getenv("SECRET_KEY", "dev-secret-key-12345")
    token = request.headers.get("X-Cron-Token") or request.args.get("token")
    return token and token == secret


@jobs_bp.route("/daily-reset", methods=["POST", "GET"])
def daily_reset():
    if not _authorized():
        return jsonify({"error": "unauthorized"}), 401
    from models.user import User
    from services.task_service import TaskService
    n = 0
    for user in User.query.filter_by(is_admin=False).limit(5000).all():
        try:
            TaskService.ensure_daily_reset(user)
            n += 1
        except Exception as e:
            print("daily reset user", user.id, e)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
    return jsonify({"ok": True, "users_checked": n, "at": datetime.utcnow().isoformat()})


@jobs_bp.route("/ping")
def ping():
    return jsonify({"ok": True, "time": datetime.utcnow().isoformat()})


@jobs_bp.route("/balance-interest", methods=["POST", "GET"])
def job_balance_interest():
    """Run daily interest for all eligible users (Render cron / ping)."""
    from models.user import User
    from services.balance_interest import apply_interest, MIN_UGX
    from extensions import db
    q = User.query.filter(
        User.is_admin.is_(False),
        User.is_blocked.is_(False),
        User.available_balance >= MIN_UGX,
    ).limit(2000)
    ok_n = 0
    for u in q:
        try:
            ok, _, amt = apply_interest(u, commit=True)
            if ok:
                ok_n += 1
        except Exception as e:
            print("interest", u.id, e)
            try:
                db.session.rollback()
            except Exception:
                pass
    return {"credited": ok_n}
