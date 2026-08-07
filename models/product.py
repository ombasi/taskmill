from datetime import datetime

from extensions import db


class Product(db.Model):
    __tablename__ = "products"

    # ==================================================
    # PRIMARY KEY
    # ==================================================

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    # ==================================================
    # PRODUCT DETAILS
    # ==================================================

    name = db.Column(
        db.String(150),
        nullable=False
    )

    description = db.Column(
        db.Text,
        nullable=True
    )

    image = db.Column(
        db.String(500),
        nullable=True
    )

    category = db.Column(
        db.String(100),
        nullable=True
    )

    # easy | standard | challenge
    difficulty = db.Column(db.String(20), default="standard")


    partner_id = db.Column(
        db.Integer,
        db.ForeignKey("partners.id"),
        nullable=True
    )

    price = db.Column(
        db.Float,
        nullable=False,
        default=0.0
    )

    commission = db.Column(
        db.Float,
        nullable=False,
        default=0.0
    )

    stock = db.Column(
        db.Integer,
        default=999999
    )

    active = db.Column(
        db.Boolean,
        default=True
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

    # ==================================================
    # RELATIONSHIPS
    # ==================================================

    partner = db.relationship(
        "Partner",
        back_populates="products"
    )

    tasks = db.relationship(
        "Task",
        back_populates="product",
        lazy=True,
        cascade="all, delete-orphan"
    )

    # If ComboTask has a product_id foreign key


    # ==================================================
    # HELPERS
    # ==================================================

    @property
    def in_stock(self):
        return self.stock > 0

    # ==================================================
    # REPRESENTATION
    # ==================================================

    def __repr__(self):
        return f"<Product {self.name}>"
