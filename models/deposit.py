from datetime import datetime
from extensions import db


class Deposit(db.Model):
    __tablename__ = "deposits"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False
    )

    amount = db.Column(
        db.Float,
        nullable=False
    )

    currency = db.Column(
        db.String(10),
        nullable=False
    )

    payment_method = db.Column(
        db.String(50),
        nullable=False
    )

    provider = db.Column(
        db.String(50)
    )

    wallet_address = db.Column(
        db.String(255)
    )

    transaction_id = db.Column(
        db.String(150)
    )

    proof_image = db.Column(
        db.String(255)
    )

    notes = db.Column(
        db.Text
    )

    status = db.Column(
        db.String(20),
        default="Pending"
    )

    approved_by = db.Column(
        db.Integer,
        db.ForeignKey("users.id")
    )

    approved_at = db.Column(
        db.DateTime
    )

    rejected_reason = db.Column(
        db.Text
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    user = db.relationship(
        "User",
        foreign_keys=[user_id],
        back_populates="deposits"
    )