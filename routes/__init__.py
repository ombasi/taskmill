from .auth import auth_bp
from .admin import admin_bp
from .dashboard import dashboard_bp
from .profile import profile_bp
from .task import task_bp
from .wallet import wallet_bp
from .combo import combo_bp

__all__ = [
    "auth_bp",
    "admin_bp",
    "dashboard_bp",
    "profile_bp",
    "task_bp",
    "wallet_bp",
    "combo_bp",
]