from datetime import datetime
from extensions import db

class PromoCode(db.Model):
    __tablename__ = "promo_codes"
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(40), unique=True, nullable=False, index=True)
    bonus_percent = db.Column(db.Float, default=0.0)
    max_bonus = db.Column(db.Float, default=0.0)
    uses_left = db.Column(db.Integer, default=100)
    active = db.Column(db.Boolean, default=True)
    expires_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class RiskFlag(db.Model):
    __tablename__ = "risk_flags"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    reason = db.Column(db.String(255), nullable=False)
    severity = db.Column(db.String(20), default="medium")
    resolved = db.Column(db.Boolean, default=False)
    created_by = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship("User", foreign_keys=[user_id])
