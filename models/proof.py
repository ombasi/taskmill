from datetime import datetime
from extensions import db

class WithdrawProof(db.Model):
    __tablename__ = "withdraw_proofs"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    amount_label = db.Column(db.String(80), nullable=False)  # e.g. "UGX ***2,500"
    country = db.Column(db.String(60), nullable=True)
    membership_name = db.Column(db.String(60), nullable=True)
    note = db.Column(db.String(200), nullable=True)
    image_path = db.Column(db.String(255), nullable=True)  # optional blurred shot
    approved = db.Column(db.Boolean, default=False)
    created_by = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
