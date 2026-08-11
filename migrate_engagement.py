
import os, sqlite3
from pathlib import Path

COLS = [
    ("xp_points", "INTEGER DEFAULT 0"),
    ("user_level", "INTEGER DEFAULT 1"),
    ("quality_score", "FLOAT DEFAULT 50"),
    ("checkin_streak", "INTEGER DEFAULT 0"),
    ("last_checkin", "DATE"),
    ("telegram_chat_id", "VARCHAR(64)"),
    ("whatsapp_number", "VARCHAR(40)"),
    ("kyc_status", "VARCHAR(20) DEFAULT 'None'"),
]

def sqlite():
    for db in list(Path("instance").glob("*.db")) + list(Path(".").glob("*.db")):
        if "venv" in str(db): continue
        con = sqlite3.connect(str(db)); cur = con.cursor()
        cur.execute("PRAGMA table_info(users)")
        have = {r[1] for r in cur.fetchall()}
        for n, t in COLS:
            if n not in have:
                cur.execute(f"ALTER TABLE users ADD COLUMN {n} {t}")
                print("+", n)
        cur.execute("""CREATE TABLE IF NOT EXISTS check_ins (
            id INTEGER PRIMARY KEY, user_id INTEGER, day DATE, reward_xp INTEGER, reward_cash FLOAT, created_at DATETIME
        )""")
        cur.execute("""CREATE TABLE IF NOT EXISTS leaderboard_seasons (
            id INTEGER PRIMARY KEY, title VARCHAR(120), starts_at DATETIME, ends_at DATETIME,
            prize_note VARCHAR(255), active BOOLEAN, created_at DATETIME
        )""")
        cur.execute("""CREATE TABLE IF NOT EXISTS kyc_documents (
            id INTEGER PRIMARY KEY, user_id INTEGER, doc_type VARCHAR(40), file_path VARCHAR(255),
            status VARCHAR(20), note VARCHAR(255), reviewed_by INTEGER, created_at DATETIME, reviewed_at DATETIME
        )""")
        con.commit(); con.close()

def pg(url):
    import psycopg2
    url = url.replace("postgres://", "postgresql://", 1)
    c = psycopg2.connect(url); c.autocommit = True; cur = c.cursor()
    for n, t in COLS:
        typ = "INTEGER" if "INT" in t.upper() else ("DOUBLE PRECISION" if "FLOAT" in t.upper() else ("DATE" if "DATE" in t.upper() else "VARCHAR(64)"))
        if n == "quality_score": typ = "DOUBLE PRECISION"
        if n == "kyc_status": typ = "VARCHAR(20)"
        if n == "whatsapp_number": typ = "VARCHAR(40)"
        if n == "last_checkin": typ = "DATE"
        cur.execute(f"ALTER TABLE users ADD COLUMN IF NOT EXISTS {n} {typ}")
    cur.execute("""CREATE TABLE IF NOT EXISTS check_ins (
        id SERIAL PRIMARY KEY, user_id INTEGER, day DATE, reward_xp INTEGER, reward_cash DOUBLE PRECISION, created_at TIMESTAMP
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS leaderboard_seasons (
        id SERIAL PRIMARY KEY, title VARCHAR(120), starts_at TIMESTAMP, ends_at TIMESTAMP,
        prize_note VARCHAR(255), active BOOLEAN, created_at TIMESTAMP
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS kyc_documents (
        id SERIAL PRIMARY KEY, user_id INTEGER, doc_type VARCHAR(40), file_path VARCHAR(255),
        status VARCHAR(20), note VARCHAR(255), reviewed_by INTEGER, created_at TIMESTAMP, reviewed_at TIMESTAMP
    )""")
    c.close(); print("pg ok")

if __name__ == "__main__":
    u = os.environ.get("DATABASE_URL", "")
    if u and "postgres" in u: pg(u)
    else: sqlite()
    print("Done")
