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
try:
    from routes.spin import spin_bp
except Exception as _spin_err:
    spin_bp = None
    print("spin module skip:", _spin_err)
from models.payment_setting import PaymentSetting



def _ensure_schema_columns():
    """Add missing columns used by newer features (safe on Postgres + SQLite)."""
    from sqlalchemy import text, inspect
    try:
        insp = inspect(db.engine)
        tables = insp.get_table_names()

        # notifications.is_broadcast
        if "notifications" in tables:
            cols = [c["name"] for c in insp.get_columns("notifications")]
            if "is_broadcast" not in cols:
                dialect = db.engine.dialect.name
                if dialect == "postgresql":
                    db.session.execute(text(
                        "ALTER TABLE notifications ADD COLUMN IF NOT EXISTS is_broadcast BOOLEAN DEFAULT FALSE"
                    ))
                else:
                    db.session.execute(text(
                        "ALTER TABLE notifications ADD COLUMN is_broadcast BOOLEAN DEFAULT 0"
                    ))
                db.session.commit()
                print("Added notifications.is_broadcast")

        # login_history.location
        if "login_history" in tables:
            lcols = [c["name"] for c in insp.get_columns("login_history")]
            if "location" not in lcols:
                db.session.execute(text(
                    "ALTER TABLE login_history ADD COLUMN location VARCHAR(255)"
                ))
                db.session.commit()
                print("Added login_history.location")

        # users.is_agent
        if "users" in tables:
            ucols = [c["name"] for c in insp.get_columns("users")]
            if "is_agent" not in ucols:
                dialect = db.engine.dialect.name
                if dialect == "postgresql":
                    db.session.execute(text(
                        "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_agent BOOLEAN DEFAULT FALSE"
                    ))
                else:
                    db.session.execute(text(
                        "ALTER TABLE users ADD COLUMN is_agent BOOLEAN DEFAULT 0"
                    ))
                db.session.commit()
                print("Added users.is_agent")

    except Exception as e:
        print("ensure schema columns:", e)
        try:
            db.session.rollback()
        except Exception:
            pass


def _ensure_notification_broadcast_column():
    """Backward-compatible alias used by API routes."""
    _ensure_schema_columns()


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
    if spin_bp:
        app.register_blueprint(spin_bp) if spin_bp else None

    # Ensure folders exist (Windows-safe)
    import os
    os.makedirs(app.config.get("UPLOAD_FOLDER", "static/uploads"), exist_ok=True)
    os.makedirs(os.path.join(app.root_path, "instance"), exist_ok=True)

    # Create tables + first-boot seed (no Shell required on Render)
    with app.app_context():
        _ensure_schema_columns()
        try:
            import models.spin  # noqa: F401
        except Exception as e:
            print("model import:", e)
        try:
            db.create_all()
        except Exception as e:
            print("create_all:", e)
        # Safe add-column for existing DBs (SQLite + Postgres)
        try:
            from sqlalchemy import text, inspect
            insp = inspect(db.engine)
            tables = insp.get_table_names()
            if "users" in tables:
                cols = [c["name"] for c in insp.get_columns("users")]
                alters = []
                if "sex" not in cols:
                    db.session.execute(text("ALTER TABLE users ADD COLUMN sex VARCHAR(20)"))
                if "date_of_birth" not in cols:
                    db.session.execute(text("ALTER TABLE users ADD COLUMN date_of_birth DATE"))
                if "profile_image" not in cols:
                    db.session.execute(text("ALTER TABLE users ADD COLUMN profile_image VARCHAR(255)"))
                if "phone_change_month" not in cols:
                    db.session.execute(text("ALTER TABLE users ADD COLUMN phone_change_month VARCHAR(7)"))
                if "phone_change_count" not in cols:
                    db.session.execute(text("ALTER TABLE users ADD COLUMN phone_change_count INTEGER DEFAULT 0"))
                if "accepted_terms_at" not in cols:
                    db.session.execute(text("ALTER TABLE users ADD COLUMN accepted_terms_at TIMESTAMP"))
                if "is_broadcast" not in cols and "notifications" in tables:
                    try:
                        db.session.execute(text("ALTER TABLE notifications ADD COLUMN is_broadcast BOOLEAN DEFAULT 0"))
                        db.session.commit()
                    except Exception:
                        db.session.rollback()
                if "withdraw_pin_hash" not in cols:
                    db.session.execute(text("ALTER TABLE users ADD COLUMN withdraw_pin_hash VARCHAR(255)"))
                db.session.commit()
                db.create_all()
        except Exception as e:
            print("schema ensure:", e)
            try:
                db.session.rollback()
            except Exception:
                pass
        # Auto-seed if no admin
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

        # Ensure membership minimum balances
        try:
            from models.membership import Membership
            mins = {"Starter": 15000, "Silver": 30000, "Gold": 60000, "VIP": 200000}
            for name, val in mins.items():
                m = Membership.query.filter_by(name=name).first()
                if m and float(m.minimum_deposit or 0) != float(val):
                    m.minimum_deposit = val
            db.session.commit()
        except Exception as e:
            print("membership mins:", e)
            try:
                db.session.rollback()
            except Exception:
                pass

            try:
                db.session.rollback()
            except Exception:
                pass


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
        unread_notifications = 0
        try:
            if current_user.is_authenticated:
                _ensure_schema_columns()
                unread_notifications = Notification.query.filter_by(
                    user_id=current_user.id,
                    is_read=False
                ).count()
        except Exception as e:
            print("inject_notifications:", e)
            try:
                db.session.rollback()
            except Exception:
                pass
            unread_notifications = 0
        return dict(unread_notifications=unread_notifications)

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
    app.run(debug=False, host="0.0.0.0", port=5000)