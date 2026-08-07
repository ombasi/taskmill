
import os, sqlite3
from pathlib import Path

def sqlite():
    for db in list(Path("instance").glob("*.db")) + list(Path(".").glob("*.db")):
        if "venv" in str(db): continue
        con = sqlite3.connect(str(db)); cur = con.cursor()
        def add(table, col, typ):
            cur.execute(f"PRAGMA table_info({table})")
            if col not in {r[1] for r in cur.fetchall()}:
                cur.execute(f"ALTER TABLE {table} ADD COLUMN {col} {typ}")
                print("+", table, col)
        add("products", "difficulty", "VARCHAR(20) DEFAULT 'standard'")
        add("users", "skips_used_today", "INTEGER DEFAULT 0")
        add("users", "mystery_opened_today", "BOOLEAN DEFAULT 0")
        add("tasks", "proof_image", "VARCHAR(500)")
        for c,t in [("vip_skips_per_day","INTEGER DEFAULT 2"),("mystery_box_enabled","BOOLEAN DEFAULT 1"),
                    ("mystery_cash_min","FLOAT DEFAULT 500"),("mystery_cash_max","FLOAT DEFAULT 3000")]:
            try: add("settings", c, t)
            except: pass
        cur.execute("""CREATE TABLE IF NOT EXISTS badges (
            id INTEGER PRIMARY KEY, code VARCHAR(40) UNIQUE, name VARCHAR(80), description VARCHAR(255), icon VARCHAR(40))""")
        cur.execute("""CREATE TABLE IF NOT EXISTS user_badges (
            id INTEGER PRIMARY KEY, user_id INTEGER, badge_id INTEGER, earned_at DATETIME)""")
        con.commit(); con.close()

def pg(url):
    import psycopg2
    url = url.replace("postgres://","postgresql://",1)
    c = psycopg2.connect(url); c.autocommit=True; cur=c.cursor()
    for sql in [
        "ALTER TABLE products ADD COLUMN IF NOT EXISTS difficulty VARCHAR(20) DEFAULT 'standard'",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS skips_used_today INTEGER DEFAULT 0",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS mystery_opened_today BOOLEAN DEFAULT FALSE",
        "ALTER TABLE tasks ADD COLUMN IF NOT EXISTS proof_image VARCHAR(500)",
        "ALTER TABLE settings ADD COLUMN IF NOT EXISTS vip_skips_per_day INTEGER DEFAULT 2",
        "ALTER TABLE settings ADD COLUMN IF NOT EXISTS mystery_box_enabled BOOLEAN DEFAULT TRUE",
        "ALTER TABLE settings ADD COLUMN IF NOT EXISTS mystery_cash_min DOUBLE PRECISION DEFAULT 500",
        "ALTER TABLE settings ADD COLUMN IF NOT EXISTS mystery_cash_max DOUBLE PRECISION DEFAULT 3000",
        """CREATE TABLE IF NOT EXISTS badges (
            id SERIAL PRIMARY KEY, code VARCHAR(40) UNIQUE, name VARCHAR(80), description VARCHAR(255), icon VARCHAR(40))""",
        """CREATE TABLE IF NOT EXISTS user_badges (
            id SERIAL PRIMARY KEY, user_id INTEGER, badge_id INTEGER, earned_at TIMESTAMP)""",
    ]:
        cur.execute(sql); print(sql[:60])
    c.close()

if __name__=="__main__":
    u=os.environ.get("DATABASE_URL","")
    if u and "postgres" in u: pg(u)
    else: sqlite()
    print("Done")
