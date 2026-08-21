
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
    """Frozen while balance < 0; assigned (Pending) when balance >= 0."""
    TaskService.sync_negative_and_combo_tasks(user)
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

    # Active combo products take priority — order-card UI
    if combo_tasks or (bal < 0 and current_user.combo_active):
        progress = TaskService.progress(current_user)
        combo_total = sum(float(t.product_price or 0) for t in combo_tasks)
        return render_template(
            "tasks/combo_queue.html",
            combo_tasks=combo_tasks,
            balance=bal,
            needs_deposit=bal < 0,
            progress=progress,
            combo_total=combo_total,
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
        flash("Submitted. Product price + commission credited to your wallet.", "success")

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
        try:
            from services.notification_service import NotificationService
            NotificationService.send(
                current_user.id,
                "Set 1 complete — unlock Set 2",
                "Great work! Message Support to unlock Set 2 so you can continue today's tasks.",
                "info",
            )
        except Exception:
            pass
        return redirect(url_for("task.set1_complete"))
    if progress.get("can_withdraw"):
        flash("You may now request a withdrawal (keep UGX 15,000 reserve).", "info")

    return redirect(url_for("task.index"))






@task_bp.route("/combo-guide")
@login_required
def combo_guide():
    """Platinum explainer when a combo is active or user is negative from combo."""
    _sync_combo_status(current_user)
    combo_tasks = [
        t for t in _combo_tasks(current_user)
        if t.status in ("assigned", "frozen", "pending")
    ]
    bal = float(current_user.available_balance or 0)
    combo_total = sum(float(getattr(t, "product_price", 0) or 0) for t in combo_tasks)
    return render_template(
        "tasks/combo_guide.html",
        combo_tasks=combo_tasks,
        combo_total=combo_total,
        bal=bal,
        user=current_user,
    )


@task_bp.route("/set1-complete")
@login_required
def set1_complete():
    """First-time friendly screen after Set 1 — clear path to Support."""
    progress = TaskService.progress(current_user)
    if not progress.get("needs_admin_unlock") and int(getattr(current_user, "daily_sets_completed", 0) or 0) >= 2:
        return redirect(url_for("task.index"))
    support = None
    try:
        from models.support import Support
        support = Support.query.first()
    except Exception:
        pass
    return render_template(
        "tasks/set1_complete.html",
        progress=progress,
        support=support,
        user=current_user,
    )


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


@task_bp.route("/park/<int:id>", methods=["POST", "GET"])
@login_required
def park(id):
    """Leave task assigned (pending) — user cannot get a new one until done."""
    task = Task.query.get_or_404(id)
    if task.user_id != current_user.id:
        flash("Not allowed.", "danger")
        return redirect(url_for("task.history"))
    if task.status in ("assigned", "frozen"):
        flash("Task saved as pending. Complete it before starting another.", "info")
    return redirect(url_for("task.history"))


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
        # Refund held product price
        price = float(task.product_price or 0)
        if price > 0:
            before = float(current_user.available_balance or 0)
            current_user.available_balance = before + price
            from models.wallet_transaction import WalletTransaction
            db.session.add(WalletTransaction(
                user_id=current_user.id,
                amount=price,
                transaction_type="task_hold_release",
                description=f"Hold released – {task.product_name}",
                balance_before=before,
                balance_after=float(current_user.available_balance),
            ))
        task.status = "cancelled"
        db.session.commit()
        flash("Task cancelled. Product hold returned to wallet.", "info")
    return redirect(url_for("dashboard.index"))


@task_bp.route("/skip", methods=["POST"])
@login_required
def skip_task():
    from services.task_service import TaskService
    ok, msg = TaskService.skip_current_task(current_user)
    flash(msg, "success" if ok else "warning")
    return redirect(url_for("task.index"))


@task_bp.route("/mystery-box", methods=["GET", "POST"])
@login_required
def mystery_box():
    from services.task_service import TaskService
    from models.settings import Settings
    from extensions import db
    import random
    TaskService.ensure_daily_reset(current_user)
    settings = Settings.query.first()
    if not settings or not getattr(settings, "mystery_box_enabled", True):
        flash("Mystery box is not available.", "warning")
        return redirect(url_for("dashboard.index"))
    tasks_per_set, daily_sets, total = TaskService._limits(current_user)
    done = int(current_user.tasks_completed_today or 0)
    if done < total:
        flash(f"Complete all {total} daily tasks first ({done}/{total}).", "warning")
        return redirect(url_for("task.index"))
    if getattr(current_user, "mystery_opened_today", False):
        flash("You already opened today's mystery box.", "info")
        return redirect(url_for("dashboard.index"))
    if request.method == "POST":
        lo = float(getattr(settings, "mystery_cash_min", 500) or 500)
        hi = float(getattr(settings, "mystery_cash_max", 3000) or 3000)
        if hi < lo:
            hi = lo
        roll = random.random()
        if roll < 0.15:
            prize = "try_again"
            msg = "Mystery box: try again tomorrow — better luck next time!"
        elif roll < 0.35:
            prize = "spin"
            current_user.daily_spins_used = max(0, int(current_user.daily_spins_used or 0) - 1)  # grant feel: reduce used
            msg = "Mystery box: +1 lucky spin!"
        else:
            cash = round(random.uniform(lo, hi), 0)
            before = float(current_user.available_balance or 0)
            current_user.available_balance = before + cash
            current_user.total_earned = (current_user.total_earned or 0) + cash
            from models.wallet_transaction import WalletTransaction
            db.session.add(WalletTransaction(
                user_id=current_user.id,
                amount=cash,
                transaction_type="mystery_box",
                description="Mystery box cash prize",
                balance_before=before,
                balance_after=float(current_user.available_balance),
            ))
            msg = f"Mystery box: you won cash!"
            prize = cash
        current_user.mystery_opened_today = True
        db.session.commit()
        flash(msg, "success")
        return redirect(url_for("dashboard.index"))
    return render_template("tasks/mystery_box.html", total=total, done=done)
