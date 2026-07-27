from datetime import datetime
import uuid

from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from extensions import db


class User(db.Model, UserMixin):
    __tablename__ = "users"

    # =====================================================
    # PRIMARY KEY
    # =====================================================

    id = db.Column(db.Integer, primary_key=True)

    # =====================================================
    # ACCOUNT INFORMATION
    # =====================================================

    username = db.Column(
        db.String(80),
        unique=True,
        nullable=False
    )

    full_name = db.Column(
        db.String(150),
        nullable=False
    )

    email = db.Column(
        db.String(120),
        unique=True,
        nullable=False
    )

    phone = db.Column(
        db.String(30),
        unique=True
    )

    password_hash = db.Column(
        db.String(255),
        nullable=False
    )

    # When True, user must set a new password after login (admin reset)
    must_change_password = db.Column(
        db.Boolean,
        default=False
    )

    # =====================================================
    # MEMBERSHIP
    # =====================================================

    membership_id = db.Column(
        db.Integer,
        db.ForeignKey("memberships.id")
    )

    membership = db.relationship(
        "Membership",
        back_populates="users"
    )

    # =====================================================
    # WALLET
    # =====================================================

    available_balance = db.Column(
        db.Float,
        default=0.0
    )

    pending_balance = db.Column(
        db.Float,
        default=0.0
    )

    combo_balance = db.Column(
        db.Float,
        default=0.0
    )

    total_earned = db.Column(
        db.Float,
        default=0.0
    )

    total_withdrawn = db.Column(
        db.Float,
        default=0.0
    )

    # =====================================================
    # TASKS
    # =====================================================

    completed_tasks = db.Column(
        db.Integer,
        default=0
    )

    tasks_completed_today = db.Column(
        db.Integer,
        default=0
    )

    daily_sets_completed = db.Column(
        db.Integer,
        default=0
    )

    # Mandatory daily progress (Taskmill V2 rules)
    mandatory_completed = db.Column(
        db.Boolean,
        default=False
    )

    daily_limit_reached = db.Column(
        db.Boolean,
        default=False
    )

    # Mandatory withdrawal system
    withdrawal_completed_today = db.Column(
        db.Boolean,
        default=False
    )

    must_withdraw_today = db.Column(
        db.Boolean,
        default=False
    )

    # Negative trading day
    negative_today = db.Column(
        db.Boolean,
        default=False
    )

    last_daily_reset = db.Column(
        db.Date
    )

    # Admin must unlock set 2 after set 1 is completed
    set2_unlocked = db.Column(
        db.Boolean,
        default=False
    )

    # =====================================================
    # COMBO
    # =====================================================

    combo_active = db.Column(
        db.Boolean,
        default=False
    )

    combo_completed = db.Column(
        db.Boolean,
        default=False
    )

    combo_started_at = db.Column(
        db.DateTime
    )

    # =====================================================
    # SPIN WHEEL
    # =====================================================

    daily_spins_used = db.Column(
        db.Integer,
        default=0
    )

    # =====================================================
    # REFERRALS
    # =====================================================

    referral_code = db.Column(
        db.String(30),
        unique=True,
        nullable=False,
        default=lambda: uuid.uuid4().hex[:8].upper()
    )

    referred_by_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id")
    )

    referral_count = db.Column(
        db.Integer,
        default=0
    )

    referral_income = db.Column(
        db.Float,
        default=0.0
    )

    referrals = db.relationship(
        "User",
        backref=db.backref(
            "referrer",
            remote_side=[id]
        ),
        lazy=True
    )

    # =====================================================
    # LOCATION
    # =====================================================

    country = db.Column(
        db.String(100),
        default="Uganda"
    )

    currency = db.Column(
        db.String(10),
        default="UGX"
    )

    currency_symbol = db.Column(
        db.String(10),
        default="USh"
    )

    ip_address = db.Column(
        db.String(100)
    )

    # =====================================================
    # ACCOUNT STATUS
    # =====================================================

    is_admin = db.Column(
        db.Boolean,
        default=False
    )

    is_active = db.Column(
        db.Boolean,
        default=True
    )

    is_blocked = db.Column(
        db.Boolean,
        default=False
    )

    email_verified = db.Column(
        db.Boolean,
        default=False
    )

    # =====================================================
    # DATES
    # =====================================================

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    last_login = db.Column(
        db.DateTime
    )

    # =====================================================
    # RELATIONSHIPS
    # =====================================================

    tasks = db.relationship(
        "Task",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy=True
    )

    combo_tasks = db.relationship(
        "ComboTask",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy=True
    )

    deposits = db.relationship(
        "Deposit",
        foreign_keys="Deposit.user_id",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy=True
    )

    withdrawals = db.relationship(
        "Withdrawal",
        foreign_keys="Withdrawal.user_id",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy=True
    )

    wallet_transactions = db.relationship(
        "WalletTransaction",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy=True
    )

    notifications = db.relationship(
        "Notification",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy=True
    )

    login_history = db.relationship(
        "LoginHistory",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy=True
    )

    # =====================================================
    # PASSWORD HELPERS
    # =====================================================

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(
            self.password_hash,
            password
        )

    # =====================================================
    # REPRESENTATION
    # =====================================================

    def __repr__(self):
        return f"<User {self.username}>"