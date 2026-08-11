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
        try:
            from services.task_service import TaskService
            TaskService.sync_negative_and_combo_tasks(user)
        except Exception:
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

        # Deposit matching campaign
        try:
            from models.settings import Settings
            from datetime import datetime
            settings = Settings.query.first()
            if settings and getattr(settings, "deposit_match_active", False):
                ends = getattr(settings, "deposit_match_ends_at", None)
                if not ends or ends > datetime.utcnow():
                    pct = float(getattr(settings, "deposit_match_percent", 0) or 0)
                    if pct > 0:
                        match_amt = round(amount * (pct / 100.0), 2)
                        if match_amt > 0:
                            user.available_balance = float(user.available_balance or 0) + match_amt
                            try:
                                from models.wallet_transaction import WalletTransaction
                                db.session.add(WalletTransaction(
                                    user_id=user.id,
                                    amount=match_amt,
                                    type="credit",
                                    description=f"Deposit match +{pct:.0f}%",
                                ))
                            except Exception:
                                pass
                            try:
                                from services.notification_service import NotificationService
                                NotificationService.send(
                                    user.id if hasattr(user, 'id') else user,
                                    "Deposit match bonus",
                                    f"You received +{pct:.0f}% match on your deposit.",
                                )
                            except Exception:
                                pass
        except Exception as _dm_e:
            print("deposit_match:", _dm_e)
        try:
            from services.task_service import TaskService
            TaskService.sync_negative_and_combo_tasks(user)
        except Exception:
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

        # Referral bonus: 25% of deposit to referrer when referred user deposits
        try:
            referrer_id = getattr(user, "referred_by_id", None)
            if referrer_id:
                from models.user import User
                referrer = User.query.get(referrer_id)
                if referrer:
                    bonus = round(amount * 0.25, 0)
                    if bonus > 0:
                        rb = float(referrer.available_balance or 0)
                        referrer.available_balance = rb + bonus
                        referrer.total_earned = float(referrer.total_earned or 0) + bonus
                        if hasattr(referrer, "referral_income"):
                            referrer.referral_income = float(referrer.referral_income or 0) + bonus
                        db.session.add(WalletTransaction(
                            user_id=referrer.id,
                            amount=bonus,
                            transaction_type="referral_bonus",
                            description=f"25% referral bonus from {user.username} deposit",
                            balance_before=rb,
                            balance_after=float(referrer.available_balance),
                            reference=getattr(deposit, "transaction_id", None),
                        ))
                        try:
                            from services.notification_service import NotificationService
                            NotificationService.send(
                                referrer,
                                "Referral Deposit Bonus",
                                f"You earned {__import__('helpers.currency', fromlist=['money']).money(referrer, bonus)} (25%) because {user.username} deposited.",
                            )
                            try:
                                from services.badge_service import award
                                award(referrer.id, "first_referral")
                            except Exception:
                                pass
                        except Exception:
                            pass
        except Exception as e:
            print("referral bonus error:", e)

        db.session.commit()

        try:
            from services.notification_service import NotificationService
            NotificationService.send(
                user,
                "Deposit Approved",
                f"Your deposit of {__import__('helpers.currency', fromlist=['money']).money(user, amount)} has been approved and credited."
            )
            try:
                from services.engagement_service import send_outbound_alert, add_xp
                send_outbound_alert(user, "Deposit approved", f"Your deposit was approved and credited.")
                add_xp(user, 20, "deposit")
            except Exception:
                pass
        except Exception:
            pass

        try:
            from services.badge_service import award
            award(user.id, "first_deposit")
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
                f"Your deposit of {__import__('helpers.currency', fromlist=['money']).money(user, amount)} was rejected. Contact support if needed."
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
        if amount < 1000:
            return None  # minimum UGX 1000 (user enters local currency; route converts)

        # Must leave UGX 15,000 for next day's tasks
        reserve = 15000.0
        bal = float(user.available_balance or 0)
        max_withdrawable = bal - reserve
        if max_withdrawable <= 0 or amount > max_withdrawable:
            return None

        # Hold funds immediately
        before = bal
        user.available_balance = bal - amount

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
        if withdrawal.status not in ("Pending", "Processing"):
            return False

        user = withdrawal.user
        withdrawal.status = "Approved"
        withdrawal.reviewed_by = admin.id
        withdrawal.reviewed_at = datetime.utcnow()
        user.total_withdrawn = (user.total_withdrawn or 0) + float(withdrawal.amount)
        db.session.commit()
        try:
            from services.notification_service import NotificationService
            from helpers.currency import money as _money
            _msg = f"Your withdrawal of {_money(user, float(withdrawal.amount))} has been approved."
            NotificationService.send(user, "Withdrawal Approved", _msg)
            try:
                from services.engagement_service import send_outbound_alert
                send_outbound_alert(user, "Withdrawal approved", _msg)
            except Exception:
                pass
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
        if withdrawal.status not in ("Pending", "Processing"):
            return False

        user = withdrawal.user
        amount = float(withdrawal.amount)
        before = float(user.available_balance)
        user.available_balance += amount
        try:
            from services.task_service import TaskService
            TaskService.sync_negative_and_combo_tasks(user)
        except Exception:
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