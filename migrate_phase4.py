
import os, sqlite3
from pathlib import Path

def sqlite():
    for db in list(Path("instance").glob("*.db"))+list(Path(".").glob("*.db")):
        if "venv" in str(db): continue
        con=sqlite3.connect(str(db)); cur=con.cursor()
        cur.execute("""CREATE TABLE IF NOT EXISTS badges (
            id INTEGER PRIMARY KEY, code VARCHAR(40) UNIQUE, name VARCHAR(80),
            description VARCHAR(255), icon VARCHAR(40))""")
        cur.execute("""CREATE TABLE IF NOT EXISTS user_badges (
            id INTEGER PRIMARY KEY, user_id INTEGER, badge_id INTEGER, earned_at DATETIME)""")
        cur.execute("""CREATE TABLE IF NOT EXISTS team_challenges (
            id INTEGER PRIMARY KEY, agent_id INTEGER, title VARCHAR(120),
            target_sets INTEGER, prize_spins INTEGER, prize_cash FLOAT,
            starts_at DATETIME, ends_at DATETIME, active BOOLEAN, created_at DATETIME)""")
        con.commit(); con.close(); print("sqlite ok", db)

def pg(url):
    import psycopg2
    url=url.replace("postgres://","postgresql://",1)
    c=psycopg2.connect(url); c.autocommit=True; cur=c.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS badges (
        id SERIAL PRIMARY KEY, code VARCHAR(40) UNIQUE, name VARCHAR(80),
        description VARCHAR(255), icon VARCHAR(40))""")
    cur.execute("""CREATE TABLE IF NOT EXISTS user_badges (
        id SERIAL PRIMARY KEY, user_id INTEGER, badge_id INTEGER, earned_at TIMESTAMP)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS team_challenges (
        id SERIAL PRIMARY KEY, agent_id INTEGER, title VARCHAR(120),
        target_sets INTEGER, prize_spins INTEGER, prize_cash DOUBLE PRECISION,
        starts_at TIMESTAMP, ends_at TIMESTAMP, active BOOLEAN, created_at TIMESTAMP)""")
    c.close(); print("pg ok")

if __name__=="__main__":
    u=os.environ.get("DATABASE_URL","")
    if u and "postgres" in u: pg(u)
    else: sqlite()
