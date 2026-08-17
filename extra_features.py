"""Lightweight models for goal jar, shoutouts, missions."""
from datetime import datetime
from extensions import db


class GoalJar(db.Model):
    __tablename__ = "goal_jars"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    title = db.Column(db.String(120), nullable=False, default="My goal")
    target_amount = db.Column(db.Float, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class TeamShoutout(db.Model):
    __tablename__ = "team_shoutouts"
    id = db.Column(db.Integer, primary_key=True)
    agent_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    message = db.Column(db.String(280), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class BrandMission(db.Model):
    __tablename__ = "brand_missions"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), nullable=False)
    category = db.Column(db.String(80), nullable=True)
    active = db.Column(db.Boolean, default=True)
    badge_label = db.Column(db.String(40), default="Mission")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
