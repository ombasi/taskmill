from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user

from extensions import db
from models.task import Task
from services.task_service import TaskService
from utils.security import csrf_protect

task_bp = Blueprint("task", __name__, url_prefix="/tasks")


@task_bp.route("/", methods=["GET"])
@login_required
def index():
    bal = float(current_user.available_balance or 0)

    # Prefer an assigned COMBO product when balance is cleared (>= 0)
    combo_task = (
        Task.query
        .filter_by(user_id=current_user.id, task_set=99, status="assigned")
        .order_by(Task.id.asc())
        .first()
    )
    if combo_task is not None:
        if bal < 0:
            flash(
                "Deposit to clear your negative combo balance before reviewing these products.",
                "warning",
            )
            return redirect(url_for("wallet.deposit"))
        progress = TaskService.progress(current_user)
        return render_template(
            "tasks/task.html",
            task=combo_task,
            progress=progress,
            is_combo=True,
        )

    allowed, reason = TaskService.can_perform_tasks(current_user)
    if not allowed:
        flash(reason, "warning")
        if "negative" in reason.lower() or "deposit" in reason.lower():
            return redirect(url_for("wallet.deposit"))
        if "admin" in reason.lower() or "set 1" in reason.lower():
            return redirect(url_for("dashboard.index"))
        if "withdraw" in reason.lower():
            return redirect(url_for("wallet.withdraw"))
        return redirect(url_for("dashboard.index"))

    task = TaskService.assign_task(current_user)
    if not task:
        flash(
            "No products available within your membership product limit. "
            "Ask admin to add products or raise max product price.",
            "warning",
        )
        return redirect(url_for("dashboard.index"))

    progress = TaskService.progress(current_user)
    return render_template("tasks/task.html", task=task, progress=progress, is_combo=False)


@task_bp.route("/submit/<int:id>", methods=["POST"])
@login_required
@csrf_protect
def submit(id):
    task = Task.query.get_or_404(id)

    if task.user_id != current_user.id:
        flash("Unauthorized.", "danger")
        return redirect(url_for("task.index"))

    if task.status != "assigned":
        flash("This task is no longer available.", "warning")
        return redirect(url_for("task.index"))

    is_combo_task = int(getattr(task, "task_set", 0) or 0) == 99

    # Combo tasks: require non-negative balance first
    if is_combo_task:
        if float(current_user.available_balance or 0) < 0:
            flash(
                "Your account is negative because of a combo. "
                "Deposit to clear the balance before reviewing combo products.",
                "warning",
            )
            return redirect(url_for("wallet.deposit"))

    rating = int(request.form.get("rating", 5))
    review = request.form.get("review", "")

    ok, result = TaskService.complete_task(task, rating=rating, review=review)

    if not ok:
        flash(result, "danger")
        return redirect(url_for("task.index"))

    if result == "negative":
        flash(
            "Negative trading result applied. Withdrawal is blocked until cleared.",
            "warning",
        )
    else:
        flash("Task completed successfully. Commission credited.", "success")

    progress = TaskService.progress(current_user)
    if progress.get("needs_admin_unlock"):
        flash(
            "Set 1 complete. Contact admin to unlock Set 2 before you can continue.",
            "info",
        )
        return redirect(url_for("dashboard.index"))

    if progress.get("can_withdraw"):
        flash("You may now request a withdrawal.", "info")

    return redirect(url_for("task.index"))


@task_bp.route("/history")
@login_required
def history():
    # Include pending (assigned) and completed — combo products appear here too
    tasks = (
        Task.query
        .filter(
            Task.user_id == current_user.id,
            Task.status.in_(["assigned", "completed", "cancelled"]),
        )
        .order_by(Task.created_at.desc())
        .limit(150)
        .all()
    )
    completed = sum(1 for t in tasks if t.status == "completed")
    pending = sum(1 for t in tasks if t.status == "assigned")
    total_earnings = float(current_user.total_earned or 0)
    return render_template(
        "history.html",
        history=tasks,
        completed=completed,
        pending=pending,
        total_earnings=total_earnings,
    )


@task_bp.route("/cancel/<int:id>")
@login_required
def cancel(id):
    task = Task.query.get_or_404(id)
    if task.user_id != current_user.id:
        flash("Unauthorized.", "danger")
        return redirect(url_for("task.index"))
    if task.status == "assigned":
        task.status = "cancelled"
        db.session.commit()
        flash("Task cancelled.", "info")
    return redirect(url_for("dashboard.index"))
