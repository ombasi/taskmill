from extensions import db


class Membership(db.Model):
    __tablename__ = "memberships"

    # ==================================================
    # PRIMARY KEY
    # ==================================================

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    # ==================================================
    # MEMBERSHIP DETAILS
    # ==================================================

    name = db.Column(
        db.String(50),
        unique=True,
        nullable=False
    )

    price = db.Column(
        db.Float,
        nullable=False,
        default=0.0
    )

    # Number of mandatory tasks the user must complete each day
    daily_tasks = db.Column(
        db.Integer,
        default=2
    )

    # Alias used by older code
    tasks_per_set = db.Column(
        db.Integer,
        default=2
    )

    daily_sets = db.Column(
        db.Integer,
        default=1
    )

    # Commission percentage applied to product price
    commission_percent = db.Column(
        db.Float,
        default=0.5
    )

    # Commission % on combo product reviews
    combo_commission_percent = db.Column(
        db.Float,
        default=5.0
    )

    combo_probability = db.Column(
        db.Integer,
        default=5
    )

    max_product_price = db.Column(
        db.Float,
        default=50000.0
    )

    withdrawal_limit = db.Column(
        db.Float,
        default=100000.0
    )

    minimum_deposit = db.Column(
        db.Float,
        default=0.0
    )

    referral_bonus = db.Column(
        db.Float,
        default=0.0
    )

    active = db.Column(
        db.Boolean,
        default=True
    )

    # ==================================================
    # RELATIONSHIPS
    # ==================================================

    users = db.relationship(
        "User",
        back_populates="membership",
        lazy=True
    )

    # ==================================================
    # HELPERS
    # ==================================================

    @property
    def total_daily_tasks(self):
        return self.daily_tasks

    @property
    def total_sets(self):
        return self.daily_sets

    # ==================================================
    # REPRESENTATION
    # ==================================================

    def __repr__(self):
        return f"<Membership {self.name}>"