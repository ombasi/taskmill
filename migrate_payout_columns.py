
"""Add payout_* columns. Run: python migrate_payout_columns.py"""
import os
import sqlite3
from pathlib import Path

def fix_sqlite():
    dbs = list(Path("instance").glob("*.db")) + list(Path(".").glob("*.db"))
    cols = [
        ("payout_method", "VARCHAR(100)"),
        ("payout_account_name", "VARCHAR(150)"),
        ("payout_account_number", "VARCHAR(150)"),
        ("payout_provider", "VARCHAR(100)"),
        ("payout_confirmed", "BOOLEAN DEFAULT 0"),
        ("payout_set_at", "DATETIME"),
    ]
    for db in dbs:
        if "venv" in str(db):
            continue
        print("DB", db)
        con = sqlite3.connect(str(db))
        cur = con.cursor()
        cur.execute("PRAGMA table_info(users)")
        existing = {r[1] for r in cur.fetchall()}
        for name, typ in cols:
            if name not in existing:
                cur.execute(f"ALTER TABLE users ADD COLUMN {name} {typ}")
                print(" +", name)
        con.commit()
        con.close()

def fix_postgres(url):
    import psycopg2
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    c = psycopg2.connect(url)
    c.autocommit = True
    cur = c.cursor()
    for sql in [
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS payout_method VARCHAR(100)",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS payout_account_name VARCHAR(150)",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS payout_account_number VARCHAR(150)",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS payout_provider VARCHAR(100)",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS payout_confirmed BOOLEAN DEFAULT FALSE",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS payout_set_at TIMESTAMP",
    ]:
        cur.execute(sql)
        print(sql)
    c.close()

if __name__ == "__main__":
    url = os.environ.get("DATABASE_URL", "")
    if url and "postgres" in url:
        fix_postgres(url)
    else:
        fix_sqlite()
    print("Done")
