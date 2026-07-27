import os

# Project root (folder that contains this file)
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# Ensure instance folder exists (Windows + Linux safe)
INSTANCE_DIR = os.path.join(BASE_DIR, "instance")
os.makedirs(INSTANCE_DIR, exist_ok=True)

# Absolute path to SQLite file — works on Windows and Linux
DEFAULT_DB_PATH = os.path.join(INSTANCE_DIR, "local.db")
# SQLAlchemy needs forward slashes even on Windows
DEFAULT_SQLITE_URI = "sqlite:///" + DEFAULT_DB_PATH.replace("\\", "/")


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-12345")

    # Prefer DATABASE_URL (Postgres on Render etc.), else local SQLite
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", DEFAULT_SQLITE_URI)

    # Render sometimes provides postgres:// — SQLAlchemy wants postgresql://
    if SQLALCHEMY_DATABASE_URI.startswith("postgres://"):
        SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace(
            "postgres://", "postgresql://", 1
        )

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024
