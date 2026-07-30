
"""Update membership rates and remove product caps (no data wipe)."""
from app import create_app
from extensions import db
from models.membership import Membership

RATES = {
    "Starter": (5.0, 8.0),
    "Silver": (7.0, 10.0),
    "Gold": (9.0, 12.0),
    "VIP": (12.0, 15.0),
}

app = create_app()
with app.app_context():
    for name, (c, cc) in RATES.items():
        m = Membership.query.filter_by(name=name).first()
        if not m:
            print("Missing", name)
            continue
        m.commission_percent = c
        if hasattr(m, "combo_commission_percent"):
            m.combo_commission_percent = cc
        m.max_product_price = 1000000  # no practical cap
        print(f"{name}: {c}% / combo {cc}%, max_product unrestricted")
    db.session.commit()
    print("Done.")
