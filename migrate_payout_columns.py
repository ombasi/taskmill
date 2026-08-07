
"""Add missing columns/tables. Run: python migrate_payout_columns.py"""
import os
import sqlite3
from pathlib import Path

USER_COLS = [
    ("payout_method", "VARCHAR(100)"),
    ("payout_account_name", "VARCHAR(150)"),
    ("payout_account_number", "VARCHAR(150)"),
    ("payout_provider", "VARCHAR(100)"),
    ("payout_confirmed", "BOOLEAN DEFAULT 0"),
    ("payout_set_at", "DATETIME"),
    ("currency_locked", "BOOLEAN DEFAULT 0"),
    ("last_big_withdraw_at", "DATETIME"),
]
SETTINGS_COLS = [
    ("deposit_match_active", "BOOLEAN DEFAULT 0"),
    ("deposit_match_percent", "FLOAT DEFAULT 0"),
    ("deposit_match_ends_at", "DATETIME"),
    ("deposit_match_message", "VARCHAR(255)"),
    ("whatsapp_number", "VARCHAR(40)"),
    ("status_message", "VARCHAR(255)"),
    ("status_deposits", "VARCHAR(40)"),
    ("status_withdrawals", "VARCHAR(40)"),
    ("status_tasks", "VARCHAR(40)"),
    ("weekend_bonus_percent", "FLOAT DEFAULT 0"),
    ("potd_product_id", "INTEGER"),
    ("potd_boost_percent", "FLOAT DEFAULT 25"),
    ("potd_slots_left", "INTEGER DEFAULT 0"),
    ("withdraw_cooling_minutes", "INTEGER DEFAULT 30"),
    ("withdraw_cooling_threshold", "FLOAT DEFAULT 500000"),
]

def fix_sqlite():
    dbs = list(Path("instance").glob("*.db")) + list(Path(".").glob("*.db"))
    for db in dbs:
        if "venv" in str(db):
            continue
        print("DB", db)
        con = sqlite3.connect(str(db))
        cur = con.cursor()
        cur.execute("PRAGMA table_info(users)")
        existing = {r[1] for r in cur.fetchall()}
        for name, typ in USER_COLS:
            if name not in existing:
                cur.execute(f"ALTER TABLE users ADD COLUMN {name} {typ}")
                print(" + users." + name)
        try:
            cur.execute("PRAGMA table_info(settings)")
            existing = {r[1] for r in cur.fetchall()}
            for name, typ in SETTINGS_COLS:
                if name not in existing:
                    cur.execute(f"ALTER TABLE settings ADD COLUMN {name} {typ}")
                    print(" + settings." + name)
        except Exception as e:
            print("settings", e)
        cur.execute(
            """CREATE TABLE IF NOT EXISTS success_stories (
                id INTEGER PRIMARY KEY,
                display_name VARCHAR(80) NOT NULL,
                country VARCHAR(80),
                membership_name VARCHAR(40),
                body TEXT NOT NULL,
                approved BOOLEAN DEFAULT 0,
                created_at DATETIME
            )"""
        )
        con.commit()
        con.close()

def fix_postgres(url):
    import psycopg2
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    c = psycopg2.connect(url)
    c.autocommit = True
    cur = c.cursor()
    for name, typ in [
        ("currency_locked", "BOOLEAN DEFAULT FALSE"),
        ("last_big_withdraw_at", "TIMESTAMP"),
        ("payout_method", "VARCHAR(100)"),
        ("payout_account_name", "VARCHAR(150)"),
        ("payout_account_number", "VARCHAR(150)"),
        ("payout_provider", "VARCHAR(100)"),
        ("payout_confirmed", "BOOLEAN DEFAULT FALSE"),
        ("payout_set_at", "TIMESTAMP"),
    ]:
        cur.execute(f"ALTER TABLE users ADD COLUMN IF NOT EXISTS {name} {typ}")
    for name, typ in [
        ("deposit_match_active", "BOOLEAN DEFAULT FALSE"),
        ("deposit_match_percent", "DOUBLE PRECISION DEFAULT 0"),
        ("deposit_match_ends_at", "TIMESTAMP"),
        ("deposit_match_message", "VARCHAR(255)"),
        ("whatsapp_number", "VARCHAR(40)"),
        ("status_message", "VARCHAR(255)"),
        ("status_deposits", "VARCHAR(40)"),
        ("status_withdrawals", "VARCHAR(40)"),
        ("status_tasks", "VARCHAR(40)"),
        ("weekend_bonus_percent", "DOUBLE PRECISION DEFAULT 0"),
        ("potd_product_id", "INTEGER"),
        ("potd_boost_percent", "DOUBLE PRECISION DEFAULT 25"),
        ("potd_slots_left", "INTEGER DEFAULT 0"),
        ("withdraw_cooling_minutes", "INTEGER DEFAULT 30"),
        ("withdraw_cooling_threshold", "DOUBLE PRECISION DEFAULT 500000"),
    ]:
        cur.execute(f"ALTER TABLE settings ADD COLUMN IF NOT EXISTS {name} {typ}")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS success_stories (
            id SERIAL PRIMARY KEY,
            display_name VARCHAR(80) NOT NULL,
            country VARCHAR(80),
            membership_name VARCHAR(40),
            body TEXT NOT NULL,
            approved BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP
        )
    """)
    c.close()
    print("postgres ok")

if __name__ == "__main__":
    url = os.environ.get("DATABASE_URL", "")
    if url and "postgres" in url:
        fix_postgres(url)
    else:
        fix_sqlite()
    print("Done")
