
from datetime import datetime
from extensions import db

class SuccessStory(db.Model):
    __tablename__ = "success_stories"
    id = db.Column(db.Integer, primary_key=True)
    display_name = db.Column(db.String(80), nullable=False)
    country = db.Column(db.String(80), nullable=True)
    membership_name = db.Column(db.String(40), nullable=True)
    body = db.Column(db.Text, nullable=False)
    approved = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
