"""
Taskmill V2 – Combo Engine

Combo tasks are occasional higher-value product reviews.
They require the user to have enough available balance (or deposit)
and pay a higher commission when completed.
Admin can still assign forced combo penalties via the Combo model.
"""

from datetime import datetime
import random

from extensions import db
from models.combo import Combo
from models.wallet_transaction import WalletTransaction
from models.product import Product
from models.task import Task


class ComboService:

    # Chance (0-100) a normal task completion rolls a combo opportunity
    # Actual chance is also limited by membership.combo_probability
    MAX_DAILY_COMBOS = 1

    @staticmethod
    def check_combo(user):
        """
        Trigger a pending admin-assigned combo when the user reaches
        the configured completed_tasks count.
        """
        combo = (
            Combo.query
            .filter_by(
                user_id=user.id,
                active=True,
                status="Pending"
            )
            .order_by(Combo.trigger_task.asc())
            .first()
        )
        if combo is None:
            return None

        if int(user.completed_tasks or 0) < int(combo.trigger_task or 0):
            return None

        if combo.status != "Pending":
            return None

        if combo.combo_type == "fixed":
            penalty = float(combo.amount)
        else:
            penalty = (
                float(user.available_balance)
                * float(combo.amount)
                / 100.0
            )

        balance_before = float(user.available_balance)
        penalty = min(penalty, balance_before)

        user.available_balance -= penalty
        user.combo_balance = (user.combo_balance or 0) + penalty
        user.combo_active = True
        user.combo_started_at = datetime.utcnow()

        combo.status = "Triggered"
        combo.triggered_at = datetime.utcnow()

        tx = WalletTransaction(
            user_id=user.id,
            transaction_type="combo",
            amount=-penalty,
            description=f"Combo triggered at task {combo.trigger_task}",
            balance_before=balance_before,
            balance_after=float(user.available_balance),
        )
        db.session.add(tx)
        db.session.commit()

        try:
            from services.notification_service import NotificationService
            NotificationService.send(
                user,
                "Combo Order Activated",
                f"UGX {penalty:,.0f} moved to Combo Balance. Complete the required tasks after recharging."
            )
        except Exception:
            pass

        return combo

    @staticmethod
    def get_active_combo(user):
        return (
            Combo.query
            .filter(
                Combo.user_id == user.id,
                Combo.status.in_(["Triggered", "Pending"])
            )
            .order_by(Combo.triggered_at.desc().nullslast())
            .first()
        )

    @staticmethod
    def clear_combo(combo):
        user = combo.user
        combo.status = "Completed"
        combo.completed_at = datetime.utcnow()
        user.combo_balance = 0
        user.combo_active = False
        user.combo_completed = True
        db.session.commit()

    @staticmethod
    def cancel_combo(combo):
        combo.status = "Cancelled"
        if combo.user:
            combo.user.combo_active = False
        db.session.commit()

    @staticmethod
    def maybe_assign_premium_task(user):
        """
        Randomly assign a higher-value product as a 'combo-style' task
        based on membership.combo_probability. Does not freeze the account.
        """
        membership = user.membership
        if not membership:
            return None

        chance = int(getattr(membership, "combo_probability", 5) or 5)
        if random.randint(1, 100) > chance:
            return None

        # Higher-tier products for combo feel
        min_price = float(membership.max_product_price or 50000) * 0.6
        max_price = float(membership.max_product_price or 50000)

        products = (
            Product.query
            .filter(
                Product.active == True,
                Product.stock > 0,
                Product.price >= min_price,
                Product.price <= max_price,
            )
            .order_by(db.func.random())
            .limit(10)
            .all()
        )
        if not products:
            return None

        product = random.choice(products)
        percent = float(getattr(membership, "commission_percent", 15) or 15)
        # Slightly higher commission for combo-style reviews
        commission = round(float(product.price) * (percent / 100.0) * 1.25, 0)

        task = Task(
            user_id=user.id,
            product_id=product.id,
            product_name=f"⭐ {product.name}",
            product_image=product.image,
            product_price=product.price,
            commission=commission,
            status="assigned",
            task_number=(user.tasks_completed_today or 0) + 1,
            task_set=1,
        )
        if product.stock is not None:
            product.stock = max(0, product.stock - 1)

        db.session.add(task)
        db.session.commit()
        return task
