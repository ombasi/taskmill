from datetime import datetime

from extensions import db


class Settings(db.Model):
    __tablename__ = "settings"

    # ==================================================
    # PRIMARY KEY
    # ==================================================

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    # ==================================================
    # WEBSITE
    # ==================================================

    site_name = db.Column(
        db.String(100),
        nullable=False
    )

    site_url = db.Column(
        db.String(255),
        nullable=True
    )

    logo = db.Column(
        db.String(255),
        nullable=True
    )

    favicon = db.Column(
        db.String(255),
        nullable=True
    )

    maintenance = db.Column(
        db.Boolean,
        default=False
    )

    # ==================================================
    # SYSTEM
    # ==================================================

    registration_enabled = db.Column(
        db.Boolean,
        default=True
    )

    deposits_enabled = db.Column(
        db.Boolean,
        default=True
    )

    withdrawals_enabled = db.Column(
        db.Boolean,
        default=True
    )

    # ==================================================
    # REFERRAL
    # ==================================================

    referral_bonus = db.Column(
        db.Float,
        default=20.0
    )

    referral_activation = db.Column(
        db.Float,
        default=20.0
    )

    # ==================================================
    # TASK ENGINE
    # ==================================================

    daily_task_reset_hour = db.Column(
        db.Integer,
        default=0
    )

    task_delay = db.Column(
        db.Integer,
        default=3
    )

    # ==================================================
    # COMBO ENGINE
    # ==================================================

    combo_probability = db.Column(
        db.Float,
        default=18.0
    )

    combo_penalty = db.Column(
        db.Float,
        default=30.0
    )

    max_daily_combo = db.Column(
        db.Integer,
        default=1
    )

    combo_minimum_amount = db.Column(
        db.Float,
        default=150.0
    )

    # ==================================================
    # LUCKY SPIN
    # ==================================================

    daily_spins = db.Column(
        db.Integer,
        default=1
    )

    max_spin_reward = db.Column(
        db.Float,
        default=100.0
    )

    # ==================================================
    # EMAIL
    # ==================================================

    smtp_host = db.Column(
        db.String(255),
        nullable=True
    )

    smtp_port = db.Column(
        db.Integer,
        nullable=True
    )

    smtp_username = db.Column(
        db.String(255),
        nullable=True
    )

    smtp_password = db.Column(
        db.String(255),
        nullable=True
    )

    sender_email = db.Column(
        db.String(255),
        nullable=True
    )

    # ==================================================
    # SECURITY
    # ==================================================

    minimum_withdrawal = db.Column(
        db.Float,
        default=10.0
    )

    maximum_withdrawal = db.Column(
        db.Float,
        default=100000.0
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
        return "<Settings>"