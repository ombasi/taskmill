"""
Taskmill V2 – Task Engine

Rules (current product rules):
- Products are limited by membership.max_product_price
- Complete Set 1 → locked until admin unlocks Set 2
- Withdraw only after completing required sets (typically 2)
  AND account has no negative balance / negative_today flag
"""

from datetime import datetime, date
import random

from extensions import db
from models.task import Task
from models.product import Product
from models.wallet_transaction import WalletTransaction


class TaskService:

    NEGATIVE_DAY_CHANCE = 8
    MINIMUM_START_BALANCE = 15000  # UGX required before submitting tasks


    @staticmethod
    def _limits(user):
        m = user.membership
        tasks_per_set = int(
            getattr(m, "tasks_per_set", None)
            or getattr(m, "daily_tasks", None)
            or 2
        ) if m else 2
        daily_sets = int(getattr(m, "daily_sets", None) or 2) if m else 2
        total = tasks_per_set * daily_sets
        return tasks_per_set, daily_sets, total

    @staticmethod
    def ensure_daily_reset(user):
        today = date.today()
        if user.last_daily_reset == today:
            return False

        user.tasks_completed_today = 0
        user.daily_sets_completed = 0
        user.mandatory_completed = False
        user.daily_limit_reached = False
        user.withdrawal_completed_today = False
        user.must_withdraw_today = False
        user.negative_today = False
        user.daily_spins_used = 0
        # Admin must unlock set 2 after set 1
        if hasattr(user, "set2_unlocked"):
            user.set2_unlocked = False
        user.last_daily_reset = today

        Task.query.filter_by(user_id=user.id, status="assigned").update(
            {"status": "cancelled"}
        )
        db.session.commit()
        return True

    @staticmethod
    def can_perform_tasks(user):
        TaskService.ensure_daily_reset(user)

        if user.is_blocked or not user.is_active:
            return False, "Account is suspended."

        if not user.membership:
            return False, "No active membership."

        bal = float(user.available_balance or 0)

        # Auto-clear negative_today once balance is restored
        if bal >= 0 and getattr(user, "negative_today", False):
            user.negative_today = False
            db.session.commit()

        if bal < 0:
            return (
                False,
                "Your account has a negative balance (combo charge). "
                "Please deposit to clear it before continuing tasks.",
            )

        # Pending combo reviews: allow when balance >= 0 (skip 15k / set gates for combo)
        pending_combo = Task.query.filter_by(
            user_id=user.id, task_set=99, status="assigned"
        ).count()
        if pending_combo > 0:
            return True, "OK"

        # 15,000 rule only when starting fresh (no work today, no active combo)
        started_today = int(user.tasks_completed_today or 0) > 0
        if (
            bal < TaskService.MINIMUM_START_BALANCE
            and not started_today
            and not bool(user.combo_active)
        ):
            return (
                False,
                f"You need at least UGX {TaskService.MINIMUM_START_BALANCE:,} in your account to start tasks. "
                "Please deposit or top up first.",
            )

        tasks_per_set, daily_sets, total = TaskService._limits(user)
        done = int(user.tasks_completed_today or 0)
        sets_done = int(user.daily_sets_completed or 0)

        # Finished all sets for the day
        if sets_done >= daily_sets or done >= total:
            user.mandatory_completed = True
            user.daily_limit_reached = True
            return False, "You have completed all task sets for today."

        # After set 1: wait for admin to unlock set 2
        if sets_done >= 1:
            unlocked = bool(getattr(user, "set2_unlocked", False))
            if not unlocked:
                return (
                    False,
                    "Set 1 complete. Contact admin to unlock Set 2 before continuing.",
                )

        return True, "OK"

    @staticmethod
    def assign_task(user):
        allowed, reason = TaskService.can_perform_tasks(user)
        if not allowed:
            return None

        # Reuse existing normal task only (combo tasks are handled separately)
        existing = (
            Task.query
            .filter_by(user_id=user.id, status="assigned")
            .filter(Task.task_set != 99)
            .first()
        )
        if existing:
            return existing

        membership = user.membership
        max_price = float(membership.max_product_price or 1000)
        tasks_per_set, daily_sets, _ = TaskService._limits(user)
        current_set = int(user.daily_sets_completed or 0) + 1

        # Products strictly within membership max price
        products = (
            Product.query
            .filter(
                Product.active == True,
                Product.stock > 0,
                Product.price <= max_price,
                Product.price > 0,
            )
            .order_by(db.func.random())
            .limit(30)
            .all()
        )

        if not products:
            return None

        product = random.choice(products)
        percent = float(getattr(membership, "commission_percent", 0.5) or 0.5)
        commission = round(float(product.price) * (percent / 100.0), 2)

        task_in_set = (int(user.tasks_completed_today or 0) % tasks_per_set) + 1

        task = Task(
            user_id=user.id,
            product_id=product.id,
            product_name=product.name,
            product_image=product.image,
            product_price=product.price,
            commission=commission,
            status="assigned",
            task_number=task_in_set,
            task_set=current_set,
        )
        if product.stock is not None:
            product.stock = max(0, product.stock - 1)

        db.session.add(task)
        db.session.commit()
        return task

    @staticmethod
    def complete_task(task, rating=5, review=""):
        if task.status != "assigned":
            return False, "Task already completed or cancelled."

        user = task.user
        TaskService.ensure_daily_reset(user)
        is_combo = int(getattr(task, "task_set", 0) or 0) == 99

        # Combo reviews require cleared (non-negative) balance
        if is_combo and float(user.available_balance or 0) < 0:
            return (
                False,
                "Deposit to clear your negative combo balance before submitting.",
            )

        tasks_per_set, daily_sets, total = TaskService._limits(user)

        # Normal tasks can roll a negative trading day; combo tasks never do
        is_negative = False
        if (
            not is_combo
            and not user.negative_today
            and random.randint(1, 100) <= TaskService.NEGATIVE_DAY_CHANCE
        ):
            is_negative = True
            user.negative_today = True

        task.status = "completed"
        task.rating = max(1, min(5, int(rating or 5)))
        task.review = (review or "")[:2000]
        task.completed_at = datetime.utcnow()

        commission = float(task.commission or 0)

        if is_negative:
            loss = round(commission * random.uniform(0.3, 0.7), 0)
            loss = min(loss, max(0.0, float(user.available_balance)))
            if loss > 0:
                before = float(user.available_balance)
                user.available_balance -= loss
                db.session.add(WalletTransaction(
                    user_id=user.id,
                    amount=-loss,
                    transaction_type="negative_day",
                    description=f"Trading loss on task #{task.id}",
                    balance_before=before,
                    balance_after=float(user.available_balance),
                ))
        else:
            # Pay commission for this product (combo or normal)
            before = float(user.available_balance)
            user.available_balance += commission
            user.total_earned = (user.total_earned or 0) + commission
            db.session.add(WalletTransaction(
                user_id=user.id,
                amount=commission,
                transaction_type="combo_commission" if is_combo else "task_commission",
                description=f"Commission – {task.product_name}",
                balance_before=before,
                balance_after=float(user.available_balance),
            ))

        if not is_combo:
            user.completed_tasks = (user.completed_tasks or 0) + 1
            user.tasks_completed_today = (user.tasks_completed_today or 0) + 1
            done = int(user.tasks_completed_today or 0)
            if done > 0 and done % tasks_per_set == 0:
                user.daily_sets_completed = (user.daily_sets_completed or 0) + 1
                if user.daily_sets_completed >= daily_sets:
                    user.mandatory_completed = True
                    user.daily_limit_reached = True

        db.session.commit()

        # When BOTH combo products are done → refund combo amount (principal)
        if is_combo:
            TaskService._finalize_combo_if_done(user)

        try:
            if not is_combo:
                from services.combo_service import ComboService
                ComboService.check_combo(user)
        except Exception:
            pass

        return True, "negative" if is_negative else "success"

    @staticmethod
    def _finalize_combo_if_done(user):
        """
        After both combo product reviews are completed:
        refund the full combo charge so the user recovers the money that
        created the negative, on top of commissions already paid.
        """
        from models.combo import Combo

        pending = Task.query.filter_by(
            user_id=user.id, task_set=99, status="assigned"
        ).count()
        if pending > 0:
            return False

        completed = Task.query.filter_by(
            user_id=user.id, task_set=99, status="completed"
        ).count()
        if completed < 2:
            return False

        combo = (
            Combo.query
            .filter_by(user_id=user.id, status="Triggered", active=True)
            .order_by(Combo.id.desc())
            .first()
        )
        if not combo:
            return False

        refund = float(combo.amount or 0)
        if refund > 0:
            before = float(user.available_balance or 0)
            user.available_balance = before + refund
            user.total_earned = (user.total_earned or 0) + refund
            db.session.add(WalletTransaction(
                user_id=user.id,
                amount=refund,
                transaction_type="combo_refund",
                description=(
                    f"Combo completed – refund of charge for "
                    f"{combo.product1_name} + {combo.product2_name}"
                ),
                balance_before=before,
                balance_after=float(user.available_balance),
            ))

        combo.status = "Completed"
        combo.completed_at = datetime.utcnow()
        user.combo_active = False
        user.negative_today = False
        db.session.commit()

        try:
            from services.notification_service import NotificationService
            NotificationService.send(
                user,
                "Combo Completed",
                f"Combo finished. UGX {refund:,.0f} refunded plus your product commissions.",
            )
        except Exception:
            pass
        return True

    @staticmethod
    def can_withdraw(user):
        """
        Withdraw only when:
        - at least 2 sets completed today (or membership daily_sets if lower)
        - no negative_today
        - available_balance >= 0
        """
        TaskService.ensure_daily_reset(user)
        tasks_per_set, daily_sets, total = TaskService._limits(user)
        required_sets = min(2, daily_sets)
        sets_done = int(user.daily_sets_completed or 0)

        if float(user.available_balance or 0) < 0:
            return False, "Cannot withdraw with a negative balance."

        if user.negative_today:
            return False, "Cannot withdraw on a negative trading day."

        if sets_done < required_sets:
            return (
                False,
                f"Complete {required_sets} task sets before withdrawing. "
                f"You have finished {sets_done}.",
            )

        return True, "OK"

    @staticmethod
    def admin_unlock_set2(user):
        """Admin unlocks set 2 after user finishes set 1."""
        if int(user.daily_sets_completed or 0) < 1:
            return False, "User has not completed Set 1 yet."
        if hasattr(user, "set2_unlocked"):
            user.set2_unlocked = True
        else:
            # fallback flag via combo_completed unused field if column missing
            pass
        user.must_withdraw_today = False
        user.daily_limit_reached = False
        user.mandatory_completed = False
        db.session.commit()
        return True, "Set 2 unlocked for user."

    @staticmethod
    def mark_withdrawal_done(user):
        user.withdrawal_completed_today = True
        user.must_withdraw_today = False
        db.session.commit()

    @staticmethod
    def progress(user):
        TaskService.ensure_daily_reset(user)
        tasks_per_set, daily_sets, total = TaskService._limits(user)
        done = int(user.tasks_completed_today or 0)
        sets_done = int(user.daily_sets_completed or 0)
        current_set = min(sets_done + 1, daily_sets)
        can_wd, wd_reason = TaskService.can_withdraw(user)
        return {
            "completed_today": done,
            "mandatory": total,
            "remaining": max(0, total - done),
            "tasks_per_set": tasks_per_set,
            "daily_sets": daily_sets,
            "sets_completed": sets_done,
            "current_set": current_set,
            "tasks_in_current_set": done % tasks_per_set if done < total else tasks_per_set,
            "mandatory_completed": bool(user.mandatory_completed),
            "must_withdraw": False,  # withdraw is post 2-sets, not mid-set gate
            "needs_admin_unlock": sets_done >= 1 and not bool(getattr(user, "set2_unlocked", False)) and sets_done < daily_sets,
            "can_withdraw": can_wd,
            "withdraw_reason": wd_reason,
            "negative_today": bool(user.negative_today),
            "withdrawal_done": bool(user.withdrawal_completed_today),
            "max_product_price": float(user.membership.max_product_price) if user.membership else 0,
        }
