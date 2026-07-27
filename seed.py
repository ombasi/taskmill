from datetime import datetime
import random

from extensions import db

from models.user import User
from models.membership import Membership
from models.partner import Partner
from models.product import Product
from models.settings import Settings
from models.support import Support
from models.banner import Banner


# ==========================================================
# RESET DATABASE
# ==========================================================

def reset_database(force=False):
    """Only wipe DB when force=True (never on normal seed)."""
    if force:
        db.drop_all()
        print("Database DROPPED (force).")
    db.create_all()
    print("Tables ensured (create_all).")


# ==========================================================
# SETTINGS
# ==========================================================

def seed_settings():
    if Settings.query.first():
        print("Settings already exist — skipped.")
        return

    settings = Settings(

        site_name="TaskMill",

        site_url="http://127.0.0.1:5000",

        logo="img/taskmill-logo.png",

        favicon="img/taskmill-logo.png",

        maintenance=False,

        registration_enabled=True,

        deposits_enabled=True,

        withdrawals_enabled=True,

        referral_bonus=5000,

        referral_activation=5000,

        daily_task_reset_hour=0,

        task_delay=3,

        combo_probability=18,

        combo_penalty=30,

        max_daily_combo=1,

        combo_minimum_amount=150000,

        daily_spins=1,

        max_spin_reward=50000,

        minimum_withdrawal=10000,

        maximum_withdrawal=5000000,

        created_at=datetime.utcnow()

    )

    db.session.add(settings)

    db.session.commit()

    print("Settings seeded.")


# ==========================================================
# SUPPORT
# ==========================================================

def seed_support():
    if Support.query.first():
        print("Support already exists — skipped.")
        return


    support = Support(

        whatsapp1="+447548641237",

        whatsapp2="+256700000002",

        telegram1="https://t.me/taskmillsupport",

        telegram2="https://t.me/taskmillvip",

        livechat="https://taskmill.com/chat",

        updated_at=datetime.utcnow()

    )

    db.session.add(support)

    db.session.commit()

    print("Support seeded.")


# ==========================================================
# BANNERS
# ==========================================================

def seed_banners():
    if Banner.query.first():
        print("Banners already exist — skipped.")
        return


    banners = [

        Banner(

            title="Welcome to TaskMill",

            image="banner1.jpg",

            link="#",

            active=True,

            created_at=datetime.utcnow()

        ),

        Banner(

            title="Earn Daily",

            image="banner2.jpg",

            link="#",

            active=True,

            created_at=datetime.utcnow()

        )

    ]

    db.session.add_all(banners)

    db.session.commit()

    print("Banners seeded.")
    # ==========================================================
# MEMBERSHIPS
# ==========================================================

def seed_memberships():
    if Membership.query.first():
        print("Memberships already exist — skipped.")
        return

    # Default memberships (admin-configured production values)
    memberships = [

        Membership(
            name="Starter",
            price=15000,
            daily_tasks=32,
            tasks_per_set=16,
            daily_sets=2,
            commission_percent=0.5,
            combo_commission_percent=5.0,
            combo_probability=3,
            max_product_price=1000,
            withdrawal_limit=20000,
            minimum_deposit=0,
            referral_bonus=2000,
            active=True
        ),
        Membership(
            name="Silver",
            price=60000,
            daily_tasks=36,
            tasks_per_set=18,
            daily_sets=2,
            commission_percent=0.8,
            combo_commission_percent=8.0,
            combo_probability=4,
            max_product_price=20000,
            withdrawal_limit=70000,
            minimum_deposit=60000,
            referral_bonus=5000,
            active=True
        ),
        Membership(
            name="Gold",
            price=150000,
            daily_tasks=42,
            tasks_per_set=21,
            daily_sets=2,
            commission_percent=1.0,
            combo_commission_percent=10.0,
            combo_probability=6,
            max_product_price=40000,
            withdrawal_limit=200000,
            minimum_deposit=150000,
            referral_bonus=10000,
            active=True
        ),
        Membership(
            name="VIP",
            price=350000,
            daily_tasks=50,
            tasks_per_set=25,
            daily_sets=2,
            commission_percent=1.5,
            combo_commission_percent=15.0,
            combo_probability=10,
            max_product_price=300000,
            withdrawal_limit=2000000,
            minimum_deposit=350000,
            referral_bonus=25000,
            active=True
        ),

    ]

    db.session.add_all(memberships)
    db.session.commit()
    # Ensure commission rates even if columns were added late
    rates = {
        "Starter": (0.5, 5.0),
        "Silver": (0.8, 8.0),
        "Gold": (1.0, 10.0),
        "VIP": (1.5, 15.0),
    }
    for name, (c, cc) in rates.items():
        m = Membership.query.filter_by(name=name).first()
        if m:
            m.commission_percent = c
            try:
                m.combo_commission_percent = cc
            except Exception:
                pass
    db.session.commit()
    print("Memberships seeded (UGX defaults).")

    # ==========================================================
# ADMIN
# ==========================================================

def seed_admin():
    existing = User.query.filter(
        (User.username == "admin") | (User.is_admin == True)
    ).first()
    if existing:
        print(f"Admin already exists ({existing.username}) — skipped.")
        return

    starter = Membership.query.filter_by(
        name="Starter"
    ).first()

    admin = User(

        username="admin",

        full_name="TaskMill Administrator",

        email="admin@taskmill.com",

        phone="+256700000000",

        referral_code="ADMIN001",

        membership=starter,

        available_balance=500000,

        combo_balance=500000,

        pending_balance=0,

        total_earned=0,

        total_withdrawn=0,

        country="Uganda",
        currency="UGX",
        currency_symbol="UGX",

        is_admin=True,

        is_active=True,

        email_verified=True,

        created_at=datetime.utcnow()

    )

    admin.set_password("admin123")

    db.session.add(admin)

    db.session.commit()

    print("Admin seeded.")

    # ==========================================================
# PARTNERS
# ==========================================================

def seed_partners():
    if Partner.query.first():
        print("Partners already exist — skipped.")
        return

    partners = [

        Partner(
            name="Jumia",
            logo="partners/amazon.png",
            website="https://www.jumia.ug",
            description="Jumia Uganda Marketplace"
        ),

        Partner(
            name="Jiji",
            logo="partners/amazon.png",
            website="https://jiji.ug",
            description="Jiji Uganda Classifieds"
        ),

        Partner(
            name="Amazon",
            logo="partners/amazon.png",
            website="https://amazon.com",
            description="Amazon Marketplace"
        ),

        Partner(
            name="AliExpress",
            logo="partners/amazon.png",
            website="https://aliexpress.com",
            description="AliExpress"
        ),

    ]

    db.session.add_all(partners)

    db.session.commit()

    print("Partners seeded.")

    # ==========================================================
# PRODUCTS
# ==========================================================

PRODUCT_NAMES = [

    # Phones & accessories
    "Oraimo Power Bank 20000mAh",
    "Tecno Spark Screen Protector",
    "Infinix Hot Soft Case",
    "Type-C Fast Charger Cable",
    "Wireless Earbuds TWS",
    "Bluetooth Neckband Earphones",
    "Phone Holder for Car",
    "Selfie Ring Light Clip",
    "USB Flash Drive 32GB",
    "Memory Card 64GB",

    # Home & kitchen
    "Electric Kettle 1.8L",
    "Non-Stick Frying Pan",
    "Stainless Steel Flask",
    "Rechargeable Emergency Lamp",
    "Extension Cable 4-Way",
    "LED Bulb Pack 3pcs",
    "Table Fan Portable",
    "Clothes Hanger Set",
    "Kitchen Knife Set",
    "Plastic Storage Box",

    # Fashion & beauty
    "Men Canvas Sneakers",
    "Women Handbag",
    "Unisex Sunglasses",
    "Leather Belt",
    "Ankara Fabric Bundle",
    "Hair Dryer Mini",
    "Body Lotion Set",
    "Wrist Watch Analog",
    "Sports Cap",
    "Backpack School Bag",

    # Electronics
    "Bluetooth Speaker Mini",
    "Wireless Mouse",
    "USB Hub 4-Port",
    "HDMI Cable 1.5m",
    "Laptop Cooling Pad",
    "Keyboard USB",
    "Webcam HD",
    "Power Strip Surge Guard",
    "Rechargeable Torch",
    "Smart Watch Band",

    # Lifestyle
    "Yoga Mat",
    "Water Bottle 1L",
    "Umbrella Foldable",
    "Travel Toiletry Bag",
    "Desk Organizer",
    "Wall Clock",
    "Mosquito Repellent Machine",
    "Shoe Rack Stackable",
    "Laundry Basket",
    "Phone Tripod Stand",
]

def seed_products():
    if Product.query.first():
        print("Products already exist — skipped.")
        return

    partners = Partner.query.all()

    if not partners:
        print("No partners found.")
        return

    # Random price ranges (not fixed amounts) aligned to membership tiers
    # Starter max ~1000 | Silver ~20000 | Gold ~40000 | VIP ~300000
    price_ranges = [
        (500, 1000),       # Starter-friendly
        (1000, 3000),
        (3000, 8000),
        (8000, 15000),
        (15000, 20000),    # Silver upper
        (20000, 40000),    # Gold upper
        (40000, 80000),
        (80000, 150000),
        (150000, 250000),
        (250000, 300000),  # VIP upper
    ]
    total_target = 800
    per_band = total_target // len(price_ranges)
    remainder = total_target - (per_band * len(price_ranges))

    desc_templates = [
        "Authentic {item} from {brand}. Brand-new in sealed packaging. Fast delivery across Uganda. Ideal for everyday use and resale.",
        "{item} sourced via {brand}. High quality materials, ready for review. Ships from Kampala warehouse within 24–48 hours.",
        "Popular {item} listed on {brand}. Customer favourite with strong ratings. Perfect product-review assignment for your membership tier.",
        "{brand} official-style listing: {item}. Includes basic warranty support. Suitable for honest product feedback tasks.",
        "Top-selling {item} on {brand}. Clean condition, clear photos available. Assigned based on your membership product limit (UGX {price:,}).",
        "Marketplace pick: {item} ({brand}). Great value at UGX {price:,}. Leave a fair star rating and short review after inspecting details.",
    ]

    products = []
    image_index = 1
    partner_cycle = 0

    for i, (lo, hi) in enumerate(price_ranges):
        count = per_band + (1 if i < remainder else 0)
        for n in range(count):
            partner = partners[partner_cycle % len(partners)]
            partner_cycle += 1
            base_name = random.choice(PRODUCT_NAMES)
            brand = random.choice(["Jumia", "Jiji", partner.name])
            name = f"{brand} {base_name}"
            # Random price inside the band (rounded to nearest 50)
            price = random.randint(lo, hi)
            price = int(round(price / 50.0) * 50)
            price = max(lo, min(hi, price))
            commission = round(price * random.uniform(0.12, 0.20), 0)
            description = random.choice(desc_templates).format(
                item=base_name, brand=brand, price=price
            )

            # Online product image (unique per item, loads in browser)
            seed_key = abs(hash(f"{name}-{price}-{image_index}")) % 100000
            image_url = f"https://picsum.photos/seed/tm{seed_key}/400/400"

            products.append(
                Product(
                    partner_id=partner.id,
                    name=name,
                    description=description,
                    image=image_url,
                    category=random.choice([
                        "Electronics", "Phones", "Home", "Fashion", "Beauty", "Accessories"
                    ]),
                    price=float(price),
                    commission=float(commission),
                    stock=random.randint(80, 500),
                    active=True,
                    created_at=datetime.utcnow(),
                )
            )
            image_index += 1

    db.session.add_all(products)
    db.session.commit()
    print(
        f"{len(products)} Products Seeded."
    )



# ==========================================================
# RUN SEED
# ==========================================================


def seed_payments():
    from models.payment_setting import PaymentSetting
    if PaymentSetting.query.first():
        print("Payment methods already exist.")
        return
    methods = [
        PaymentSetting(
            method="MTN Mobile Money",
            provider="MTN",
            account_name="Taskmill",
            account_number="256700000000",
            instructions="Send money then upload the receipt.",
            logo="mtn.png",
            active=True,
        ),
        PaymentSetting(
            method="Airtel Money",
            provider="Airtel",
            account_name="Taskmill",
            account_number="256700000001",
            instructions="Send money then upload the receipt.",
            logo="airtel.png",
            active=True,
        ),
        PaymentSetting(
            method="Bank Transfer",
            provider="Bank",
            account_name="Taskmill Ltd",
            account_number="1234567890",
            instructions="Use your username as reference.",
            logo="bank.jpg",
            active=True,
        ),
    ]
    db.session.add_all(methods)
    db.session.commit()
    print("Payment methods seeded.")



def run_safe_seed():
    """
    Idempotent seed for production boot.
    Never drops tables. Only inserts missing baseline data.
    """
    reset_database(force=False)
    seed_settings()
    seed_support()
    seed_banners()
    seed_memberships()
    seed_admin()
    seed_partners()
    seed_products()
    seed_payments()
    print("Safe seed finished.")


if __name__ == "__main__":
    import os
    import sys
    from app import create_app

    # Safe by default: does NOT wipe data.
    # Wipe only if:  python seed.py --force
    #            or:  FORCE_SEED=1 python seed.py
    force = (
        "--force" in sys.argv
        or os.getenv("FORCE_SEED", "").strip() in ("1", "true", "yes")
    )

    app = create_app()
    with app.app_context():
        print("DATABASE_URL set:" , "yes" if os.getenv("DATABASE_URL") else "no (using local SQLite)")
        reset_database(force=force)
        seed_settings()
        seed_support()
        seed_banners()
        seed_memberships()
        seed_admin()
        seed_partners()
        seed_products()
        seed_payments()
        print()
        print("=" * 60)
        if force:
            print("DATABASE FORCE-RESEEDED (all data was wiped first)")
        else:
            print("SAFE SEED COMPLETE (existing data kept)")
        print("Admin login: admin / admin123")
        print("=" * 60)
