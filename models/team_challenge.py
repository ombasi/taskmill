
from datetime import datetime
from extensions import db

class TeamChallenge(db.Model):
    __tablename__ = "team_challenges"
    id = db.Column(db.Integer, primary_key=True)
    agent_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    title = db.Column(db.String(120), nullable=False)
    target_sets = db.Column(db.Integer, default=10)  # total sets by team
    prize_spins = db.Column(db.Integer, default=1)
    prize_cash = db.Column(db.Float, default=0.0)
    starts_at = db.Column(db.DateTime, default=datetime.utcnow)
    ends_at = db.Column(db.DateTime, nullable=True)
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
