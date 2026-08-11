"""
Combo Engine — single high-value product.

Admin assigns one product + trigger_task number (e.g. 5).
When the user completes that many tasks (today), combo auto-triggers:
  balance -= product price (can go negative)
  one Frozen/Pending task appears on Tasks page
User deposits, submits the product, gets refund + commission.
"""

from datetime import datetime

from extensions import db
from models.combo import Combo
from models.wallet_transaction import WalletTransaction
from models.task import Task
from models.product import Product


class ComboService:

    MAX_DAILY_COMBOS = 1

    @staticmethod
    def apply_trigger(combo):
        """
        Apply combo: debit full product amount, create 1 combo task.
        Used by admin manual trigger AND auto-trigger at task number.
        """
        if not combo or combo.status != "Pending":
            return False, "Combo not pending."

        user = combo.user
        if not user:
            return False, "No user."

        amount = float(combo.amount or combo.product1_price or 0)
        if amount <= 0:
            return False, "Invalid combo amount."

        before = float(user.available_balance or 0)
        user.available_balance = before - amount
        after = float(user.available_balance)

        user.combo_active = True
        user.combo_started_at = datetime.utcnow()
        user.negative_today = after < 0

        combo.status = "Triggered"
        combo.triggered_at = datetime.utcnow()

        fallback_pid = (
            db.session.query(Product.id).order_by(Product.id.asc()).limit(1).scalar()
            or 1
        )
        pname = combo.product1_name or "Combo Product"
        pprice = float(combo.product1_price or amount)
        pimg = combo.product1_image
        pid = combo.product1_id or fallback_pid

        status = "frozen" if after < 0 else "assigned"

        try:
            from services.task_service import TaskService
            commission = TaskService.calculate_commission(
                user, pprice, is_combo=True, task_set=99
            )
        except Exception:
            commission = round(pprice * 0.08, 0)

        task = Task(
            user_id=user.id,
            product_id=pid,
            product_name=f"[COMBO] {pname}",
            product_image=pimg,
            product_price=pprice,
            commission=commission,
            status=status,
            task_number=1,
            task_set=99,
        )
        db.session.add(task)
        db.session.add(
            WalletTransaction(
                user_id=user.id,
                amount=-amount,
                transaction_type="combo_debit",
                description=(
                    f"Combo at task #{combo.trigger_task}: {pname} "
                    f"(UGX {amount:,.0f}). Deposit if negative, then submit."
                ),
                balance_before=before,
                balance_after=after,
            )
        )
        db.session.commit()

        try:
            from services.notification_service import NotificationService
            try:
                from helpers.currency import money as _money
                _amt_s = _money(user, amount)
                _bal_s = _money(user, after)
            except Exception:
                _amt_s = f"UGX {amount:,.0f}"
                _bal_s = f"UGX {after:,.0f}"
            NotificationService.send(
                user,
                "Combo Product Activated",
                f"{pname} ({_amt_s}) was charged. "
                f"Balance: {_bal_s}. "
                + (
                    "Deposit to clear the negative, then open Tasks to submit."
                    if after < 0
                    else "Open Tasks and submit the product."
                ),
            )
        except Exception:
            pass

        return True, f"Triggered. Balance UGX {after:,.0f}"

    @staticmethod
    def check_combo(user):
        """
        Auto-trigger when user's completed tasks TODAY reach trigger_task.
        Example: trigger_task=5 → fires after the 5th product submitted today.
        """
        combo = (
            Combo.query.filter_by(
                user_id=user.id,
                active=True,
                status="Pending",
            )
            .order_by(Combo.trigger_task.asc())
            .first()
        )
        if combo is None:
            return None

        # Product / task number set by admin (daily count)
        done_today = int(user.tasks_completed_today or 0)
        target = int(combo.trigger_task or 0)
        if target <= 0:
            return None
        if done_today < target:
            return None

        ok, _ = ComboService.apply_trigger(combo)
        return combo if ok else None

    @staticmethod
    def get_active_combo(user):
        return (
            Combo.query.filter(
                Combo.user_id == user.id,
                Combo.status.in_(["Triggered", "Pending"]),
            )
            .order_by(Combo.triggered_at.desc().nullslast())
            .first()
        )

    @staticmethod
    def clear_combo(combo):
        user = combo.user
        combo.status = "Completed"
        combo.completed_at = datetime.utcnow()
        if user:
            user.combo_balance = 0
            user.combo_active = False
            user.combo_completed = True
            user.negative_today = float(user.available_balance or 0) < 0
        db.session.commit()

    @staticmethod
    def cancel_combo(combo):
        combo.status = "Cancelled"
        if combo.user:
            combo.user.combo_active = False
            combo.user.combo_completed = False
        db.session.commit()
