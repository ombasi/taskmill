
from datetime import datetime, date
from extensions import db


class CheckIn(db.Model):
    __tablename__ = "check_ins"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    day = db.Column(db.Date, nullable=False, index=True)
    reward_xp = db.Column(db.Integer, default=10)
    reward_cash = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint("user_id", "day", name="uq_checkin_user_day"),)


class LeaderboardSeason(db.Model):
    __tablename__ = "leaderboard_seasons"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), default="Season")
    starts_at = db.Column(db.DateTime, nullable=True)
    ends_at = db.Column(db.DateTime, nullable=True)
    prize_note = db.Column(db.String(255), nullable=True)
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class KycDocument(db.Model):
    __tablename__ = "kyc_documents"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    doc_type = db.Column(db.String(40), default="id")  # id | passport | selfie
    file_path = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(20), default="Pending")  # Pending | Approved | Rejected
    note = db.Column(db.String(255), nullable=True)
    reviewed_by = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    reviewed_at = db.Column(db.DateTime, nullable=True)
