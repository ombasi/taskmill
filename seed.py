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
            commission_percent=3.5,
            combo_commission_percent=6.0,
            combo_probability=3,
            max_product_price=10000,
            withdrawal_limit=20000,
            minimum_deposit=15000,
            referral_bonus=2000,
            active=True
        ),
        Membership(
            name="Silver",
            price=120000,
            daily_tasks=36,
            tasks_per_set=18,
            daily_sets=2,
            commission_percent=4.0,
            combo_commission_percent=7.0,
            combo_probability=4,
            max_product_price=50000,
            withdrawal_limit=70000,
            minimum_deposit=30000,
            referral_bonus=5000,
            active=True
        ),
        Membership(
            name="Gold",
            price=300000,
            daily_tasks=42,
            tasks_per_set=21,
            daily_sets=2,
            commission_percent=4.5,
            combo_commission_percent=8.0,
            combo_probability=6,
            max_product_price=150000,
            withdrawal_limit=200000,
            minimum_deposit=60000,
            referral_bonus=10000,
            active=True
        ),
        Membership(
            name="VIP",
            price=700000,
            daily_tasks=50,
            tasks_per_set=25,
            daily_sets=2,
            commission_percent=5.0,
            combo_commission_percent=10.0,
            combo_probability=10,
            max_product_price=500000,
            withdrawal_limit=2000000,
            minimum_deposit=200000,
            referral_bonus=25000,
            active=True
        ),

    ]

    db.session.add_all(memberships)
    db.session.commit()
    # Ensure commission rates even if columns were added late
    rates = {
        "Starter": (3.5, 6.0),
        "Silver": (4.0, 7.0),
        "Gold": (4.5, 8.0),
        "VIP": (5.0, 10.0),
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
    "Samsung Galaxy A15 Case",
    "iPhone Lightning Cable",
    "Oraimo Necklace Bluetooth",
    "Baseus Car Charger Dual",
    "Xiaomi Redmi Buds",
    "Anker PowerCore Mini",
    "JBL Go Clip Speaker",
    "Sony Wired Earphones",
    "HP Wireless Mouse",
    "Logitech Keyboard Slim",
    "Canon Camera Strap",
    "Nike Running Socks Pair",
    "Adidas Cap Black",
    "Puma Sports T-Shirt",
    "Levi Style Denim Shorts",
    "Ray-Ban Style Shades",
    "Fossil Style Watch",
    "Maybelline Lipstick Set",
    "Nivea Soft Cream 200ml",
    "Colgate Electric Toothbrush",
    "Philips Trimmer",
    "Dyson Style Hair Comb",
    "Instant Pot Style Cooker Mini",
    "Nespresso Compatible Cups",
    "Tefal Non Stick Set",
    "Binatone Blender Jar",
    "Hisense Remote Cover",
    "LG TV Wall Bracket",
    "PlayStation Controller Skin",
    "Xbox Charging Cable",
    "Lego Compatible Blocks Set",
    "Hot Wheels Style Car Pack",
    "Ikea Style Desk Lamp",
    "Ashanti Print Cushion",
    "Kampala Market Basket",
    "Uganda Coffee Pack 500g",
    "Fresh Maize Flour 2kg",
    "Vegetable Oil 1L",
    "Solar Garden Light",
    "Rain Boots Rubber",

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
        (300, 1500),       # Starter low
        (1500, 4000),
        (4000, 7000),
        (7000, 10000),     # Starter max band
        (10000, 25000),    # Silver
        (25000, 50000),
        (50000, 100000),   # Gold
        (100000, 150000),
        (150000, 300000),  # VIP
        (300000, 500000),
    ]
    total_target = 1200
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
            brand = random.choice(["Amazon", "Alibaba", "Temu", "eBay", "Jumia", "Jiji", "AliExpress", partner.name])
            name = f"{brand} {base_name}"
            # Random price inside the band (rounded to nearest 50)
            price = random.randint(lo, hi)
            price = int(round(price / 50.0) * 50)
            price = max(lo, min(hi, price))
            commission = round(price * random.uniform(0.12, 0.20), 0)
            description = random.choice(desc_templates).format(
                item=base_name, brand=brand, price=price
            )

            # Marketplace-style product images (DummyJSON CDN + category keywords)
            cat = random.choice([
                "Electronics", "Phones", "Home", "Fashion", "Beauty", "Accessories"
            ])
            # Cycle real-looking product thumbnails from DummyJSON (1–100)
            dj_id = (image_index % 100) + 1
            # Multiple CDN patterns so images vary and match "shop" look
            image_pool = [
                f"https://cdn.dummyjson.com/product-images/{dj_id}/thumbnail.jpg",
                f"https://cdn.dummyjson.com/product-images/{dj_id}/1.jpg",
                f"https://cdn.dummyjson.com/product-images/{(dj_id % 30) + 1}/2.jpg",
            ]
            # Category-themed free stock (Unsplash source-style via images.unsplash fixed ids)
            unsplash_by_cat = {
                "Electronics": [
                    "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=400&h=400&fit=crop",
                    "https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=400&h=400&fit=crop",
                    "https://images.unsplash.com/photo-1546868871-7041f2a55e12?w=400&h=400&fit=crop",
                    "https://images.unsplash.com/photo-1572569511254-d8f925fe2cbb?w=400&h=400&fit=crop",
                ],
                "Phones": [
                    "https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?w=400&h=400&fit=crop",
                    "https://images.unsplash.com/photo-1592899677977-9c10ca588bbd?w=400&h=400&fit=crop",
                    "https://images.unsplash.com/photo-1580910051074-3eb694886505?w=400&h=400&fit=crop",
                    "https://images.unsplash.com/photo-1510557880182-3d4d3cba35a5?w=400&h=400&fit=crop",
                ],
                "Home": [
                    "https://images.unsplash.com/photo-1556911220-bff31c812dce?w=400&h=400&fit=crop",
                    "https://images.unsplash.com/photo-1586023492125-27b2c045efd7?w=400&h=400&fit=crop",
                    "https://images.unsplash.com/photo-1555041469-a586c61ea9bc?w=400&h=400&fit=crop",
                    "https://images.unsplash.com/photo-1524758631624-e2822e304c36?w=400&h=400&fit=crop",
                ],
                "Fashion": [
                    "https://images.unsplash.com/photo-1523381210434-271e8be1f52b?w=400&h=400&fit=crop",
                    "https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=400&h=400&fit=crop",
                    "https://images.unsplash.com/photo-1560769629-975ec94e6a86?w=400&h=400&fit=crop",
                    "https://images.unsplash.com/photo-1503342217505-b0a15ec3261c?w=400&h=400&fit=crop",
                ],
                "Beauty": [
                    "https://images.unsplash.com/photo-1596462502278-27bfdc403348?w=400&h=400&fit=crop",
                    "https://images.unsplash.com/photo-1522335789203-aabdacdda6de?w=400&h=400&fit=crop",
                    "https://images.unsplash.com/photo-1571781926291-c77df809dca0?w=400&h=400&fit=crop",
                    "https://images.unsplash.com/photo-1512496015851-a90fb38ba796?w=400&h=400&fit=crop",
                ],
                "Accessories": [
                    "https://images.unsplash.com/photo-1523170335258-f5ed11844a49?w=400&h=400&fit=crop",
                    "https://images.unsplash.com/photo-1627123424574-724758594e93?w=400&h=400&fit=crop",
                    "https://images.unsplash.com/photo-1572635196237-14b3f281503f?w=400&h=400&fit=crop",
                    "https://images.unsplash.com/photo-1606760227091-3dd870d97f1d?w=400&h=400&fit=crop",
                ],
            }
            pool = unsplash_by_cat.get(cat, unsplash_by_cat["Electronics"]) + image_pool
            image_url = pool[image_index % len(pool)]

            products.append(
                Product(
                    partner_id=partner.id,
                    name=name,
                    description=description,
                    image=image_url,
                    category=cat,
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


def seed_payments()
    try:
        from utils.payment_methods import ensure_crypto_payment_methods
        ensure_crypto_payment_methods()
    except Exception as e:
        print("crypto payments:", e):
    # crypto ensured below after mobile money

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
