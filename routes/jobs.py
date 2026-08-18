
"""Simple scheduled jobs (call from Render Cron or external ping)."""
import os
from datetime import datetime
from flask import Blueprint, jsonify, request
from extensions import db

jobs_bp = Blueprint("jobs", __name__, url_prefix="/jobs")


def _authorized():
    secret = os.getenv("CRON_SECRET") or os.getenv("SECRET_KEY", "dev-secret-key-12345")
    token = request.headers.get("X-Cron-Token") or request.args.get("token")
    return token and token == secret


@jobs_bp.route("/daily-reset", methods=["POST", "GET"])
def daily_reset():
    if not _authorized():
        return jsonify({"error": "unauthorized"}), 401
    from models.user import User
    from services.task_service import TaskService
    n = 0
    for user in User.query.filter_by(is_admin=False).limit(5000).all():
        try:
            TaskService.ensure_daily_reset(user)
            n += 1
        except Exception as e:
            print("daily reset user", user.id, e)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
    return jsonify({"ok": True, "users_checked": n, "at": datetime.utcnow().isoformat()})


@jobs_bp.route("/ping")
def ping():
    return jsonify({"ok": True, "time": datetime.utcnow().isoformat()})


@jobs_bp.route("/balance-interest", methods=["POST", "GET"])
def job_balance_interest():
    """Run daily interest for all eligible users (Render cron / ping)."""
    from models.user import User
    from services.balance_interest import apply_interest, MIN_UGX
    from extensions import db
    q = User.query.filter(
        User.is_admin.is_(False),
        User.is_blocked.is_(False),
        User.available_balance >= MIN_UGX,
    ).limit(2000)
    ok_n = 0
    for u in q:
        try:
            ok, _, amt = apply_interest(u, commit=True)
            if ok:
                ok_n += 1
        except Exception as e:
            print("interest", u.id, e)
            try:
                db.session.rollback()
            except Exception:
                pass
    return {"credited": ok_n}


@jobs_bp.route("/db-backup", methods=["POST", "GET"])
def db_backup():
    """
    Dump database and force-push a single backup file to GitHub (overwrites previous).
    Env:
      CRON_SECRET / X-Cron-Token — required
      DATABASE_URL — Postgres (uses pg_dump) or SQLite file path in SQLALCHEMY_DATABASE_URI
      BACKUP_GITHUB_TOKEN — PAT with repo contents write
      BACKUP_GITHUB_REPO — owner/repo (e.g. ombasi/taskmill)
      BACKUP_GITHUB_BRANCH — default backup-db
      BACKUP_GITHUB_PATH — default backups/taskmill.sql.gz
    Call every 5 min from cron-job.org or similar:
      GET https://YOUR-APP.onrender.com/jobs/db-backup?token=CRON_SECRET
    """
    if not _authorized():
        return jsonify({"error": "unauthorized"}), 401

    import base64
    import gzip
    import json
    import subprocess
    import tempfile
    from pathlib import Path as P

    token = os.getenv("BACKUP_GITHUB_TOKEN") or os.getenv("GITHUB_TOKEN")
    repo = os.getenv("BACKUP_GITHUB_REPO")  # owner/name
    branch = os.getenv("BACKUP_GITHUB_BRANCH") or "backup-db"
    remote_path = os.getenv("BACKUP_GITHUB_PATH") or "backups/taskmill.sql.gz"

    if not token or not repo:
        return jsonify({
            "error": "missing_config",
            "need": ["BACKUP_GITHUB_TOKEN", "BACKUP_GITHUB_REPO"],
        }), 400

    db_url = os.getenv("DATABASE_URL") or ""
    # Flask config fallback
    try:
        from flask import current_app
        db_url = db_url or current_app.config.get("SQLALCHEMY_DATABASE_URI") or ""
    except Exception:
        pass

    raw = b""
    method = "empty"
    try:
        if db_url.startswith("postgres") or "postgresql" in db_url:
            url = db_url.replace("postgres://", "postgresql://", 1)
            # pg_dump to stdout
            env = os.environ.copy()
            # parse password into env for pg_dump
            proc = subprocess.run(
                ["pg_dump", "--no-owner", "--no-acl", url],
                capture_output=True,
                timeout=120,
            )
            if proc.returncode != 0:
                return jsonify({
                    "error": "pg_dump_failed",
                    "stderr": (proc.stderr or b"")[:500].decode("utf-8", "ignore"),
                }), 500
            raw = proc.stdout
            method = "pg_dump"
        elif db_url.startswith("sqlite") or db_url.endswith(".db"):
            # sqlite:///path
            path = db_url.split("sqlite:///")[-1] if "sqlite" in db_url else db_url
            path = path.split("?")[0]
            raw = P(path).read_bytes()
            method = "sqlite_file"
        else:
            return jsonify({"error": "unsupported_database_url"}), 400
    except FileNotFoundError:
        return jsonify({"error": "pg_dump_not_installed"}), 500
    except Exception as e:
        return jsonify({"error": "dump_failed", "detail": str(e)}), 500

    payload = gzip.compress(raw)
    content_b64 = base64.b64encode(payload).decode("ascii")

    # GitHub Contents API — create or update (overwrite)
    import urllib.request
    api = f"https://api.github.com/repos/{repo}/contents/{remote_path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "taskmill-backup",
    }

    sha = None
    try:
        req = urllib.request.Request(api + f"?ref={branch}", headers=headers)
        with urllib.request.urlopen(req, timeout=30) as resp:
            meta = json.loads(resp.read().decode())
            sha = meta.get("sha")
    except Exception:
        sha = None  # file may not exist yet

    body = {
        "message": f"db backup {datetime.utcnow().isoformat()}Z",
        "content": content_b64,
        "branch": branch,
    }
    if sha:
        body["sha"] = sha

    data = json.dumps(body).encode()
    req = urllib.request.Request(api, data=data, headers={**headers, "Content-Type": "application/json"}, method="PUT")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode())
    except Exception as e:
        err_body = ""
        if hasattr(e, "read"):
            try:
                err_body = e.read().decode()[:400]
            except Exception:
                pass
        return jsonify({"error": "github_upload_failed", "detail": str(e), "body": err_body}), 500

    return jsonify({
        "ok": True,
        "method": method,
        "bytes_raw": len(raw),
        "bytes_gz": len(payload),
        "repo": repo,
        "branch": branch,
        "path": remote_path,
        "commit": (result.get("commit") or {}).get("sha"),
        "at": datetime.utcnow().isoformat() + "Z",
    })
