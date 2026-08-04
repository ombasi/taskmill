
"""Add 2FA / agent columns. Run: python fix_2fa_columns.py"""
import os
import sqlite3
from pathlib import Path

# Prefer DATABASE_URL (Render), else local sqlite
db_url = os.environ.get("DATABASE_URL", "")

def fix_sqlite(path):
    path = Path(path)
    if not path.exists():
        print("DB not found:", path)
        return
    conn = sqlite3.connect(str(path))
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(users)")
    cols = {r[1] for r in cur.fetchall()}
    adds = [
        ("is_agent", "BOOLEAN DEFAULT 0"),
        ("totp_secret", "VARCHAR(64)"),
        ("totp_enabled", "BOOLEAN DEFAULT 0"),
        ("wallet_frozen", "BOOLEAN DEFAULT 0"),
        ("agent_credit_limit_daily", "FLOAT DEFAULT 500000"),
        ("agent_debit_limit_daily", "FLOAT DEFAULT 500000"),
        ("agent_credit_used_today", "FLOAT DEFAULT 0"),
        ("agent_debit_used_today", "FLOAT DEFAULT 0"),
        ("agent_limits_day", "VARCHAR(10)"),
        ("checklist_done", "BOOLEAN DEFAULT 0"),
    ]
    for name, typ in adds:
        if name not in cols:
            try:
                cur.execute(f"ALTER TABLE users ADD COLUMN {name} {typ}")
                print("Added", name)
            except Exception as e:
                print(name, e)
    cur.execute("PRAGMA table_info(deposits)")
    dcols = {r[1] for r in cur.fetchall()}
    for name, typ in [("flagged_by_id", "INTEGER"), ("flag_note", "VARCHAR(255)")]:
        if name not in dcols:
            try:
                cur.execute(f"ALTER TABLE deposits ADD COLUMN {name} {typ}")
                print("Added deposits." + name)
            except Exception as e:
                print(name, e)
    # tables
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {r[0] for r in cur.fetchall()}
    if "audit_logs" not in tables:
        cur.execute("""
        CREATE TABLE audit_logs (
            id INTEGER PRIMARY KEY,
            admin_id INTEGER NOT NULL,
            action VARCHAR(100) NOT NULL,
            module VARCHAR(100) NOT NULL,
            target VARCHAR(255),
            description TEXT,
            ip_address VARCHAR(100),
            created_at DATETIME
        )""")
        print("Created audit_logs")
    if "user_notes" not in tables:
        cur.execute("""
        CREATE TABLE user_notes (
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            author_id INTEGER NOT NULL,
            body TEXT NOT NULL,
            created_at DATETIME
        )""")
        print("Created user_notes")
    conn.commit()
    conn.close()
    print("SQLite OK:", path)

def fix_postgres(url):
    try:
        import psycopg2
    except ImportError:
        print("pip install psycopg2-binary")
        return
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    conn = psycopg2.connect(url)
    conn.autocommit = True
    cur = conn.cursor()
    cols = [
        ("is_agent", "BOOLEAN DEFAULT FALSE"),
        ("totp_secret", "VARCHAR(64)"),
        ("totp_enabled", "BOOLEAN DEFAULT FALSE"),
        ("wallet_frozen", "BOOLEAN DEFAULT FALSE"),
        ("agent_credit_limit_daily", "DOUBLE PRECISION DEFAULT 500000"),
        ("agent_debit_limit_daily", "DOUBLE PRECISION DEFAULT 500000"),
        ("agent_credit_used_today", "DOUBLE PRECISION DEFAULT 0"),
        ("agent_debit_used_today", "DOUBLE PRECISION DEFAULT 0"),
        ("agent_limits_day", "VARCHAR(10)"),
        ("checklist_done", "BOOLEAN DEFAULT FALSE"),
    ]
    for name, typ in cols:
        cur.execute(f"ALTER TABLE users ADD COLUMN IF NOT EXISTS {name} {typ}")
        print("Ensured users." + name)
    cur.execute("ALTER TABLE deposits ADD COLUMN IF NOT EXISTS flagged_by_id INTEGER")
    cur.execute("ALTER TABLE deposits ADD COLUMN IF NOT EXISTS flag_note VARCHAR(255)")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS audit_logs (
        id SERIAL PRIMARY KEY,
        admin_id INTEGER NOT NULL,
        action VARCHAR(100) NOT NULL,
        module VARCHAR(100) NOT NULL,
        target VARCHAR(255),
        description TEXT,
        ip_address VARCHAR(100),
        created_at TIMESTAMP
    )""")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS user_notes (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL,
        author_id INTEGER NOT NULL,
        body TEXT NOT NULL,
        created_at TIMESTAMP
    )""")
    conn.close()
    print("Postgres OK")

if __name__ == "__main__":
    if db_url and "postgres" in db_url:
        fix_postgres(db_url)
    else:
        # common local paths
        roots = [
            Path("instance/app.db"),
            Path("instance/taskmill.db"),
            Path("app.db"),
            Path("instance/database.db"),
        ]
        found = False
        for p in roots:
            if p.exists():
                fix_sqlite(p)
                found = True
        if not found:
            # search
            for p in Path(".").rglob("*.db"):
                if "venv" in str(p) or ".git" in str(p):
                    continue
                fix_sqlite(p)
                found = True
                break
        if not found:
            print("No sqlite db found. Set DATABASE_URL or place app.db under instance/")
