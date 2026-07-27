from datetime import datetime

from extensions import db


class Banner(db.Model):
    __tablename__ = "banners"

    # ==================================================
    # PRIMARY KEY
    # ==================================================

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    # ==================================================
    # BANNER DETAILS
    # ==================================================

    title = db.Column(
        db.String(150),
        nullable=False
    )

    image = db.Column(
        db.String(255),
        nullable=False
    )

    link = db.Column(
        db.String(255),
        nullable=True
    )

    active = db.Column(
        db.Boolean,
        default=True
    )

    display_order = db.Column(
        db.Integer,
        default=1
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
        return f"<Banner {self.title}>"