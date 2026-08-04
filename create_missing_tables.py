
"""Create any missing tables and columns."""
from app import create_app
from extensions import db
from sqlalchemy import text, inspect

app = create_app()
with app.app_context():
    import models.audit_log  # noqa
    import models.user_note  # noqa
    import models.promo  # noqa
    import models.spin  # noqa
    db.create_all()
    insp = inspect(db.engine)
    if "users" in insp.get_table_names():
        cols = {c["name"] for c in insp.get_columns("users")}
        dialect = db.engine.dialect.name
        adds = []
        for name, sql_type in [
            ("totp_secret", "VARCHAR(64)"),
            ("totp_enabled", "BOOLEAN DEFAULT 0" if dialect != "postgresql" else "BOOLEAN DEFAULT FALSE"),
            ("wallet_frozen", "BOOLEAN DEFAULT 0" if dialect != "postgresql" else "BOOLEAN DEFAULT FALSE"),
            ("agent_credit_limit_daily", "FLOAT DEFAULT 500000"),
            ("agent_debit_limit_daily", "FLOAT DEFAULT 500000"),
            ("agent_credit_used_today", "FLOAT DEFAULT 0"),
            ("agent_debit_used_today", "FLOAT DEFAULT 0"),
            ("agent_limits_day", "VARCHAR(10)"),
            ("checklist_done", "BOOLEAN DEFAULT 0" if dialect != "postgresql" else "BOOLEAN DEFAULT FALSE"),
            ("is_agent", "BOOLEAN DEFAULT 0" if dialect != "postgresql" else "BOOLEAN DEFAULT FALSE"),
        ]:
            if name not in cols:
                try:
                    db.session.execute(text(f"ALTER TABLE users ADD COLUMN {name} {sql_type}"))
                    db.session.commit()
                    print("Added users." + name)
                except Exception as e:
                    db.session.rollback()
                    print(name, e)
    if "deposits" in insp.get_table_names():
        cols = {c["name"] for c in insp.get_columns("deposits")}
        for name, sql_type in [("flagged_by_id", "INTEGER"), ("flag_note", "VARCHAR(255)")]:
            if name not in cols:
                try:
                    db.session.execute(text(f"ALTER TABLE deposits ADD COLUMN {name} {sql_type}"))
                    db.session.commit()
                    print("Added deposits." + name)
                except Exception as e:
                    db.session.rollback()
                    print(name, e)
    print("OK — schema ensured")
