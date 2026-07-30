
"""Set membership product caps and commission rates (no wipe)."""
from app import create_app
from extensions import db
from models.membership import Membership

DATA = {
    "Starter": dict(commission_percent=5.0, combo_commission_percent=8.0, max_product_price=10000),
    "Silver": dict(commission_percent=7.0, combo_commission_percent=10.0, max_product_price=50000),
    "Gold": dict(commission_percent=9.0, combo_commission_percent=12.0, max_product_price=150000),
    "VIP": dict(commission_percent=12.0, combo_commission_percent=15.0, max_product_price=500000),
}

app = create_app()
with app.app_context():
    for name, vals in DATA.items():
        m = Membership.query.filter_by(name=name).first()
        if not m:
            print("Missing", name)
            continue
        for k, v in vals.items():
            setattr(m, k, v)
        print(name, vals)
    db.session.commit()
    print("Done.")
