from datetime import datetime

from extensions import db


class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)

    admin_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False
    )

    action = db.Column(
        db.String(100),
        nullable=False
    )

    module = db.Column(
        db.String(100),
        nullable=False
    )

    target = db.Column(
        db.String(255)
    )

    description = db.Column(
        db.Text
    )

    ip_address = db.Column(
        db.String(100)
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    admin = db.relationship(
        "User",
        foreign_keys=[admin_id]
    )

    def __repr__(self):
        return f"<AuditLog {self.action}>"