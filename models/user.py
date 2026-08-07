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

    currency_locked = db.Column(db.Boolean, default=False)
    last_big_withdraw_at = db.Column(db.DateTime, nullable=True)
    skips_used_today = db.Column(db.Integer, default=0)
    mystery_opened_today = db.Column(db.Boolean, default=False)


    currency_symbol = db.Column(
        db.String(10),
        default="USh"
    )

    ip_address = db.Column(
        db.String(100)
    )

    # Withdraw security PIN (4-6 digits, hashed)
    # Saved withdrawal destination (user sets once; admin confirms / can change)
    payout_method = db.Column(db.String(100), nullable=True)
    payout_account_name = db.Column(db.String(150), nullable=True)
    payout_account_number = db.Column(db.String(150), nullable=True)
    payout_provider = db.Column(db.String(100), nullable=True)
    payout_confirmed = db.Column(db.Boolean, default=False)
    payout_set_at = db.Column(db.DateTime, nullable=True)

    withdraw_pin_hash = db.Column(
        db.String(255),
        nullable=True
    )

    sex = db.Column(db.String(20), nullable=True)  # Male / Female / Other
    date_of_birth = db.Column(db.Date, nullable=True)
    accepted_terms_at = db.Column(db.DateTime, nullable=True)
    profile_image = db.Column(db.String(255), nullable=True)
    phone_change_month = db.Column(db.String(7), nullable=True)  # YYYY-MM
    phone_change_count = db.Column(db.Integer, default=0)

    # =====================================================
    # ACCOUNT STATUS
    # =====================================================

    is_admin = db.Column(
        db.Boolean,
        default=False
    )

    # Team leader / agent: can manage only own referral downline in admin
    is_agent = db.Column(
        db.Boolean,
        default=False
    )

    # TOTP 2FA (authenticator app) — required for admins once enabled
    totp_secret = db.Column(db.String(64), nullable=True)
    totp_enabled = db.Column(db.Boolean, default=False)

    # Soft freeze wallet (disputes / risk)
    wallet_frozen = db.Column(db.Boolean, default=False)

    # Agent daily limits (UGX); 0 = unlimited
    agent_credit_limit_daily = db.Column(db.Float, default=500000.0)
    agent_debit_limit_daily = db.Column(db.Float, default=500000.0)
    agent_credit_used_today = db.Column(db.Float, default=0.0)
    agent_debit_used_today = db.Column(db.Float, default=0.0)
    agent_limits_day = db.Column(db.String(10), nullable=True)  # YYYY-MM-DD

    # Onboarding checklist
    checklist_done = db.Column(db.Boolean, default=False)

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

    def set_withdraw_pin(self, pin):
        self.withdraw_pin_hash = generate_password_hash(str(pin))

    def check_withdraw_pin(self, pin):
        if not self.withdraw_pin_hash:
            return False
        return check_password_hash(self.withdraw_pin_hash, str(pin))

    def has_withdraw_pin(self):
        return bool(self.withdraw_pin_hash)

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