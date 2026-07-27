from datetime import datetime
import os
import uuid

from extensions import db

from models.deposit import Deposit
from models.withdraw import Withdrawal
from models.wallet_transaction import WalletTransaction


class WalletService:

    UPLOAD_FOLDER = "static/uploads/receipts"

    # ============================================================
    # BALANCES
    # ============================================================

    @staticmethod
    def available_balance(user):
        return float(user.available_balance)

    @staticmethod
    def pending_balance(user):
        return float(user.pending_balance)

    @staticmethod
    def combo_balance(user):
        return float(user.combo_balance)

    # ============================================================
    # CREDIT USER
    # ============================================================

    @staticmethod
    def credit(
        user,
        amount,
        description,
        transaction_type="credit",
        reference=None
    ):

        amount = float(amount)

        before = float(user.available_balance)

        user.available_balance += amount
        if float(user.available_balance or 0) >= 0:
            user.negative_today = False

        if transaction_type == "task":
            user.total_earned += amount

        tx = WalletTransaction(

            user_id=user.id,

            amount=amount,

            transaction_type=transaction_type,

            description=description,

            reference=reference,

            balance_before=before,

            balance_after=float(user.available_balance)

        )

        db.session.add(tx)
        db.session.commit()

        return tx

    # ============================================================
    # DEBIT USER
    # ============================================================

    @staticmethod
    def debit(
        user,
        amount,
        description,
        transaction_type="withdraw",
        reference=None
    ):

        amount = float(amount)

        if float(user.available_balance) < amount:
            return False

        before = float(user.available_balance)

        user.available_balance -= amount

        tx = WalletTransaction(

            user_id=user.id,

            amount=-amount,

            transaction_type=transaction_type,

            description=description,

            reference=reference,

            balance_before=before,

            balance_after=float(user.available_balance)

        )

        db.session.add(tx)
        db.session.commit()

        return True

        # ============================================================
    # CREATE DEPOSIT
    # ============================================================

    @staticmethod
    def create_deposit(
        user,
        amount,
        payment_method,
        provider,
        transaction_id=None,
        proof_file=None
    ):

        filename = None

        if proof_file and proof_file.filename:

            os.makedirs(
                WalletService.UPLOAD_FOLDER,
                exist_ok=True
            )

            extension = proof_file.filename.rsplit(".", 1)[1].lower()

            filename = (
                str(uuid.uuid4())
                + "."
                + extension
            )

            proof_file.save(
                os.path.join(
                    WalletService.UPLOAD_FOLDER,
                    filename
                )
            )

        deposit = Deposit(
            user_id=user.id,
            amount=float(amount),
            currency=getattr(user, "currency", "UGX"),
            payment_method=payment_method,
            provider=provider,
            transaction_id=transaction_id,
            proof_image=filename,
            status="Pending"
        )

        db.session.add(deposit)
        db.session.commit()

        return deposit

    # ============================================================
    # APPROVE DEPOSIT
    # ============================================================

    @staticmethod
    def approve_deposit(
        deposit,
        admin
    ):
        if deposit.status != "Pending":
            return False

        user = deposit.user
        amount = float(deposit.amount)

        before = float(user.available_balance)
        user.available_balance += amount
        if float(user.available_balance or 0) >= 0:
            user.negative_today = False

        deposit.status = "Approved"
        # support both column names if present
        if hasattr(deposit, "reviewed_by"):
            deposit.reviewed_by = admin.id
        if hasattr(deposit, "approved_by"):
            deposit.approved_by = admin.id
        if hasattr(deposit, "reviewed_at"):
            deposit.reviewed_at = datetime.utcnow()
        if hasattr(deposit, "approved_at"):
            deposit.approved_at = datetime.utcnow()

        tx = WalletTransaction(
            user_id=user.id,
            amount=amount,
            transaction_type="deposit",
            description="Deposit approved",
            balance_before=before,
            balance_after=float(user.available_balance),
            reference=getattr(deposit, "transaction_reference", None) or getattr(deposit, "transaction_id", None)
        )
        db.session.add(tx)
        db.session.commit()

        try:
            from services.notification_service import NotificationService
            NotificationService.send(
                user,
                "Deposit Approved",
                f"Your deposit of UGX {amount:,.0f} has been approved and credited."
            )
        except Exception:
            pass

        return True

    # ============================================================
    # REJECT DEPOSIT
    # ============================================================

    @staticmethod
    def reject_deposit(
        deposit,
        admin
    ):
        if deposit.status != "Pending":
            return False

        deposit.status = "Rejected"
        if hasattr(deposit, "reviewed_by"):
            deposit.reviewed_by = admin.id
        if hasattr(deposit, "approved_by"):
            deposit.approved_by = admin.id
        if hasattr(deposit, "reviewed_at"):
            deposit.reviewed_at = datetime.utcnow()
        if hasattr(deposit, "approved_at"):
            deposit.approved_at = datetime.utcnow()

        db.session.commit()

        try:
            from services.notification_service import NotificationService
            user = deposit.user
            amount = float(deposit.amount)
            NotificationService.send(
                user,
                "Deposit Rejected",
                f"Your deposit of UGX {amount:,.0f} was rejected. Contact support if needed."
            )
        except Exception:
            pass

        return True

        # ============================================================
    # CREATE WITHDRAWAL
    # ============================================================

    @staticmethod
    def create_withdrawal(
        user,
        amount,
        payment_method,
        account_name,
        account_number,
        provider
    ):

        amount = float(amount)

        if amount <= 0:
            return None

        if float(user.available_balance) < amount:
            return None

        # Hold funds immediately
        before = float(user.available_balance)
        user.available_balance -= amount

        withdrawal = Withdrawal(
            user_id=user.id,
            amount=amount,
            payment_method=payment_method,
            account_name=account_name,
            account_number=account_number,
            provider=provider,
            status="Pending"
        )
        db.session.add(withdrawal)

        from models.wallet_transaction import WalletTransaction
        tx = WalletTransaction(
            user_id=user.id,
            amount=-amount,
            transaction_type="withdrawal_request",
            description="Withdrawal request submitted",
            balance_before=before,
            balance_after=float(user.available_balance),
            reference=None
        )
        db.session.add(tx)

        # Satisfy daily mandatory withdrawal rule
        try:
            from services.task_service import TaskService
            TaskService.mark_withdrawal_done(user)
        except Exception:
            user.withdrawal_completed_today = True
            user.must_withdraw_today = False

        db.session.commit()
        return withdrawal

    # ============================================================
    # APPROVE WITHDRAWAL
    # ============================================================

    @staticmethod
    def approve_withdrawal(
        withdrawal,
        admin
    ):
        """Funds were already held on request – just mark approved."""
        if withdrawal.status != "Pending":
            return False

        user = withdrawal.user
        withdrawal.status = "Approved"
        withdrawal.reviewed_by = admin.id
        withdrawal.reviewed_at = datetime.utcnow()
        user.total_withdrawn = (user.total_withdrawn or 0) + float(withdrawal.amount)
        db.session.commit()
        try:
            from services.notification_service import NotificationService
            NotificationService.send(
                user,
                "Withdrawal Approved",
                f"Your withdrawal of UGX {float(withdrawal.amount):,.0f} has been approved."
            )
        except Exception:
            pass
        return True

    # ============================================================
    # REJECT WITHDRAWAL
    # ============================================================

    @staticmethod
    def reject_withdrawal(
        withdrawal,
        admin
    ):
        """Refund held amount back to available balance."""
        if withdrawal.status != "Pending":
            return False

        user = withdrawal.user
        amount = float(withdrawal.amount)
        before = float(user.available_balance)
        user.available_balance += amount
        if float(user.available_balance or 0) >= 0:
            user.negative_today = False

        from models.wallet_transaction import WalletTransaction
        tx = WalletTransaction(
            user_id=user.id,
            amount=amount,
            transaction_type="withdrawal_refund",
            description="Withdrawal rejected – funds returned",
            balance_before=before,
            balance_after=float(user.available_balance)
        )
        db.session.add(tx)

        withdrawal.status = "Rejected"
        withdrawal.reviewed_by = admin.id
        withdrawal.reviewed_at = datetime.utcnow()
        db.session.commit()
        return True

    # ============================================================
    # HISTORY
    # ============================================================

    @staticmethod
    def history(user):

        return WalletTransaction.query.filter_by(

            user_id=user.id

        ).order_by(

            WalletTransaction.created_at.desc()

        ).all()

    # ============================================================
    # LATEST TRANSACTIONS
    # ============================================================

    @staticmethod
    def latest_transactions(
        user,
        limit=10
    ):

        return WalletTransaction.query.filter_by(

            user_id=user.id

        ).order_by(

            WalletTransaction.created_at.desc()

        ).limit(limit).all()