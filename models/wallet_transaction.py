from datetime import datetime

from extensions import db


class WalletTransaction(db.Model):
    __tablename__ = "wallet_transactions"

    # ==================================================
    # PRIMARY KEY
    # ==================================================

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    # ==================================================
    # USER
    # ==================================================

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False
    )

    # ==================================================
    # TRANSACTION DETAILS
    # ==================================================

    amount = db.Column(
        db.Numeric(12, 2),
        nullable=False
    )

    transaction_type = db.Column(
        db.String(30),
        nullable=False
    )
    # deposit
    # withdrawal
    # task_commission
    # combo_commission
    # referral_bonus
    # adjustment

    reference = db.Column(
        db.String(100),
        nullable=True
    )

    description = db.Column(
        db.String(255),
        nullable=True
    )

    balance_before = db.Column(
        db.Numeric(12, 2),
        default=0
    )

    balance_after = db.Column(
        db.Numeric(12, 2),
        default=0
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    # ==================================================
    # RELATIONSHIPS
    # ==================================================

    user = db.relationship(
        "User",
        back_populates="wallet_transactions"
    )

    # ==================================================
    # HELPERS
    # ==================================================

    @property
    def is_credit(self):
        return self.amount > 0

    @property
    def is_debit(self):
        return self.amount < 0

    # ==================================================
    # REPRESENTATION
    # ==================================================

    def __repr__(self):
        return (
            f"<WalletTransaction #{self.id}>"
        )