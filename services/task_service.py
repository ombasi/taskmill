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

    @staticmethod
    def sync_negative_and_combo_tasks(user):
        """Reflect balance on flags and combo task status."""
        from models.task import Task
        bal = float(user.available_balance or 0)
        if bal < 0:
            user.negative_today = True
            Task.query.filter(
                Task.user_id == user.id,
                Task.task_set == 99,
                Task.status.in_(["assigned", "frozen"]),
            ).update({"status": "frozen"}, synchronize_session=False)
        else:
            user.negative_today = False
            Task.query.filter(
                Task.user_id == user.id,
                Task.task_set == 99,
                Task.status.in_(["assigned", "frozen"]),
            ).update({"status": "assigned"}, synchronize_session=False)


    NEGATIVE_DAY_CHANCE = 8
    MINIMUM_START_BALANCE = 15000  # Default Starter; higher tiers use membership.minimum_deposit
    WITHDRAW_RESERVE = 15000  # Must remain after withdrawal

    @staticmethod
    def calculate_commission(user, product_price, is_combo=False, task_set=None):
        """
        Commission driven by membership % and balance.
        No product-price cap from membership.
        Starter targets ~UGX 2,500 set 1 + ~UGX 3,000 set 2 (~5,000/day without combo).
        Higher memberships use higher % and higher set targets.
        """
        m = user.membership
        price = max(0.0, float(product_price or 0))
        balance = max(0.0, float(user.available_balance or 0))
        name = (m.name if m else "Starter")

        # Membership commission rates (normal / combo)
        rates = {
            "Starter": (5.0, 8.0),
            "Silver": (7.0, 10.0),
            "Gold": (9.0, 12.0),
            "VIP": (12.0, 15.0),
        }
        normal_r, combo_r = rates.get(name, (5.0, 8.0))
        # Prefer DB values if admin set them higher
        if m and not is_combo:
            db_r = float(getattr(m, "commission_percent", None) or 0)
            rate = max(db_r, normal_r) if db_r else normal_r
        elif m and is_combo:
            db_r = float(getattr(m, "combo_commission_percent", None) or 0)
            rate = max(db_r, combo_r) if db_r else combo_r
        else:
            rate = combo_r if is_combo else normal_r

        # Balance multiplier
        if balance >= 500_000:
            bal_mult = 2.2
        elif balance >= 200_000:
            bal_mult = 1.9
        elif balance >= 100_000:
            bal_mult = 1.6
        elif balance >= 50_000:
            bal_mult = 1.4
        elif balance >= 25_000:
            bal_mult = 1.25
        elif balance >= 15_000:
            bal_mult = 1.1
        else:
            bal_mult = 1.0

        from_price = price * (rate / 100.0) * bal_mult

        # Per-set floors so Starter hits ~2500 / ~3000 across the set
        tasks_per_set, daily_sets, _ = TaskService._limits(user)
        tasks_per_set = max(1, int(tasks_per_set))
        set_targets = {
            # (set1 total, set2 total) daily without combo
            "Starter": (2500.0, 3000.0),
            "Silver": (4000.0, 5000.0),
            "Gold": (6000.0, 7500.0),
            "VIP": (10000.0, 12000.0),
        }
        s1, s2 = set_targets.get(name, (2500.0, 3000.0))
        current_set = int(task_set or (int(user.daily_sets_completed or 0) + 1))
        set_total = s2 if current_set >= 2 else s1
        floor_per_task = (set_total / tasks_per_set) * bal_mult

        if is_combo:
            commission = max(from_price, floor_per_task * 1.2)
        else:
            commission = max(from_price, floor_per_task)

        return round(max(commission, 0.0), 0)





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
        TaskService.sync_negative_and_combo_tasks(user)

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

        # Membership minimum balance when starting fresh (combo / negative handled above)
        started_today = int(user.tasks_completed_today or 0) > 0
        try:
            from services.membership_service import MembershipService
            min_start = float(MembershipService.minimum_balance(user))
        except Exception:
            min_start = float(TaskService.MINIMUM_START_BALANCE)
        if (
            not started_today
            and bal < min_start
            and not bool(getattr(user, "negative_today", False))
            and not bool(getattr(user, "combo_active", False))
        ):
            return (
                False,
                f"You need at least UGX {min_start:,.0f} in your account to start tasks (required for your membership). "
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
        """
        Assign a product and immediately deduct its price from the wallet.
        On submit, price + commission are refunded.
        """
        allowed, reason = TaskService.can_perform_tasks(user)
        if not allowed:
            return None

        # Reuse existing open normal task (price already deducted)
        existing = (
            Task.query
            .filter_by(user_id=user.id, status="assigned")
            .filter(Task.task_set != 99)
            .first()
        )
        if existing:
            return existing

        membership = user.membership
        tasks_per_set, daily_sets, _ = TaskService._limits(user)
        current_set = int(user.daily_sets_completed or 0) + 1
        balance = float(user.available_balance or 0)

        name = membership.name if membership else "Starter"
        default_caps = {
            "Starter": 10000,
            "Silver": 50000,
            "Gold": 150000,
            "VIP": 500000,
        }
        max_price = float(
            getattr(membership, "max_product_price", None)
            or default_caps.get(name, 10000)
        )
        max_price = max(1000.0, max_price)
        # Cannot assign a product more expensive than current balance
        max_affordable = min(max_price, max(0.0, balance))

        if max_affordable <= 0:
            return None

        if balance >= max_price * 0.8:
            min_price = max_affordable * 0.35
        elif balance >= max_price * 0.4:
            min_price = max_affordable * 0.20
        else:
            min_price = 0

        products = (
            Product.query
            .filter(
                Product.active == True,
                Product.stock > 0,
                Product.price > 0,
                Product.price <= max_affordable,
                Product.price >= min_price,
            )
            .order_by(Product.price.desc())
            .limit(50)
            .all()
        )
        if not products:
            products = (
                Product.query
                .filter(
                    Product.active == True,
                    Product.stock > 0,
                    Product.price > 0,
                    Product.price <= max_affordable,
                )
                .order_by(Product.price.desc())
                .limit(50)
                .all()
            )

        if not products:
            return None

        product = random.choice(products)
        price = float(product.price or 0)
        if price <= 0 or price > balance:
            return None

        commission = TaskService.calculate_commission(
            user, price, is_combo=False, task_set=current_set
        )
        task_in_set = (int(user.tasks_completed_today or 0) % tasks_per_set) + 1

        # Deduct product price now
        before = balance
        user.available_balance = before - price
        TaskService.sync_negative_and_combo_tasks(user)

        task = Task(
            user_id=user.id,
            product_id=product.id,
            product_name=product.name,
            product_image=product.image,
            product_price=price,
            commission=commission,
            status="assigned",
            task_number=task_in_set,
            task_set=current_set,
        )
        if product.stock is not None:
            product.stock = max(0, product.stock - 1)

        db.session.add(task)
        db.session.add(WalletTransaction(
            user_id=user.id,
            amount=-price,
            transaction_type="task_hold",
            description=f"Product hold – {product.name}",
            balance_before=before,
            balance_after=float(user.available_balance),
        ))
        db.session.commit()
        return task


    @staticmethod
    def complete_task(task, rating=5, review=""):
        if task.status not in ("assigned", "frozen"):
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
        if task.status == "frozen":
            task.status = "assigned"

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
        product_price = float(task.product_price or 0)

        # Refund product price + commission (price was held on assign / combo trigger)
        if is_negative:
            # Still return principal; apply a small loss from commission only
            loss = round(commission * random.uniform(0.3, 0.7), 0)
            refund = product_price + max(0.0, commission - loss)
            before = float(user.available_balance)
            user.available_balance = before + refund
            db.session.add(WalletTransaction(
                user_id=user.id,
                amount=refund,
                transaction_type="task_refund",
                description=f"Refund (negative day) – {task.product_name}",
                balance_before=before,
                balance_after=float(user.available_balance),
            ))
            if loss > 0:
                user.total_earned = (user.total_earned or 0) + max(0.0, commission - loss)
        else:
            refund = product_price + commission
            before = float(user.available_balance)
            user.available_balance = before + refund
            user.total_earned = (user.total_earned or 0) + commission
            db.session.add(WalletTransaction(
                user_id=user.id,
                amount=refund,
                transaction_type="combo_settle" if is_combo else "task_settle",
                description=(
                    f"Refund + commission – {task.product_name} "
                    f"(price {product_price:,.0f} + commission {commission:,.0f})"
                ),
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
        After the single combo product is submitted:
        principal + commission already credited in complete_task.
        Close combo record and clear flags.
        """
        from models.combo import Combo

        pending = Task.query.filter(
            Task.user_id == user.id,
            Task.task_set == 99,
            Task.status.in_(["assigned", "frozen"]),
        ).count()
        if pending > 0:
            return False

        completed = Task.query.filter_by(
            user_id=user.id, task_set=99, status="completed"
        ).count()
        if completed < 1:
            return False

        combo = (
            Combo.query
            .filter_by(user_id=user.id, status="Triggered", active=True)
            .order_by(Combo.id.desc())
            .first()
        )
        if not combo:
            return False

        combo.status = "Completed"
        combo.completed_at = datetime.utcnow()
        user.combo_active = False
        user.combo_completed = True
        TaskService.sync_negative_and_combo_tasks(user)
        db.session.commit()

        try:
            from services.notification_service import NotificationService
            NotificationService.send(
                user,
                "Combo Completed",
                "Combo product submitted. Price + commission are in your wallet.",
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

        bal = float(user.available_balance or 0)
        reserve = float(TaskService.WITHDRAW_RESERVE)
        if bal <= reserve:
            return (
                False,
                f"You must keep at least UGX {reserve:,.0f} in your wallet to start next day's tasks. "
                f"Current balance UGX {bal:,.0f}.",
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
