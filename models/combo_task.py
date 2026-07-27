from datetime import datetime, timedelta

from extensions import db


class ComboTask(db.Model):
    __tablename__ = "combo_tasks"

    STATUS_ASSIGNED = "assigned"
    STATUS_WAITING = "waiting_deposit"
    STATUS_READY = "ready"
    STATUS_COMPLETED = "completed"
    STATUS_EXPIRED = "expired"
    STATUS_CANCELLED = "cancelled"

    # ======================================
    # PRIMARY KEY
    # ======================================

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    # ======================================
    # USER
    # ======================================

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False
    )

    # ======================================
    # COMBO DETAILS
    # ======================================

    status = db.Column(
        db.String(30),
        default=STATUS_ASSIGNED
    )

    products_count = db.Column(
        db.Integer,
        default=3
    )

    total_amount = db.Column(
        db.Float,
        default=0
    )

    commission = db.Column(
        db.Float,
        default=0
    )

    required_balance = db.Column(
        db.Float,
        default=0
    )

    current_balance = db.Column(
        db.Float,
        default=0
    )

    deposit_required = db.Column(
        db.Boolean,
        default=False
    )

    # ======================================
    # DATES
    # ======================================

    expires_at = db.Column(
        db.DateTime,
        default=lambda: datetime.utcnow() + timedelta(hours=24)
    )

    completed_at = db.Column(
        db.DateTime
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    # ======================================
    # RELATIONSHIPS
    # ======================================
    # ======================================
    # RELATIONSHIPS
    # ======================================

    user = db.relationship(
        "User",
        back_populates="combo_tasks"
    )

    product_id = db.Column(
        db.Integer,
        db.ForeignKey("products.id"),
        nullable=True
    )

    product = db.relationship(
    "Product",
    lazy="joined"
    )

    # ======================================
    # REPRESENTATION
    # ======================================

    def __repr__(self):
        return f"<ComboTask {self.id}>"