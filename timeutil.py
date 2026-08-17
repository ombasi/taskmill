"""Timezone-aware UTC helpers (replace datetime.utcnow)."""
from datetime import datetime, timezone

def utcnow():
    return datetime.now(timezone.utc)

def utcnow_naive():
    """Naive UTC for DB columns that are timezone-unaware."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
