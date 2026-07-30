
"""Update membership commission rates (does not wipe data)."""
from app import create_app
from extensions import db
from models.membership import Membership

RATES = {
    "Starter": (1.0, 5.0),
    "Silver": (3.0, 7.0),
    "Gold": (5.0, 9.0),
    "VIP": (7.0, 12.0),
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
        print(f"{name}: {c}% task / {cc}% combo")
    db.session.commit()
    print("Done.")
