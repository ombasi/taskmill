from datetime import datetime

from extensions import db


class Combo(db.Model):
    __tablename__ = "combos"

    id = db.Column(db.Integer, primary_key=True)

    # User affected by this combo
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False
    )

    user = db.relationship(
        "User",
        foreign_keys=[user_id],
        backref=db.backref(
            "combos",
            lazy=True,
            cascade="all, delete-orphan"
        )
    )

    # Admin who created it
    created_by = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=True
    )

    admin = db.relationship(
        "User",
        foreign_keys=[created_by]
    )

    # Trigger after completing this task number
    trigger_task = db.Column(
        db.Integer,
        nullable=False
    )

    # Penalty amount
    amount = db.Column(
        db.Float,
        nullable=False
    )

    # fixed / percentage
    combo_type = db.Column(
        db.String(20),
        default="fixed"
    )

    # Tasks required after payment
    tasks_required = db.Column(
        db.Integer,
        default=3
    )

    # Pending | Triggered | Completed | Cancelled
    status = db.Column(
        db.String(30),
        default="Pending"
    )

    active = db.Column(
        db.Boolean,
        default=True
    )

    notes = db.Column(
        db.Text
    )

    # Two high-value products that form this combo
    product1_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=True)
    product2_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=True)
    product1 = db.relationship("Product", foreign_keys=[product1_id])
    product2 = db.relationship("Product", foreign_keys=[product2_id])

    # Snapshot names/prices shown to the user
    product1_name = db.Column(db.String(200))
    product2_name = db.Column(db.String(200))
    product1_price = db.Column(db.Float, default=0)
    product2_price = db.Column(db.Float, default=0)
    product1_image = db.Column(db.String(255))
    product2_image = db.Column(db.String(255))

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    triggered_at = db.Column(
        db.DateTime
    )

    completed_at = db.Column(
        db.DateTime
    )

    def __repr__(self):
        return (
            f"<Combo User={self.user_id} "
            f"Trigger={self.trigger_task} "
            f"Status={self.status}>"
        )