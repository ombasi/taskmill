from datetime import datetime
from extensions import db


class ChatMessage(db.Model):
    __tablename__ = "chat_messages"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    is_from_admin = db.Column(db.Boolean, default=False)

    admin_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=True,
    )

    message = db.Column(db.Text, nullable=True)

    # Relative path under static/, e.g. uploads/chat/abc.pdf
    attachment = db.Column(db.String(255), nullable=True)
    attachment_name = db.Column(db.String(255), nullable=True)

    is_read = db.Column(db.Boolean, default=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship(
        "User",
        foreign_keys=[user_id],
        backref=db.backref("chat_messages", lazy="dynamic"),
    )
    admin = db.relationship(
        "User",
        foreign_keys=[admin_id],
    )

    def __repr__(self):
        return f"<ChatMessage {self.id} user={self.user_id}>"
