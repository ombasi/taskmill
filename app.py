from flask import Flask, redirect, url_for
from flask_login import current_user

from config import Config
from extensions import db, migrate, login_manager

# Blueprints
from routes.auth import auth_bp
from routes.dashboard import dashboard_bp
from routes.profile import profile_bp
from routes.task import task_bp
from routes.wallet import wallet_bp
from routes.admin import admin_bp
from models.notification import Notification
from routes.combo import combo_bp
from routes.chat import chat_bp
from models.payment_setting import PaymentSetting


def create_app():

    app = Flask(__name__)
    app.config.from_object(Config)

    # Extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)

    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please log in to continue."

    # User Loader
    from models.user import User

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    # Register Blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(profile_bp)
    app.register_blueprint(task_bp)
    app.register_blueprint(wallet_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(combo_bp)
    app.register_blueprint(chat_bp)

    # Ensure folders exist (Windows-safe)
    import os
    os.makedirs(app.config.get("UPLOAD_FOLDER", "static/uploads"), exist_ok=True)
    os.makedirs(os.path.join(app.root_path, "instance"), exist_ok=True)

    # Create tables
    with app.app_context():
        db.create_all()

    # Home
    @app.route("/")
    def home():

        if current_user.is_authenticated:

            if current_user.is_admin:
                return redirect(url_for("admin.dashboard"))

            return redirect(url_for("dashboard.index"))

        return redirect(url_for("auth.login"))

    # Notifications available in ALL templates

    @app.context_processor
    def inject_media():
        from flask import url_for

        def media(path, default="img/taskmill-logo.png"):
            """Build a static URL for stored image paths."""
            if not path:
                return url_for("static", filename=default)
            path = str(path).replace("\\", "/").lstrip("/")
            if path.startswith("http://") or path.startswith("https://"):
                return path
            if path.startswith("/static/"):
                return path
            if path.startswith("static/"):
                path = path[7:]
            return url_for("static", filename=path)

        return dict(media=media)

    @app.context_processor
    def inject_notifications():

        if current_user.is_authenticated:

            unread_notifications = Notification.query.filter_by(
                user_id=current_user.id,
                is_read=False
            ).count()

        else:

            unread_notifications = 0

        return dict(
            unread_notifications=unread_notifications
        )

    from helpers.currency import money
    from utils.security import inject_csrf

    @app.context_processor
    def inject_helpers():
        return dict(
            money=money
        )

    app.context_processor(inject_csrf)

    return app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True)