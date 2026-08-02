from models.notification import Notification
from extensions import db


class NotificationService:

    @staticmethod
    def send(user, title, message):
        """Send notification to user"""

        notification = Notification(

            user_id=user.id,

            title=title,

            message=message,

            is_read=False

        )

        db.session.add(notification)
        db.session.commit()

        return notification

    @staticmethod
    def unread(user):
        """Return unread notification count"""

        return Notification.query.filter_by(

            user_id=user.id,

            is_read=False

        ).count()

    @staticmethod
    def mark_all_read(user):

        Notification.query.filter_by(

            user_id=user.id,

            is_read=False

        ).update({

            "is_read": True

        })

        db.session.commit()

    @staticmethod
    def broadcast(title, message, users=None):
        """Send a full-screen broadcast notification to many users."""
        from models.user import User
        if users is None:
            users = User.query.filter_by(is_admin=False, is_active=True).all()
        count = 0
        for user in users:
            db.session.add(Notification(
                user_id=user.id,
                title=title,
                message=message,
                is_read=False,
                is_broadcast=True,
            ))
            count += 1
        db.session.commit()
        return count
