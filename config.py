import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
INSTANCE_DIR = os.path.join(BASE_DIR, "instance")
os.makedirs(INSTANCE_DIR, exist_ok=True)

DEFAULT_DB_PATH = os.path.join(INSTANCE_DIR, "local.db")
DEFAULT_SQLITE_URI = "sqlite:///" + DEFAULT_DB_PATH.replace("\\", "/")


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-12345")

    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", DEFAULT_SQLITE_URI)

    if SQLALCHEMY_DATABASE_URI.startswith("postgres://"):
        SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace(
            "postgres://", "postgresql://", 1
        )

    # Render Postgres requires SSL from outside / stabilizes external access
    if (
        SQLALCHEMY_DATABASE_URI.startswith("postgresql://")
        and "sslmode=" not in SQLALCHEMY_DATABASE_URI
    ):
        sep = "&" if "?" in SQLALCHEMY_DATABASE_URI else "?"
        SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI + sep + "sslmode=require"

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Avoid "server closed the connection unexpectedly" on idle Render DB
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 280,
        "pool_size": 5,
        "max_overflow": 10,
    }

    UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024
