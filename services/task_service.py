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

    @staticmethod
    def _fmt_money(user, amount):
        try:
            from helpers.currency import money
            return money(user, amount)
        except Exception:
            return f"UGX {float(amount or 0):,.0f}"

    WITHDRAW_RESERVE = 15000  # Must remain after withdrawal

    # Daily non-combo profit targets (UGX). Hard cap = target + 500.
    DAILY_PROFIT_TARGETS = {
        "Starter": 5000.0,
        "Silver": 10000.0,
        "Gold": 30000.0,
        "VIP": 100000.0,
    }
    DAILY_PROFIT_SLACK = 500.0  # allowed excess above target

    @staticmethod
    def daily_profit_target(user):
        m = getattr(user, "membership", None)
        name = (m.name if m else "Starter") or "Starter"
        return float(TaskService.DAILY_PROFIT_TARGETS.get(name, 5000.0))

    @staticmethod
    def today_non_combo_commission(user):
        """Sum of commissions already earned today on normal (non-combo) tasks."""
        from datetime import datetime
        from sqlalchemy import func
        today = datetime.utcnow().date()
        try:
            total = (
                db.session.query(func.coalesce(func.sum(Task.commission), 0))
                .filter(
                    Task.user_id == user.id,
                    Task.status == "completed",
                    Task.task_set != 99,
                    func.date(Task.completed_at) == today,
                )
                .scalar()
            )
            return float(total or 0)
        except Exception:
            return 0.0

    @staticmethod
    def calculate_commission(user, product_price, is_combo=False, task_set=None):
        """
        Normal tasks: size commissions so the day totals ~ membership target
        (Starter 5k, Silver 10k, Gold 30k, VIP 100k), hard-capped at target + 500.
        Combo tasks are uncapped by the daily target.
        """
        price = float(product_price or 0)
        m = getattr(user, "membership", None)
        name = (m.name if m else "Starter") or "Starter"

        # Combo: percentage of product, no daily target cap
        if is_combo:
            rates = {
                "Starter": 8.0,
                "Silver": 10.0,
                "Gold": 12.0,
                "VIP": 15.0,
            }
            rate = rates.get(name, 8.0)
            if m:
                db_r = float(getattr(m, "combo_commission_percent", None) or 0)
                if db_r > 0:
                    rate = db_r
            _raw = round(max(price * (rate / 100.0), 0.0), 0)
            try:
                from services.engagement_service import quality_multiplier
                _raw = float(_raw) * quality_multiplier(user)
            except Exception:
                pass
            return round(float(_raw), 0)

        target = TaskService.daily_profit_target(user)
        hard_cap = target + TaskService.DAILY_PROFIT_SLACK
        earned = TaskService.today_non_combo_commission(user)
        remaining_budget = max(0.0, hard_cap - earned)

        tasks_per_set, daily_sets, total_tasks = TaskService._limits(user)
        total_tasks = max(1, int(total_tasks))
        done = int(getattr(user, "tasks_completed_today", 0) or 0)
        left = max(1, total_tasks - done)

        # Ideal per-task share of the *target* (not the slack), then clamp to remaining
        ideal = target / total_tasks
        # Slight set weighting: second set a bit higher if 2 sets
        current_set = int(task_set or (int(getattr(user, "daily_sets_completed", 0) or 0) + 1))
        if daily_sets >= 2 and current_set >= 2:
            ideal = ideal * 1.08
        else:
            ideal = ideal * 0.95

        # Spread remaining budget across remaining tasks
        share = remaining_budget / left
        commission = min(ideal, share, remaining_budget)

        # Tiny variance so not every task is identical (±8%)
        import random
        commission = commission * random.uniform(0.92, 1.08)
        commission = min(commission, remaining_budget)
        try:
            from services.engagement_service import quality_multiplier
            commission = float(commission) * quality_multiplier(user)
        except Exception:
            pass

        if remaining_budget <= 0:
            return 0.0

        # Weekend mode + product-of-the-day boosts
        try:
            from models.settings import Settings
            from datetime import datetime
            settings = Settings.query.first()
            if settings:
                if datetime.utcnow().weekday() >= 5:  # Sat=5 Sun=6
                    wb = float(getattr(settings, "weekend_bonus_percent", 0) or 0)
                    if wb > 0 and not is_combo:
                        commission = commission * (1.0 + wb / 100.0)
                if not is_combo and product_price:
                    from models.product import Product
                    potd_id = getattr(settings, "potd_product_id", None)
                    slots = int(getattr(settings, "potd_slots_left", 0) or 0)
                    boost = float(getattr(settings, "potd_boost_percent", 0) or 0)
                    # boost applied at assign time when product matches — handled in assign_task
                    pass
        except Exception:
            pass

        # Lucky hour boost (admin settings)
        try:
            from models.settings import Settings
            from datetime import datetime
            s = Settings.query.first()
            start = getattr(s, "lucky_hour_start", None)
            boost_pct = float(getattr(s, "lucky_hour_boost", 0) or 0)
            if start is not None and boost_pct > 0:
                if datetime.utcnow().hour == int(start):
                    commission = float(commission) * (1.0 + boost_pct / 100.0)
        except Exception:
            pass

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
        user.skips_used_today = 0
        user.mystery_opened_today = False
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
                f"You need at least {TaskService._fmt_money(user, min_start)} in your account to start tasks (required for your membership). "
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

        try:
            from services.engagement_service import quality_multiplier as _qm
            _qmul = _qm(user)
        except Exception:
            _qmul = 1.0
        commission = TaskService.calculate_commission(
            user, price, is_combo=False, task_set=current_set
        )

        try:
            diff = (getattr(product, "difficulty", None) or "standard").lower()
            mult = {"easy": 0.85, "standard": 1.0, "challenge": 1.25}.get(diff, 1.0)
            commission = round(float(commission) * mult, 0)
        except Exception:
            pass
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
    def complete_task(task, rating=5, review="", proof_image=None):
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
        if proof_image:
            task.proof_image = proof_image
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

        # Badges + streak (normal tasks)
        if not is_combo:
            try:
                from services.badge_service import award
                award(user.id, "first_task")
                tasks_per_set, daily_sets, total = TaskService._limits(user)
                if int(user.tasks_completed_today or 0) >= total:
                    award(user.id, "full_day")
                from datetime import date, timedelta
                today = date.today()
                last = getattr(user, "last_task_day", None)
                if last != today:
                    if last == today - timedelta(days=1):
                        user.streak_days = int(user.streak_days or 0) + 1
                    else:
                        user.streak_days = 1
                    user.last_task_day = today
                    if int(user.streak_days or 0) >= 3:
                        award(user.id, "streak_3")
                    db.session.commit()
            except Exception as _b:
                print("badge/streak:", _b)


        # XP + quality score
        try:
            from services.engagement_service import add_xp, bump_quality
            if not is_combo:
                add_xp(user, 8 if not is_negative else 3, "task")
                # faster completion proxy: rating 5 bumps quality
                if int(rating or 5) >= 5:
                    bump_quality(user, 0.3)
                else:
                    bump_quality(user, -0.2)
                db.session.commit()
        except Exception as _eng:
            print("engagement:", _eng)

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
        try:
            from services.badge_service import award
            award(user.id, "combo_cleared")
        except Exception:
            pass
        return True

    @staticmethod
    def withdraw_checklist(user):
        """Structured checklist for the withdraw page UI."""
        TaskService.ensure_daily_reset(user)
        tasks_per_set, daily_sets, total = TaskService._limits(user)
        required_sets = min(2, daily_sets)
        sets_done = int(user.daily_sets_completed or 0)
        bal = float(user.available_balance or 0)
        reserve = float(TaskService.WITHDRAW_RESERVE)
        has_pin = bool(getattr(user, "has_withdraw_pin", lambda: False)())
        if not hasattr(user, "has_withdraw_pin"):
            has_pin = bool(getattr(user, "withdraw_pin_hash", None))
        def _m(amount):
            try:
                from helpers.currency import money
                return money(user, amount)
            except Exception:
                return f"UGX {float(amount or 0):,.0f}"

        has_payout = bool(getattr(user, "payout_method", None) and getattr(user, "payout_account_number", None))
        payout_ok = has_payout and bool(getattr(user, "payout_confirmed", False))

        items = [
            {
                "key": "balance",
                "label": "Balance is not negative",
                "ok": bal >= 0,
                "detail": f"Current: {_m(bal)}",
            },
            {
                "key": "negative_day",
                "label": "No combo negative hold today",
                "ok": not bool(getattr(user, "negative_today", False)),
                "detail": "Clear combo hold first" if getattr(user, "negative_today", False) else "Clear",
            },
            {
                "key": "sets",
                "label": f"Complete {required_sets} task set(s) today",
                "ok": sets_done >= required_sets,
                "detail": f"{sets_done} / {required_sets} sets done",
            },
            {
                "key": "reserve",
                "label": f"Keep at least {_m(reserve)} after withdraw",
                "ok": bal > reserve,
                "detail": f"Withdrawable up to {_m(max(0, bal - reserve))}",
            },
            {
                "key": "pin",
                "label": "Withdraw PIN set",
                "ok": has_pin,
                "detail": "Set PIN in Profile" if not has_pin else "PIN ready",
            },
            {
                "key": "payout",
                "label": "Payout method confirmed",
                "ok": payout_ok,
                "detail": (
                    f"{user.payout_method}: {user.payout_account_number}" if payout_ok
                    else ("Awaiting admin confirmation" if has_payout else "Add a payout method below")
                ),
            },
        ]
        all_ok = all(i["ok"] for i in items)
        return {"items": items, "all_ok": all_ok, "sets_done": sets_done, "required_sets": required_sets}

    @staticmethod

    @staticmethod
    def withdrawals_today(user):
        """Count withdrawal requests created today (any non-rejected)."""
        from datetime import datetime
        try:
            from models.withdraw import Withdrawal
        except Exception:
            try:
                from models.withdrawal import Withdrawal
            except Exception:
                return int(bool(getattr(user, "withdrawal_completed_today", False)))
        start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        try:
            q = Withdrawal.query.filter(
                Withdrawal.user_id == user.id,
                Withdrawal.created_at >= start,
            )
            # count pending/processing/approved/paid — not rejected
            rows = q.all()
            n = 0
            for w in rows:
                st = (getattr(w, "status", "") or "").lower()
                if st != "rejected":
                    n += 1
            return n
        except Exception:
            return int(bool(getattr(user, "withdrawal_completed_today", False)))

    def can_withdraw(user):

        """
        Withdraw only when:
        - at least 2 sets completed today (or membership daily_sets if lower)
        - no negative_today
        - available_balance >= 0
        - once per day unless Gold or VIP
        """

        if not (getattr(user, "payout_method", None) and getattr(user, "payout_account_number", None)):
            return False, "Add a payout method on the withdraw page first."
        if not getattr(user, "payout_confirmed", False):
            return False, "Payout method is waiting for admin confirmation."
        TaskService.ensure_daily_reset(user)

        # Daily withdraw caps: default 1 · Gold 2 · VIP 3
        mname = ""
        try:
            mname = (user.membership.name or "").lower() if user.membership else ""
        except Exception:
            mname = ""
        if "vip" in mname:
            max_wd = 3
        elif "gold" in mname:
            max_wd = 2
        else:
            max_wd = 1
        used = TaskService.withdrawals_today(user)
        if used >= max_wd:
            return False, f"Daily withdrawal limit reached ({used}/{max_wd}). Try again tomorrow."
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
                f"You must keep at least {TaskService._fmt_money(user, reserve)} in your wallet to start next day's tasks. "
                f"Current balance {TaskService._fmt_money(user, bal)}.",
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
        try:
            from services.balance_interest import schedule_after_withdraw
            schedule_after_withdraw(user)
        except Exception as e:
            print("schedule interest:", e)

    @staticmethod
    def activity_streak(user):
        """Days in a row with at least one completed task (best-effort)."""
        from datetime import datetime, timedelta, date
        from sqlalchemy import func
        try:
            days = (
                db.session.query(func.date(Task.completed_at))
                .filter(
                    Task.user_id == user.id,
                    Task.status == "completed",
                    Task.completed_at.isnot(None),
                )
                .distinct()
                .all()
            )
            dayset = {d[0] if not isinstance(d, date) else d for d in days}
            # normalize
            norm = set()
            for d in dayset:
                if d is None:
                    continue
                if hasattr(d, "date"):
                    norm.add(d.date())
                else:
                    norm.add(d)
            streak = 0
            cur = date.today()
            # allow today or yesterday to start streak
            if cur not in norm and (cur - timedelta(days=1)) in norm:
                cur = cur - timedelta(days=1)
            while cur in norm:
                streak += 1
                cur = cur - timedelta(days=1)
            return streak
        except Exception:
            return int(getattr(user, "tasks_completed_today", 0) or 0) > 0 and 1 or 0

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


    @staticmethod
    def can_skip(user):
        name = (user.membership.name if user.membership else "").lower()
        if "vip" not in name:
            return False, "Skip is only available for VIP members."
        from models.settings import Settings
        settings = Settings.query.first()
        limit = int(getattr(settings, "vip_skips_per_day", 2) or 2)
        used = int(getattr(user, "skips_used_today", 0) or 0)
        if used >= limit:
            return False, f"Daily skip limit reached ({limit})."
        return True, ""

    @staticmethod
    def skip_current_task(user):
        ok, reason = TaskService.can_skip(user)
        if not ok:
            return False, reason
        task = (
            Task.query.filter_by(user_id=user.id, status="assigned")
            .filter(Task.task_set != 99)
            .first()
        )
        if not task:
            return False, "No active task to skip."
        # Refund hold without commission
        price = float(task.product_price or 0)
        before = float(user.available_balance or 0)
        user.available_balance = before + price
        task.status = "cancelled"
        user.skips_used_today = int(user.skips_used_today or 0) + 1
        from models.wallet_transaction import WalletTransaction
        db.session.add(WalletTransaction(
            user_id=user.id,
            amount=price,
            transaction_type="task_skip_refund",
            description=f"Skipped task – refund hold {task.product_name}",
            balance_before=before,
            balance_after=float(user.available_balance),
        ))
        db.session.commit()
        return True, "Task skipped. Hold refunded."
