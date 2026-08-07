
import os, sqlite3
from pathlib import Path

def sqlite():
    for db in list(Path("instance").glob("*.db"))+list(Path(".").glob("*.db")):
        if "venv" in str(db): continue
        con=sqlite3.connect(str(db)); cur=con.cursor()
        cur.execute("PRAGMA table_info(users)")
        cols={r[1] for r in cur.fetchall()}
        if "session_version" not in cols:
            cur.execute("ALTER TABLE users ADD COLUMN session_version INTEGER DEFAULT 0")
            print("+ session_version")
        con.commit(); con.close()

def pg(url):
    import psycopg2
    url=url.replace("postgres://","postgresql://",1)
    c=psycopg2.connect(url); c.autocommit=True; cur=c.cursor()
    cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS session_version INTEGER DEFAULT 0")
    c.close(); print("pg ok")

if __name__=="__main__":
    u=os.environ.get("DATABASE_URL","")
    if u and "postgres" in u: pg(u)
    else: sqlite()
    print("Done")
