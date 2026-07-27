from datetime import datetime

from extensions import db


class Partner(db.Model):
    __tablename__ = "partners"

    # ==================================================
    # PRIMARY KEY
    # ==================================================

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    # ==================================================
    # PARTNER DETAILS
    # ==================================================

    name = db.Column(
        db.String(150),
        unique=True,
        nullable=False
    )

    logo = db.Column(
        db.String(255),
        nullable=True
    )

    website = db.Column(
        db.String(255),
        nullable=True
    )

    description = db.Column(
        db.Text,
        nullable=True
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

    products = db.relationship(
        "Product",
        back_populates="partner",
        lazy=True,
        cascade="all, delete-orphan"
    )

    # ==================================================
    # HELPERS
    # ==================================================

    @property
    def product_count(self):
        return len(self.products)

    # ==================================================
    # REPRESENTATION
    # ==================================================

    def __repr__(self):
        return f"<Partner {self.name}>"