
"""Create any missing tables (vouchers, spin_*, etc.)."""
from app import create_app
from extensions import db

app = create_app()
with app.app_context():
    import models.voucher  # noqa
    import models.spin  # noqa
    db.create_all()
    print("Tables created / verified.")
