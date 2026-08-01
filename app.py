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
from routes.api import api_bp
from routes.jobs import jobs_bp
from models.payment_setting import PaymentSetting


def create_app():

    app = Flask(__name__)
    app.config.from_object(Config)

    # Optional error tracking — set SENTRY_DSN in env
    try:
        import os
        dsn = os.getenv("SENTRY_DSN")
        if dsn:
            import sentry_sdk
            from sentry_sdk.integrations.flask import FlaskIntegration
            sentry_sdk.init(dsn=dsn, integrations=[FlaskIntegration()], traces_sample_rate=0.1)
            print("Sentry enabled")
    except Exception as e:
        print("Sentry skip:", e)


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
    app.register_blueprint(api_bp)
    app.register_blueprint(jobs_bp)

    # Ensure folders exist (Windows-safe)
    import os
    os.makedirs(app.config.get("UPLOAD_FOLDER", "static/uploads"), exist_ok=True)
    os.makedirs(os.path.join(app.root_path, "instance"), exist_ok=True)

    # Create tables + first-boot seed (no Shell required on Render)
    with app.app_context():
        db.create_all()
        # Safe add-column for existing DBs (SQLite + Postgres)
        try:
            from sqlalchemy import text, inspect
            insp = inspect(db.engine)
            tables = insp.get_table_names()
            if "users" in tables:
                cols = [c["name"] for c in insp.get_columns("users")]
                if "sex" not in cols:
                    db.session.execute(text("ALTER TABLE users ADD COLUMN sex VARCHAR(20)"))
                    db.session.commit()
                if "date_of_birth" not in cols:
                    db.session.execute(text("ALTER TABLE users ADD COLUMN date_of_birth DATE"))
                    db.session.commit()
                if "accepted_terms_at" not in cols:
                    db.session.execute(text("ALTER TABLE users ADD COLUMN accepted_terms_at TIMESTAMP"))
                    db.session.commit()
                if "withdraw_pin_hash" not in cols:
                    db.session.execute(text(
                        "ALTER TABLE users ADD COLUMN withdraw_pin_hash VARCHAR(255)"
                    ))
                    db.session.commit()
                    print("Added users.withdraw_pin_hash")
            # create missing tables (login_history, etc.)
            db.create_all()
        except Exception as e:
            print("schema ensure:", e)
            try:
                db.session.rollback()
            except Exception:
                pass
        # Add columns that create_all will not alter on existing Postgres tables
        try:
            from sqlalchemy import text
            alters = [
                "ALTER TABLE memberships ADD COLUMN IF NOT EXISTS combo_commission_percent FLOAT DEFAULT 5.0",
                "ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS attachment VARCHAR(255)",
                "ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS attachment_name VARCHAR(255)",
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS set2_unlocked BOOLEAN DEFAULT FALSE",
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS must_change_password BOOLEAN DEFAULT FALSE",
            ]
            for sql in alters:
                try:
                    db.session.execute(text(sql))
                except Exception as col_err:
                    # SQLite may not support IF NOT EXISTS the same way
                    try:
                        simple = sql.replace(" IF NOT EXISTS", "")
                        db.session.execute(text(simple))
                    except Exception:
                        pass
            db.session.commit()
        except Exception as e:
            print("Column migrate note:", e)
            db.session.rollback()

        try:
            from models.user import User
            from models.membership import Membership
            need_seed = (
                User.query.filter_by(is_admin=True).first() is None
                or Membership.query.first() is None
            )
            if need_seed:
                print("Baseline data missing — running safe seed...")
                from seed import run_safe_seed
                run_safe_seed()
            else:
                print("Admin + memberships exist — skip auto-seed.")
        except Exception as e:
            print("Auto-seed skipped:", e)
            db.session.rollback()

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