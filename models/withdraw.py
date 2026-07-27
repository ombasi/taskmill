from datetime import datetime

from extensions import db


class Withdrawal(db.Model):
    __tablename__ = "withdrawals"

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
    # WITHDRAWAL DETAILS
    # ==================================================

    amount = db.Column(
        db.Numeric(12, 2),
        nullable=False
    )

    payment_method = db.Column(
    db.String(100),
    nullable=False
    )

    account_name = db.Column(
    db.String(150),
    nullable=False
    )

    account_number = db.Column(
    db.String(100),
    nullable=False
    )

    provider = db.Column(
    db.String(100),
    nullable=False
    )

    status = db.Column(
        db.String(20),
        default="Pending"
    )
    # Pending
    # Approved
    # Rejected

    # ==================================================
    # REVIEW
    # ==================================================

    reviewed_by = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=True
    )

    reviewed_at = db.Column(
        db.DateTime,
        nullable=True
    )

    # ==================================================
    # DATES
    # ==================================================

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    # ==================================================
    # RELATIONSHIPS
    # ==================================================

    user = db.relationship(
        "User",
        foreign_keys=[user_id],
        back_populates="withdrawals"
    )

    reviewer = db.relationship(
        "User",
        foreign_keys=[reviewed_by]
    )

    # ==================================================
    # HELPERS
    # ==================================================

    @property
    def is_pending(self):
        return self.status == "Pending"

    @property
    def is_approved(self):
        return self.status == "Approved"

    @property
    def is_rejected(self):
        return self.status == "Rejected"

    # ==================================================
    # REPRESENTATION
    # ==================================================

    def __repr__(self):
        return f"<Withdrawal #{self.id}>"