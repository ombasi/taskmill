#!/usr/bin/env python3
"""Membership: Starter price 15k; Silver/Gold/VIP 2x prices; lower commissions; same task counts."""
from app import create_app
from extensions import db
from models.membership import Membership

UPDATES = {
    "Starter": dict(
        price=15000, daily_tasks=32, tasks_per_set=16, daily_sets=2,
        commission_percent=3.5, combo_commission_percent=6.0, combo_probability=3,
        max_product_price=10000, withdrawal_limit=20000, minimum_deposit=15000, referral_bonus=2000,
    ),
    "Silver": dict(
        price=120000, daily_tasks=36, tasks_per_set=18, daily_sets=2,
        commission_percent=4.0, combo_commission_percent=7.0, combo_probability=4,
        max_product_price=50000, withdrawal_limit=70000, minimum_deposit=30000, referral_bonus=5000,
    ),
    "Gold": dict(
        price=300000, daily_tasks=42, tasks_per_set=21, daily_sets=2,
        commission_percent=4.5, combo_commission_percent=8.0, combo_probability=6,
        max_product_price=150000, withdrawal_limit=200000, minimum_deposit=60000, referral_bonus=10000,
    ),
    "VIP": dict(
        price=700000, daily_tasks=50, tasks_per_set=25, daily_sets=2,
        commission_percent=5.0, combo_commission_percent=10.0, combo_probability=10,
        max_product_price=500000, withdrawal_limit=2000000, minimum_deposit=200000, referral_bonus=25000,
    ),
}

def run():
    app = create_app()
    with app.app_context():
        for name, data in UPDATES.items():
            m = Membership.query.filter_by(name=name).first()
            if not m:
                print("missing", name)
                continue
            for k, v in data.items():
                if hasattr(m, k):
                    setattr(m, k, v)
            print("updated", name, "price=", data["price"], "tasks=", data["daily_tasks"], "comm=", data["commission_percent"])
        db.session.commit()
        print("OK — profit caps are in task_service DAILY_PROFIT_TARGETS")

if __name__ == "__main__":
    run()
