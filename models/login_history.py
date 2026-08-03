from datetime import datetime

from extensions import db


class LoginHistory(db.Model):
    __tablename__ = "login_history"

    # ==================================================
    # PRIMARY KEY
    # ==================================================

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    # ==================================================
    # USER
    # ==================================================

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False
    )

    # ==================================================
    # LOGIN DETAILS
    # ==================================================

    ip_address = db.Column(
        db.String(100),
        nullable=True
    )

    browser = db.Column(
        db.String(255),
        nullable=True
    )

    device = db.Column(
        db.String(255),
        nullable=True
    )

    operating_system = db.Column(
        db.String(255),
        nullable=True
    )

    location = db.Column(
        db.String(255),
        nullable=True
    )

    status = db.Column(
        db.String(20),
        default="Online"
    )
    # Online
    # Offline

    login_time = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    logout_time = db.Column(
        db.DateTime,
        nullable=True
    )

    # ==================================================
    # RELATIONSHIPS
    # ==================================================

    user = db.relationship(
        "User",
        back_populates="login_history"
    )

    # ==================================================
    # HELPERS
    # ==================================================

    @property
    def is_online(self):
        return self.status == "Online"

    @property
    def is_offline(self):
        return self.status == "Offline"

    # ==================================================
    # REPRESENTATION
    # ==================================================

    def __repr__(self):
        return f"<LoginHistory #{self.id}>"