from datetime import datetime

from extensions import db


class Announcement(db.Model):
    __tablename__ = "announcements"

    # ==========================================
    # PRIMARY KEY
    # ==========================================

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    # ==========================================
    # CONTENT
    # ==========================================

    title = db.Column(
        db.String(150),
        nullable=False
    )

    message = db.Column(
        db.Text,
        nullable=False
    )

    # ==========================================
    # STATUS
    # ==========================================

    active = db.Column(
        db.Boolean,
        default=True
    )

    # ==========================================
    # DATES
    # ==========================================

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    # ==========================================
    # REPRESENTATION
    # ==========================================

    def __repr__(self):
        return f"<Announcement {self.title}>"