
"""Simple session-based rate limits (no Redis required)."""
from datetime import datetime, timedelta
from flask import session


def too_soon(key: str, seconds: int = 8) -> bool:
    """Return True if action was done too recently."""
    now = datetime.utcnow()
    stamp = session.get(key)
    if stamp:
        try:
            last = datetime.fromisoformat(stamp)
            if now - last < timedelta(seconds=seconds):
                return True
        except Exception:
            pass
    session[key] = now.isoformat()
    return False
