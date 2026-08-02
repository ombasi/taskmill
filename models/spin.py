
from datetime import datetime
from extensions import db


class SpinPrize(db.Model):
    """Admin-configured wheel segments."""
    __tablename__ = "spin_prizes"

    id = db.Column(db.Integer, primary_key=True)
    label = db.Column(db.String(120), nullable=False)
    # cash | membership | voucher | zero
    prize_type = db.Column(db.String(30), nullable=False, default="cash")
    amount = db.Column(db.Float, default=0)  # cash amount
    membership_id = db.Column(db.Integer, db.ForeignKey("memberships.id"), nullable=True)
    voucher_code = db.Column(db.String(80), nullable=True)
    voucher_note = db.Column(db.String(255), nullable=True)
    weight = db.Column(db.Integer, default=10)  # higher = more likely
    color = db.Column(db.String(20), default="#6366f1")
    active = db.Column(db.Boolean, default=True)
    sort_order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    membership = db.relationship("Membership", foreign_keys=[membership_id])


class SpinGrant(db.Model):
    """Spins awarded to a user by admin."""
    __tablename__ = "spin_grants"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    spins_total = db.Column(db.Integer, default=1)
    spins_used = db.Column(db.Integer, default=0)
    # Optional CSV of prize ids allowed for this grant; empty = all active
    allowed_prize_ids = db.Column(db.String(255), nullable=True)
    granted_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    note = db.Column(db.String(255), nullable=True)
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", foreign_keys=[user_id])

    @property
    def remaining(self):
        return max(0, int(self.spins_total or 0) - int(self.spins_used or 0))


class SpinHistory(db.Model):
    __tablename__ = "spin_history"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    prize_id = db.Column(db.Integer, db.ForeignKey("spin_prizes.id"), nullable=True)
    prize_type = db.Column(db.String(30))
    label = db.Column(db.String(120))
    amount = db.Column(db.Float, default=0)
    detail = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
