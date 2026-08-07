from datetime import datetime

from extensions import db


class Task(db.Model):
    __tablename__ = "tasks"

    id = db.Column(db.Integer, primary_key=True)

    # User
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False
    )

    # Product
    product_id = db.Column(
        db.Integer,
        db.ForeignKey("products.id"),
        nullable=False
    )

    # Progress
    task_number = db.Column(
        db.Integer,
        default=1
    )

    task_set = db.Column(
        db.Integer,
        default=1
    )

    # Product snapshot
    product_name = db.Column(
        db.String(200)
    )

    product_image = db.Column(
        db.String(255)
    )

    product_price = db.Column(
        db.Float,
        default=0
    )

    commission = db.Column(
        db.Float,
        default=0
    )

    # Review
    rating = db.Column(
        db.Integer,
        default=5
    )

    proof_image = db.Column(db.String(500), nullable=True)

    review = db.Column(
        db.Text
    )

    # Status
    status = db.Column(
        db.String(30),
        default="assigned"
    )
    # assigned
    # completed
    # cancelled

    completed_at = db.Column(db.DateTime)

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    user = db.relationship(
        "User",
        back_populates="tasks"
    )

    product = db.relationship(
        "Product",
        back_populates="tasks"
    )

    def __repr__(self):
        return f"<Task {self.id}>"