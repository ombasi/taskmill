
"""Add many products priced from low to UGX 1,000,000. Safe — no wipe."""
import random
from datetime import datetime
from app import create_app
from extensions import db
from models.product import Product
from models.partner import Partner

BRANDS = ["Amazon", "Jumia", "Jiji", "Temu", "eBay", "AliExpress", "Kilimall", "Shopify"]
BASE_ITEMS = [
    ("Power Bank 20000mAh", "Electronics"),
    ("Wireless Earbuds TWS", "Electronics"),
    ("Bluetooth Speaker", "Electronics"),
    ("Smart Watch", "Electronics"),
    ("Phone Soft Case", "Phones"),
    ("Fast Charger 25W", "Phones"),
    ("Screen Protector Glass", "Phones"),
    ("USB-C Cable 2m", "Accessories"),
    ("Laptop Stand Aluminium", "Electronics"),
    ("Wireless Mouse", "Electronics"),
    ("Mechanical Keyboard", "Electronics"),
    ("HD Webcam", "Electronics"),
    ("4K Action Camera", "Electronics"),
    ("Drone Mini Camera", "Electronics"),
    ("LED TV 32 Inch", "Electronics"),
    ("Soundbar 2.1", "Electronics"),
    ("Gaming Headset", "Electronics"),
    ("External SSD 1TB", "Electronics"),
    ("Router WiFi 6", "Electronics"),
    ("Men Running Shoes", "Fashion"),
    ("Women Handbag Leather", "Fashion"),
    ("Unisex Sneakers", "Fashion"),
    ("Denim Jacket", "Fashion"),
    ("Wrist Watch Automatic", "Fashion"),
    ("Sunglasses UV400", "Fashion"),
    ("Backpack Travel 40L", "Fashion"),
    ("Perfume 100ml", "Beauty"),
    ("Skincare Set 5pc", "Beauty"),
    ("Hair Dryer Professional", "Beauty"),
    ("Electric Kettle 1.8L", "Home"),
    ("Air Fryer 5L", "Home"),
    ("Blender 2L", "Home"),
    ("Microwave 20L", "Home"),
    ("Vacuum Cleaner", "Home"),
    ("Standing Fan", "Home"),
    ("Sofa Throw Set", "Home"),
    ("Office Chair Mesh", "Home"),
    ("Study Desk", "Home"),
    ("Refrigerator Mini", "Home"),
    ("Washing Machine Portable", "Home"),
    ("Generator 1.5kVA", "Home"),
    ("Solar Panel Kit 100W", "Home"),
    ("CCTV Camera Set", "Electronics"),
    ("Laptop 15 i5", "Electronics"),
    ("Tablet 10 Inch", "Electronics"),
    ("Smartphone 128GB", "Phones"),
    ("iPhone Style Case Pack", "Phones"),
    ("PlayStation Controller", "Electronics"),
    ("Football Official Size", "Accessories"),
    ("Yoga Mat Premium", "Accessories"),
]

IMAGES = {
    "Phones": [
        "https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?w=500&h=500&fit=crop",
        "https://images.unsplash.com/photo-1592899677977-9c10ca588bbd?w=500&h=500&fit=crop",
        "https://images.unsplash.com/photo-1510557880182-3d4d3cba35a5?w=500&h=500&fit=crop",
    ],
    "Electronics": [
        "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=500&h=500&fit=crop",
        "https://images.unsplash.com/photo-1496181133206-80ce9b88a853?w=500&h=500&fit=crop",
        "https://images.unsplash.com/photo-1545454675-3531b543be5d?w=500&h=500&fit=crop",
        "https://images.unsplash.com/photo-1593359677879-a4b92e8c1c91?w=500&h=500&fit=crop",
    ],
    "Fashion": [
        "https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=500&h=500&fit=crop",
        "https://images.unsplash.com/photo-1523381210434-271e8be1f52b?w=500&h=500&fit=crop",
        "https://images.unsplash.com/photo-1523170335258-f5ed11844a49?w=500&h=500&fit=crop",
    ],
    "Beauty": [
        "https://images.unsplash.com/photo-1596462502278-27bfdc403348?w=500&h=500&fit=crop",
        "https://images.unsplash.com/photo-1522335789203-aabdacdda6de?w=500&h=500&fit=crop",
    ],
    "Home": [
        "https://images.unsplash.com/photo-1556911220-bff31c812dce?w=500&h=500&fit=crop",
        "https://images.unsplash.com/photo-1555041469-a586c61ea9bc?w=500&h=500&fit=crop",
        "https://images.unsplash.com/photo-1586023492125-27b2c045efd7?w=500&h=500&fit=crop",
    ],
    "Accessories": [
        "https://images.unsplash.com/photo-1572635196237-14b3f281503f?w=500&h=500&fit=crop",
        "https://images.unsplash.com/photo-1606760227091-3dd870d97f1d?w=500&h=500&fit=crop",
    ],
}

# Price tiers up to 1,000,000 UGX
PRICE_BANDS = [
    (500, 3000),
    (3000, 10000),
    (10000, 30000),
    (30000, 80000),
    (80000, 150000),
    (150000, 300000),
    (300000, 500000),
    (500000, 750000),
    (750000, 1000000),
]

app = create_app()
with app.app_context():
    partner = Partner.query.first()
    if not partner:
        print("No partner — run seed.py first")
        raise SystemExit(1)

    existing = {p.name for p in Product.query.with_entities(Product.name).all()}
    added = 0
    target_extra = 1500

    while added < target_extra:
        brand = random.choice(BRANDS)
        item, cat = random.choice(BASE_ITEMS)
        lo, hi = random.choice(PRICE_BANDS)
        price = int(round(random.randint(lo, hi) / 50) * 50)
        name = f"{brand} {item} {random.randint(1000,9999)}"
        if name in existing:
            continue
        imgs = IMAGES.get(cat, IMAGES["Accessories"])
        p = Product(
            partner_id=partner.id,
            name=name,
            description=(
                f"{item} from {brand}. Quality marketplace listing. "
                f"Price UGX {price:,}. Suitable for review tasks."
            ),
            image=random.choice(imgs),
            category=cat,
            price=float(price),
            commission=float(round(price * 0.05, 0)),
            stock=random.randint(30, 500),
            active=True,
            created_at=datetime.utcnow(),
        )
        db.session.add(p)
        existing.add(name)
        added += 1
        if added % 200 == 0:
            db.session.commit()
            print(f"... {added}")

    db.session.commit()
    print(f"Added {added} products. Total: {Product.query.count()}")
    print(f"Max price in DB: {db.session.query(db.func.max(Product.price)).scalar()}")
