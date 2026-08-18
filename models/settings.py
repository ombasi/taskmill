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

    # Deposit matching campaign (UGX base amounts; display via money())
    deposit_match_active = db.Column(db.Boolean, default=False)
    deposit_match_percent = db.Column(db.Float, default=0.0)  # e.g. 10 = +10%
    deposit_match_ends_at = db.Column(db.DateTime, nullable=True)
    deposit_match_message = db.Column(db.String(255), nullable=True)

    # Support
    whatsapp_number = db.Column(db.String(40), nullable=True)  # e.g. 2567...

    # Public status page
    status_message = db.Column(db.String(255), default="All systems normal")
    status_deposits = db.Column(db.String(40), default="normal")  # normal|delayed|offline
    status_withdrawals = db.Column(db.String(40), default="normal")
    status_tasks = db.Column(db.String(40), default="normal")

    # Weekend mode
    weekend_bonus_percent = db.Column(db.Float, default=0.0)  # extra % on normal commission Sat-Sun

    # Product of the day
    potd_product_id = db.Column(db.Integer, nullable=True)
    potd_boost_percent = db.Column(db.Float, default=25.0)
    potd_slots_left = db.Column(db.Integer, default=0)

    # Big withdraw cooling-off (minutes, threshold in UGX)
    withdraw_cooling_minutes = db.Column(db.Integer, default=30)
    withdraw_cooling_threshold = db.Column(db.Float, default=500000.0)

    vip_skips_per_day = db.Column(db.Integer, default=2)
    mystery_box_enabled = db.Column(db.Boolean, default=True)
    mystery_cash_min = db.Column(db.Float, default=500.0)
    mystery_cash_max = db.Column(db.Float, default=3000.0)
    telegram_bot_token = db.Column(db.String(120), nullable=True)
    admin_telegram_chat_ids = db.Column(db.Text, nullable=True)  # comma-separated admin chat ids
    kyc_withdraw_threshold = db.Column(db.Float, default=500000.0)





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