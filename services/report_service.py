from datetime import datetime, timedelta

from sqlalchemy import func

from models.user import User
from models.deposit import Deposit
from models.withdrawal import Withdrawal
from models.task import Task
from models.combo_task import ComboTask
from models.wallet_transaction import WalletTransaction


class ReportService:

    @staticmethod
    def user_dashboard(user):

        today = datetime.utcnow().date()

        today_completed = Task.query.filter(

            Task.user_id == user.id,

            Task.completed == True,

            func.date(Task.created_at) == today

        ).count()

        earnings_today = (

            WalletTransaction.query

            .filter(

                WalletTransaction.user_id == user.id,

                func.date(WalletTransaction.created_at) == today

            )

            .with_entities(

                func.sum(WalletTransaction.amount)

            )

            .scalar()

        )

        return {

            "available_balance": user.available_balance,

            "pending_balance": user.pending_balance,

            "combo_balance": user.combo_balance,

            "membership": user.membership.name if user.membership else "",

            "tasks_completed_today": today_completed,

            "earnings_today": float(earnings_today or 0)

        }
class ReportService:

    # =====================================
    # DASHBOARD COUNTS
    # =====================================

    @staticmethod
    def dashboard():

        return {

            "users": User.query.count(),

            "deposits": Deposit.query.count(),

            "withdrawals": Withdrawal.query.count(),

            "tasks": Task.query.count(),

            "combos": ComboTask.query.count()

        }

    # =====================================
    # TOTAL DEPOSITS
    # =====================================

    @staticmethod
    def total_deposits():

        total = (

            Deposit.query

            .filter_by(status="Approved")

            .with_entities(

                func.sum(Deposit.amount)

            )

            .scalar()

        )

        return total or 0

    # =====================================
    # TOTAL WITHDRAWALS
    # =====================================

    @staticmethod
    def total_withdrawals():

        total = (

            Withdrawal.query

            .filter_by(status="Approved")

            .with_entities(

                func.sum(Withdrawal.amount)

            )

            .scalar()

        )

        return total or 0

    # =====================================
    # TOTAL TASK COMMISSION
    # =====================================

    @staticmethod
    def total_commission():

        total = (

            WalletTransaction.query

            .filter(

                WalletTransaction.transaction_type == "Task"

            )

            .with_entities(

                func.sum(

                    WalletTransaction.amount

                )

            )

            .scalar()

        )

        return total or 0

    # =====================================
    # ACTIVE USERS
    # =====================================

    @staticmethod
    def active_users():

        return User.query.filter_by(

            is_active=True

        ).count()

    # =====================================
    # TODAY'S REGISTRATIONS
    # =====================================

    @staticmethod
    def registrations_today():

        today = datetime.utcnow().date()

        return User.query.filter(

            func.date(

                User.created_at

            ) == today

        ).count()

    # =====================================
    # LAST 7 DAYS
    # =====================================

    @staticmethod
    def weekly_registrations():

        data = []

        today = datetime.utcnow().date()

        for i in range(6, -1, -1):

            day = today - timedelta(days=i)

            count = User.query.filter(

                func.date(User.created_at) == day

            ).count()

            data.append({

                "day": day.strftime("%a"),

                "count": count

            })

        return data

    # =====================================
    # WEEKLY EARNINGS
    # =====================================

    @staticmethod
    def weekly_earnings():

        data = []

        today = datetime.utcnow().date()

        for i in range(6, -1, -1):

            day = today - timedelta(days=i)

            amount = (

                WalletTransaction.query

                .filter(

                    func.date(

                        WalletTransaction.created_at

                    ) == day

                )

                .with_entities(

                    func.sum(

                        WalletTransaction.amount

                    )

                )

                .scalar()

            )

            data.append({

                "day": day.strftime("%a"),

                "amount": float(amount or 0)

            })

        return data