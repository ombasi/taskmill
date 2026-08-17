
from datetime import datetime
from extensions import db

class InterestLog(db.Model):
    __tablename__ = "interest_logs"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    amount = db.Column(db.Float, default=0)
    balance_before = db.Column(db.Float, default=0)
    rate = db.Column(db.Float, default=0.10)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
