
"""Add notifications.is_broadcast — run once against DATABASE_URL."""
import os
from app import create_app, _ensure_notification_broadcast_column
from extensions import db

app = create_app()
with app.app_context():
    _ensure_notification_broadcast_column()
    print("OK — column ensured")
