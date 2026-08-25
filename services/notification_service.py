from models.notification import Notification
from extensions import db


class NotificationService:

    @staticmethod
    def send(user, title, message, url="/profile/notifications"):
        """In-app notification + browser/phone tray push when subscribed."""
        notification = Notification(
            user_id=user.id,
            title=title,
            message=message,
            is_read=False,
        )
        db.session.add(notification)
        db.session.commit()

        try:
            from utils.webpush_util import send_web_push_to_user
            uid = user.id if not isinstance(user, int) else user
            send_web_push_to_user(uid, title, message, url=url)
        except Exception as e:
            print("web push:", e)

        return notification

    @staticmethod
    def unread(user):
        return Notification.query.filter_by(
            user_id=user.id,
            is_read=False,
        ).count()

    @staticmethod
    def mark_all_read(user):
        Notification.query.filter_by(
            user_id=user.id,
            is_read=False,
        ).update({"is_read": True})
        db.session.commit()

    @staticmethod
    def broadcast(title, message, users=None):
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
        # push separately so one commit is enough
        try:
            from utils.webpush_util import send_web_push_to_user
            for user in users:
                try:
                    send_web_push_to_user(user.id, title, message, url="/")
                except Exception:
                    pass
        except Exception as e:
            print("broadcast push:", e)
        return count
