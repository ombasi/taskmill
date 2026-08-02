
from datetime import datetime
from extensions import db


class Voucher(db.Model):
    __tablename__ = "vouchers"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(40), unique=True, nullable=False, index=True)
    # cash | membership | spins
    reward_type = db.Column(db.String(30), default="cash")
    amount = db.Column(db.Float, default=0)
    membership_id = db.Column(db.Integer, db.ForeignKey("memberships.id"), nullable=True)
    spins = db.Column(db.Integer, default=0)
    label = db.Column(db.String(120))
    note = db.Column(db.String(255))

    # assigned user (optional until redeemed; can be pre-assigned)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    status = db.Column(db.String(20), default="active")  # active | redeemed | cancelled
    redeemed_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    redeemed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    membership = db.relationship("Membership", foreign_keys=[membership_id])
