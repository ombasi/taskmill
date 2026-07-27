from datetime import datetime

from extensions import db


class Support(db.Model):
    __tablename__ = "support"

    # ==================================================
    # PRIMARY KEY
    # ==================================================

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    # ==================================================
    # WHATSAPP
    # ==================================================

    whatsapp1 = db.Column(
        db.String(100),
        nullable=True
    )

    whatsapp2 = db.Column(
        db.String(100),
        nullable=True
    )

    whatsapp1_enabled = db.Column(
        db.Boolean,
        default=True
    )

    whatsapp2_enabled = db.Column(
        db.Boolean,
        default=True
    )

    # ==================================================
    # TELEGRAM
    # ==================================================

    telegram1 = db.Column(
        db.String(255),
        nullable=True
    )

    telegram2 = db.Column(
        db.String(255),
        nullable=True
    )

    telegram1_enabled = db.Column(
        db.Boolean,
        default=True
    )

    telegram2_enabled = db.Column(
        db.Boolean,
        default=True
    )

    # ==================================================
    # LIVE CHAT
    # ==================================================

    livechat = db.Column(
        db.String(255),
        nullable=True
    )

    livechat_enabled = db.Column(
        db.Boolean,
        default=True
    )

    # ==================================================
    # DATES
    # ==================================================

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    # ==================================================
    # REPRESENTATION
    # ==================================================

    def __repr__(self):
        return "<Support Settings>"