#!/usr/bin/env python3
"""Dump DATABASE_URL to ./backups/taskmill_YYYYMMDD_HHMM.sql (plain SQL).
Usage:
  set DATABASE_URL=postgresql://...
  python scripts/backup_db.py
Keeps only the latest 7 files in ./backups/
"""
from __future__ import annotations
import os, subprocess, sys
from datetime import datetime
from pathlib import Path

def main():
    url = os.environ.get("DATABASE_URL") or os.environ.get("EXTERNAL_DATABASE_URL")
    if not url:
        print("Set DATABASE_URL first")
        return 1
    url = url.replace("postgres://", "postgresql://", 1)
    out_dir = Path("backups")
    out_dir.mkdir(exist_ok=True)
    stamp = datetime.utcnow().strftime("%Y%m%d_%H%M")
    out = out_dir / f"taskmill_{stamp}.sql"
    cmd = ["pg_dump", f"--dbname={url}", "--no-owner", "--no-acl", "-f", str(out)]
    print("Running:", " ".join(cmd[:2]), "...")
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr or r.stdout)
        return r.returncode
    print("Wrote", out, "size", out.stat().st_size)
    # prune
    files = sorted(out_dir.glob("taskmill_*.sql"), key=lambda p: p.stat().st_mtime, reverse=True)
    for old in files[7:]:
        old.unlink(missing_ok=True)
        print("Removed old", old.name)
    return 0

if __name__ == "__main__":
    sys.exit(main())
