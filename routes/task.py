
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user

from extensions import db
from models.task import Task
from services.task_service import TaskService
from utils.security import csrf_protect

task_bp = Blueprint("task", __name__, url_prefix="/tasks")


def _combo_tasks(user):
    return (
        Task.query
        .filter_by(user_id=user.id, task_set=99)
        .filter(Task.status.in_(["assigned", "frozen", "completed"]))
        .order_by(Task.id.asc())
        .all()
    )


def _sync_combo_status(user):
    """Frozen while balance < 0; assigned (pending) when cleared."""
    bal = float(user.available_balance or 0)
    q = Task.query.filter_by(user_id=user.id, task_set=99)
    if bal < 0:
        q.filter(Task.status.in_(["assigned", "frozen"])).update(
            {"status": "frozen"}, synchronize_session=False
        )
    else:
        q.filter(Task.status.in_(["assigned", "frozen"])).update(
            {"status": "assigned"}, synchronize_session=False
        )
    db.session.commit()


@task_bp.route("/", methods=["GET"])
@login_required
def index():
    bal = float(current_user.available_balance or 0)
    _sync_combo_status(current_user)

    combo_tasks = [
        t for t in _combo_tasks(current_user)
        if t.status in ("assigned", "frozen")
    ]

    # Active combo products take priority — show as product cards
    if combo_tasks:
        progress = TaskService.progress(current_user)
        return render_template(
            "tasks/combo_queue.html",
            combo_tasks=combo_tasks,
            balance=bal,
            needs_deposit=bal < 0,
            progress=progress,
        )

    allowed, reason = TaskService.can_perform_tasks(current_user)
    if not allowed:
        flash(reason, "warning")
        low = reason.lower()
        if "negative" in low or "deposit" in low:
            return redirect(url_for("wallet.deposit"))
        if "admin" in low or "set 1" in low:
            return redirect(url_for("dashboard.index"))
        if "withdraw" in low:
            return redirect(url_for("wallet.withdraw"))
        return redirect(url_for("dashboard.index"))

    task = TaskService.assign_task(current_user)
    if not task:
        flash(
            "No products available within your membership product limit.",
            "warning",
        )
        return redirect(url_for("dashboard.index"))

    progress = TaskService.progress(current_user)
    return render_template(
        "tasks/task.html", task=task, progress=progress, is_combo=False
    )


@task_bp.route("/review/<int:id>", methods=["GET"])
@login_required
def review(id):
    """Open a specific combo (or normal) product for review."""
    task = Task.query.get_or_404(id)
    if task.user_id != current_user.id:
        flash("Unauthorized.", "danger")
        return redirect(url_for("task.index"))

    if task.status not in ("assigned", "frozen"):
        flash("This task is no longer available.", "warning")
        return redirect(url_for("task.index"))

    bal = float(current_user.available_balance or 0)
    is_combo = int(getattr(task, "task_set", 0) or 0) == 99

    if is_combo and bal < 0:
        flash(
            "Your combo is frozen. Deposit to clear the negative balance, then submit.",
            "warning",
        )
        return redirect(url_for("wallet.deposit"))

    if task.status == "frozen":
        task.status = "assigned"
        db.session.commit()

    progress = TaskService.progress(current_user)
    return render_template(
        "tasks/task.html",
        task=task,
        progress=progress,
        is_combo=is_combo,
    )


@task_bp.route("/submit/<int:id>", methods=["POST"])
@login_required
@csrf_protect
def submit(id):
    task = Task.query.get_or_404(id)

    if task.user_id != current_user.id:
        flash("Unauthorized.", "danger")
        return redirect(url_for("task.index"))

    if task.status not in ("assigned", "frozen"):
        flash("This task is no longer available.", "warning")
        return redirect(url_for("task.index"))

    is_combo_task = int(getattr(task, "task_set", 0) or 0) == 99

    if is_combo_task:
        if float(current_user.available_balance or 0) < 0:
            flash(
                "Deposit to clear your negative combo balance before submitting.",
                "warning",
            )
            return redirect(url_for("wallet.deposit"))
        if task.status == "frozen":
            task.status = "assigned"
            db.session.commit()

    rating = int(request.form.get("rating", 5))
    review = request.form.get("review", "")

    ok, result = TaskService.complete_task(task, rating=rating, review=review)

    if not ok:
        flash(result, "danger")
        return redirect(url_for("task.index"))

    if result == "negative":
        flash("Negative trading result applied.", "warning")
    else:
        flash("Product submitted successfully. Commission credited.", "success")

    # After combo item, go back to combo queue if more remain
    if is_combo_task:
        left = Task.query.filter(
            Task.user_id == current_user.id,
            Task.task_set == 99,
            Task.status.in_(["assigned", "frozen"]),
        ).count()
        if left:
            return redirect(url_for("task.index"))
        flash("All combo products completed.", "success")
        return redirect(url_for("dashboard.index"))

    progress = TaskService.progress(current_user)
    if progress.get("needs_admin_unlock"):
        flash("Set 1 complete. Contact admin to unlock Set 2.", "info")
        return redirect(url_for("dashboard.index"))
    if progress.get("can_withdraw"):
        flash("You may now request a withdrawal (keep UGX 15,000 reserve).", "info")

    return redirect(url_for("task.index"))


@task_bp.route("/history")
@login_required
def history():
    _sync_combo_status(current_user)
    tasks = (
        Task.query
        .filter(
            Task.user_id == current_user.id,
            Task.status.in_(["assigned", "frozen", "completed", "cancelled"]),
        )
        .order_by(Task.created_at.desc())
        .limit(150)
        .all()
    )
    completed = sum(1 for t in tasks if t.status == "completed")
    pending = sum(1 for t in tasks if t.status in ("assigned", "frozen"))
    total_earnings = float(current_user.total_earned or 0)
    bal = float(current_user.available_balance or 0)
    return render_template(
        "history.html",
        history=tasks,
        completed=completed,
        pending=pending,
        total_earnings=total_earnings,
        balance=bal,
    )


@task_bp.route("/cancel/<int:id>")
@login_required
def cancel(id):
    task = Task.query.get_or_404(id)
    if task.user_id != current_user.id:
        flash("Unauthorized.", "danger")
        return redirect(url_for("task.index"))
    if int(getattr(task, "task_set", 0) or 0) == 99:
        flash("Combo products cannot be cancelled.", "warning")
        return redirect(url_for("task.index"))
    if task.status in ("assigned", "frozen"):
        task.status = "cancelled"
        db.session.commit()
        flash("Task cancelled.", "info")
    return redirect(url_for("dashboard.index"))
