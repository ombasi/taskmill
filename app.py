from flask import Flask, redirect, url_for, request, Response
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
try:
    from routes.engagement import engagement_bp
except Exception as _eng_err:
    engagement_bp = None
    print("engagement module skip:", _eng_err)
try:
    from routes.extras import extras_bp, _ensure_user_extra_cols
except Exception as _ex_err:
    extras_bp = None
    _ensure_user_extra_cols = None
    print("extras module skip:", _ex_err)
from models.payment_setting import PaymentSetting



def _ensure_schema_columns():
    """Add missing columns used by newer features (safe on Postgres + SQLite)."""
    try:
        from utils.payment_methods import _ensure_countries_column
        _ensure_countries_column()
    except Exception as _pm_e:
        print("payment countries col:", _pm_e)
    from sqlalchemy import text, inspect

    def _add(table, name, typ):
        try:
            dialect = db.engine.dialect.name
            if dialect == "postgresql":
                db.session.execute(text(
                    f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {name} {typ}"
                ))
            else:
                insp = inspect(db.engine)
                cols = {c["name"] for c in insp.get_columns(table)}
                if name in cols:
                    return
                db.session.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {typ}"))
            db.session.commit()
            print(f"Added {table}.{name}")
        except Exception as e:
            try:
                db.session.rollback()
            except Exception:
                pass
            print(f"ensure {table}.{name}:", e)

    try:
        insp = inspect(db.engine)
        tables = set(insp.get_table_names())
        dialect = db.engine.dialect.name
        bool_t = "BOOLEAN DEFAULT FALSE" if dialect == "postgresql" else "BOOLEAN DEFAULT 0"
        int_t = "INTEGER DEFAULT 0"
        float_t = "DOUBLE PRECISION DEFAULT 0" if dialect == "postgresql" else "FLOAT DEFAULT 0"

        if "notifications" in tables:
            _add("notifications", "is_broadcast", bool_t)
        if "login_history" in tables:
            _add("login_history", "location", "VARCHAR(255)")

        if "users" in tables:
            user_cols = [
                ("is_agent", bool_t),
                ("session_version", int_t),
                ("xp_points", int_t),
                ("user_level", "INTEGER DEFAULT 1"),
                ("quality_score", "DOUBLE PRECISION DEFAULT 50" if dialect == "postgresql" else "FLOAT DEFAULT 50"),
                ("checkin_streak", int_t),
                ("last_checkin", "DATE"),
                ("telegram_chat_id", "VARCHAR(64)"),
                ("whatsapp_number", "VARCHAR(40)"),
                ("kyc_status", "VARCHAR(20)"),
                ("streak_days", int_t),
                ("last_task_day", "DATE"),
                ("currency_locked", bool_t),
                ("skips_used_today", int_t),
                ("mystery_opened_today", bool_t),
                ("last_big_withdraw_at", "TIMESTAMP" if dialect == "postgresql" else "DATETIME"),
                ("last_seen", "TIMESTAMP" if dialect == "postgresql" else "DATETIME"),
            ]
            for n, typ in user_cols:
                _add("users", n, typ)

        if "settings" in tables:
            for n, typ in [
                ("telegram_bot_token", "VARCHAR(120)"),
                ("kyc_withdraw_threshold", float_t),
                ("admin_telegram_chat_ids", "TEXT"),
                ("interest_enabled", bool_t),
                ("interest_min_ugx", float_t),
                ("interest_rate", float_t),
            ]:
                _add("settings", n, typ)

        # engagement tables
        try:
            db.create_all()
        except Exception as e:
            print("create_all in ensure:", e)
            try:
                db.session.rollback()
            except Exception:
                pass

    except Exception as e:
        print("ensure schema columns:", e)
        try:
            db.session.rollback()
        except Exception:
            pass


def _ensure_notification_broadcast_column():
    """Light ensure for notifications.is_broadcast only (avoid heavy migrate on every poll)."""
    try:
        from sqlalchemy import text, inspect
        dialect = db.engine.dialect.name
        insp = inspect(db.engine)
        if "notifications" not in insp.get_table_names():
            return
        cols = {c["name"] for c in insp.get_columns("notifications")}
        if "is_broadcast" in cols:
            return
        if dialect == "postgresql":
            db.session.execute(text(
                "ALTER TABLE notifications ADD COLUMN IF NOT EXISTS is_broadcast BOOLEAN DEFAULT FALSE"
            ))
        else:
            db.session.execute(text(
                "ALTER TABLE notifications ADD COLUMN is_broadcast BOOLEAN DEFAULT 0"
            ))
        db.session.commit()
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        print("ensure broadcast col:", e)



def _ensure_payout_columns(db):
    """Also ensures currency_locked + campaign settings columns."""
    """Add payout_* columns if missing (SQLite + Postgres). Safe to call every boot."""
    try:
        from sqlalchemy import text, inspect
        insp = inspect(db.engine)
        if "users" not in insp.get_table_names():
            return
        cols = {c["name"] for c in insp.get_columns("users")}
        dialect = db.engine.dialect.name
        specs = [
            ("payout_method", "VARCHAR(100)"),
            ("payout_account_name", "VARCHAR(150)"),
            ("payout_account_number", "VARCHAR(150)"),
            ("payout_provider", "VARCHAR(100)"),
            ("payout_confirmed", "BOOLEAN DEFAULT FALSE" if dialect == "postgresql" else "BOOLEAN DEFAULT 0"),
            ("payout_set_at", "TIMESTAMP" if dialect == "postgresql" else "DATETIME"),
            ("currency_locked", "BOOLEAN DEFAULT FALSE" if dialect == "postgresql" else "BOOLEAN DEFAULT 0"),
        ]
        # settings table extras
        try:
            if "settings" in insp.get_table_names():
                scols = {c["name"] for c in insp.get_columns("settings")}
                sspecs = [
                    ("deposit_match_active", "BOOLEAN DEFAULT FALSE" if dialect == "postgresql" else "BOOLEAN DEFAULT 0"),
                    ("deposit_match_percent", "FLOAT DEFAULT 0"),
                    ("deposit_match_ends_at", "TIMESTAMP" if dialect == "postgresql" else "DATETIME"),
                    ("deposit_match_message", "VARCHAR(255)"),
                    ("whatsapp_number", "VARCHAR(40)"),
                    ("status_message", "VARCHAR(255)"),
                    ("status_deposits", "VARCHAR(40)"),
                    ("status_withdrawals", "VARCHAR(40)"),
                    ("status_tasks", "VARCHAR(40)"),
                ]
                for name, typ in sspecs:
                    if name not in scols:
                        try:
                            if dialect == "postgresql":
                                db.session.execute(text(f"ALTER TABLE settings ADD COLUMN IF NOT EXISTS {name} {typ}"))
                            else:
                                db.session.execute(text(f"ALTER TABLE settings ADD COLUMN {name} {typ}"))
                            db.session.commit()
                            print("Added settings." + name)
                        except Exception as e:
                            db.session.rollback()
                            print("settings col", name, e)
        except Exception as e:
            print("settings ensure", e)
        for name, typ in specs:
            if name in cols:
                continue
            try:
                if dialect == "postgresql":
                    db.session.execute(text(f"ALTER TABLE users ADD COLUMN IF NOT EXISTS {name} {typ}"))
                else:
                    db.session.execute(text(f"ALTER TABLE users ADD COLUMN {name} {typ}"))
                db.session.commit()
                print("Added users." + name)
            except Exception as e:
                db.session.rollback()
                print("ensure payout", name, e)
    except Exception as e:
        print("ensure_payout_columns:", e)


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
        try:
            return db.session.get(User, int(user_id))
        except Exception as e:
            print("load_user:", e)
            try:
                db.session.rollback()
            except Exception:
                pass
            try:
                return db.session.get(User, int(user_id))
            except Exception as e2:
                print("load_user retry:", e2)
                try:
                    db.session.rollback()
                except Exception:
                    pass
                return None

    # Register Blueprints
    
    # Timezone display: users local, admin EAT
    try:
        from utils.timeutil import format_user, format_eat, format_smart, to_user_tz, to_eat

        @app.template_filter("localtime")
        def _filter_localtime(dt, fmt="%d %b %Y · %H:%M"):
            """Format for current viewer: EAT if admin page/user is admin, else user TZ."""
            try:
                from flask_login import current_user
                from flask import request
                is_admin_view = bool(
                    (request.path or "").startswith("/admin")
                    or (request.endpoint or "").startswith("admin.")
                    or (request.endpoint or "").startswith("chat.admin")
                )
                if is_admin_view:
                    return format_eat(dt, fmt)
                u = current_user if getattr(current_user, "is_authenticated", False) else None
                return format_user(dt, u, fmt)
            except Exception:
                return format_eat(dt, fmt) if dt else "—"

        @app.template_filter("eattime")
        def _filter_eattime(dt, fmt="%d %b %Y · %H:%M"):
            return format_eat(dt, fmt)

        @app.template_filter("usertime")
        def _filter_usertime(dt, user=None, fmt="%d %b %Y · %H:%M"):
            return format_user(dt, user, fmt)

        app.jinja_env.globals["format_eat"] = format_eat
        app.jinja_env.globals["format_user"] = format_user
    except Exception as _tz_e:
        print("timezone filters:", _tz_e)

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
        app.register_blueprint(spin_bp)
    if engagement_bp:
        app.register_blueprint(engagement_bp)
    if extras_bp:
        app.register_blueprint(extras_bp)

    # Ensure folders exist (Windows-safe)
    import os
    os.makedirs(app.config.get("UPLOAD_FOLDER", "static/uploads"), exist_ok=True)
    os.makedirs(os.path.join(app.root_path, "instance"), exist_ok=True)

    @app.before_request
    def _maintenance_gate():
        from flask import request as req
        from flask_login import current_user as cu
        # allow static, login, 2fa
        if req.endpoint and (req.endpoint.startswith("static") or req.endpoint in (
            "auth.login", "auth.two_factor", "auth.setup_2fa", "auth.logout"
        )):
            return None
        try:
            from models.settings import Settings
            s = Settings.query.first()
            if s and getattr(s, "maintenance", False):
                if not (cu.is_authenticated and getattr(cu, "is_admin", False)):
                    from flask import render_template
                    return render_template("maintenance.html"), 503
        except Exception:
            pass
        return None



    @app.before_request
    def _touch_last_seen():
        """Throttle presence updates (~every 2 min) for online/offline admin display."""
        from flask import request as req
        from flask_login import current_user as cu
        if not getattr(cu, "is_authenticated", False):
            return None
        if req.endpoint and req.endpoint.startswith("static"):
            return None
        try:
            from datetime import datetime, timedelta
            now = datetime.utcnow()
            prev = getattr(cu, "last_seen", None)
            if prev is not None and (now - prev) < timedelta(minutes=2):
                return None
            cu.last_seen = now
            db.session.commit()
        except Exception:
            try:
                db.session.rollback()
            except Exception:
                pass
        return None

    # Create tables + first-boot seed (no Shell required on Render)
    with app.app_context():
        _ensure_schema_columns()
        try:
            import models.spin  # noqa: F401
            import models.audit_log  # noqa: F401
            import models.user_note  # noqa: F401
            import models.promo  # noqa: F401
        except Exception as e:
            print("model import:", e)
        try:
            db.create_all()
            try:
                from models.engagement import CheckIn, LeaderboardSeason, KycDocument  # noqa
            except Exception:
                pass
        except Exception as e:
            print("create_all:", e)

        try:
            try:
                from utils.payment_methods import ensure_crypto_rows
                ensure_crypto_rows()
            except ImportError:
                from utils.payment_methods import ensure_crypto_payment_methods
                ensure_crypto_payment_methods()
        except Exception as e:
            print("ensure crypto payments:", e)

        # Ensure 2FA / agent columns on users (SQLite + Postgres)
        try:
            from sqlalchemy import text, inspect
            insp = inspect(db.engine)
            if "users" in insp.get_table_names():
                cols = {c["name"] for c in insp.get_columns("users")}
                dialect = db.engine.dialect.name
                bool_def = "BOOLEAN DEFAULT FALSE" if dialect == "postgresql" else "BOOLEAN DEFAULT 0"
                for name, typ in [
                    ("is_agent", bool_def),
                    ("totp_secret", "VARCHAR(64)"),
                    ("totp_enabled", bool_def),
                    ("wallet_frozen", bool_def),
                    ("agent_credit_limit_daily", "FLOAT DEFAULT 500000"),
                    ("agent_debit_limit_daily", "FLOAT DEFAULT 500000"),
                    ("agent_credit_used_today", "FLOAT DEFAULT 0"),
                    ("agent_debit_used_today", "FLOAT DEFAULT 0"),
                    ("agent_limits_day", "VARCHAR(10)"),
                    ("checklist_done", bool_def),
                ]:
                    if name not in cols:
                        try:
                            if dialect == "postgresql":
                                db.session.execute(text(
                                    f"ALTER TABLE users ADD COLUMN IF NOT EXISTS {name} {typ}"
                                ))
                            else:
                                db.session.execute(text(
                                    f"ALTER TABLE users ADD COLUMN {name} {typ}"
                                ))
                            db.session.commit()
                            print("Added users." + name)
                        except Exception as e:
                            db.session.rollback()
                            print("col", name, e)
            if "deposits" in insp.get_table_names():
                cols = {c["name"] for c in insp.get_columns("deposits")}
                for name, typ in [("flagged_by_id", "INTEGER"), ("flag_note", "VARCHAR(255)")]:
                    if name not in cols:
                        try:
                            if dialect == "postgresql":
                                db.session.execute(text(
                                    f"ALTER TABLE deposits ADD COLUMN IF NOT EXISTS {name} {typ}"
                                ))
                            else:
                                db.session.execute(text(f"ALTER TABLE deposits ADD COLUMN {name} {typ}"))
                            db.session.commit()
                            print("Added deposits." + name)
                        except Exception as e:
                            db.session.rollback()
                            print("dep col", name, e)
        except Exception as e:
            print("ensure 2fa columns:", e)
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


    # Manual language override from session
    try:
        from flask import session, g
        if session.get("lang"):
            g.lang = session.get("lang")
    except Exception:
        pass

    # IP-based languages
    try:
        from utils.i18n import init_i18n
        init_i18n(app)
    except Exception as _i18n_e:
        print("i18n init:", _i18n_e)

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
        def safe_url_for(endpoint, **values):
            try:
                from flask import url_for as _uf
                return _uf(endpoint, **values)
            except Exception:
                return "#"
        return dict(money=money, safe_url_for=safe_url_for)

    app.context_processor(inject_csrf)


    @app.context_processor
    def inject_campaign():
        try:
            from models.settings import Settings
            from datetime import datetime
            s = Settings.query.first()
            msg = None
            if s and getattr(s, "deposit_match_active", False):
                ends = getattr(s, "deposit_match_ends_at", None)
                if not ends or ends > datetime.utcnow():
                    pct = getattr(s, "deposit_match_percent", 0) or 0
                    msg = getattr(s, "deposit_match_message", None) or f"Deposit match: +{pct:.0f}% bonus — limited time"
            return {"deposit_match_banner": msg, "site_settings": s}
        except Exception:
            return {"deposit_match_banner": None, "site_settings": None}


    @app.before_request
    def _check_session_version():
        from flask_login import current_user
        from flask import session, redirect, url_for
        try:
            if not current_user.is_authenticated:
                return None
            sv = int(getattr(current_user, "session_version", 0) or 0)
            if "sv" not in session:
                session["sv"] = sv
            elif int(session.get("sv") or 0) != sv:
                from flask_login import logout_user
                logout_user()
                session.clear()
                return redirect(url_for("auth.login"))
        except Exception as e:
            try:
                db.session.rollback()
            except Exception:
                pass
            print("session_version check:", e)
            return None

    
    @app.route("/robots.txt")
    def robots_txt():
        return app.send_static_file("robots.txt")

    @app.route("/sitemap.xml")
    def sitemap_xml():
        pages = ["/login", "/register", "/about", "/faq", "/terms", "/status", "/contact"]
        base = request.url_root.rstrip("/")
        body = ['<?xml version="1.0" encoding="UTF-8"?>',
                '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
        for path in pages:
            body.append(f"  <url><loc>{base}{path}</loc></url>")
        body.append("</urlset>")
        return Response("\n".join(body), mimetype="application/xml")

    return app

app = create_app()

if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=5000)