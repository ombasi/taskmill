from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required, current_user

from extensions import db
from models.combo import Combo
from models.task import Task

combo_bp = Blueprint("combo", __name__, url_prefix="/combo")


@combo_bp.route("/")
@login_required
def index():
    combo = (
        Combo.query
        .filter_by(user_id=current_user.id, active=True)
        .filter(Combo.status.in_(["Pending", "Triggered"]))
        .order_by(Combo.id.desc())
        .first()
    )
    if not combo:
        flash("No active combo.", "info")
        return redirect(url_for("dashboard.index"))

    combo_tasks = (
        Task.query
        .filter_by(user_id=current_user.id, task_set=99)
        .filter(Task.status.in_(["assigned", "completed"]))
        .order_by(Task.id.asc())
        .all()
    )

    balance = float(current_user.available_balance or 0)
    needs_deposit = balance < 0

    return render_template(
        "tasks/combo.html",
        combo=combo,
        combo_tasks=combo_tasks,
        needs_deposit=needs_deposit,
        balance=balance,
    )
