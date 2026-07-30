
"""Add realistic products if catalog is thin (safe, no wipe)."""
import random
from datetime import datetime
from app import create_app
from extensions import db
from models.product import Product
from models.partner import Partner

NAMES = [
    ("Oraimo Power Bank 20000mAh", "Electronics", 45000),
    ("Tecno Camon Soft Case", "Phones", 8000),
    ("Infinix Smart Charger", "Phones", 15000),
    ("Wireless Earbuds TWS", "Electronics", 35000),
    ("Type-C Fast Cable", "Accessories", 5000),
    ("Men Canvas Sneakers", "Fashion", 55000),
    ("Women Handbag", "Fashion", 40000),
    ("Bluetooth Speaker Mini", "Electronics", 28000),
    ("Electric Kettle 1.8L", "Home", 45000),
    ("Non-Stick Frying Pan", "Home", 25000),
    ("Wrist Watch Analog", "Fashion", 30000),
    ("USB Flash Drive 32GB", "Electronics", 18000),
    ("Memory Card 64GB", "Electronics", 22000),
    ("Phone Tripod Stand", "Accessories", 12000),
    ("LED Bulb Pack 3pcs", "Home", 9000),
    ("Backpack School Bag", "Fashion", 35000),
    ("Hair Dryer Mini", "Beauty", 40000),
    ("Body Lotion Set", "Beauty", 15000),
    ("Yoga Mat", "Accessories", 20000),
    ("Water Bottle 1L", "Home", 8000),
    ("Samsung Style Phone Case", "Phones", 10000),
    ("iPhone Cable Braided", "Phones", 12000),
    ("JBL Style Mini Speaker", "Electronics", 50000),
    ("Nike Style Running Socks", "Fashion", 15000),
    ("Maybelline Style Lip Kit", "Beauty", 18000),
    ("Nivea Cream 200ml", "Beauty", 12000),
    ("Solar Garden Light", "Home", 25000),
    ("Desk Lamp LED", "Home", 30000),
    ("Wireless Mouse", "Electronics", 20000),
    ("Keyboard USB", "Electronics", 35000),
    ("Webcam HD", "Electronics", 55000),
    ("Umbrella Foldable", "Accessories", 10000),
    ("Sports Cap", "Fashion", 12000),
    ("Leather Belt", "Fashion", 18000),
    ("Sunglasses Unisex", "Fashion", 15000),
    ("Extension Cable 4-Way", "Home", 14000),
    ("Rechargeable Torch", "Home", 16000),
    ("Mosquito Repellent Machine", "Home", 22000),
    ("Shoe Rack Stackable", "Home", 28000),
    ("Laundry Basket", "Home", 18000),
]

IMAGES = {
    "Phones": [
        "https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?w=500&h=500&fit=crop",
        "https://images.unsplash.com/photo-1592899677977-9c10ca588bbd?w=500&h=500&fit=crop",
    ],
    "Electronics": [
        "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=500&h=500&fit=crop",
        "https://images.unsplash.com/photo-1545454675-3531b543be5d?w=500&h=500&fit=crop",
    ],
    "Fashion": [
        "https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=500&h=500&fit=crop",
        "https://images.unsplash.com/photo-1523381210434-271e8be1f52b?w=500&h=500&fit=crop",
    ],
    "Beauty": [
        "https://images.unsplash.com/photo-1596462502278-27bfdc403348?w=500&h=500&fit=crop",
        "https://images.unsplash.com/photo-1522335789203-aabdacdda6de?w=500&h=500&fit=crop",
    ],
    "Home": [
        "https://images.unsplash.com/photo-1556911220-bff31c812dce?w=500&h=500&fit=crop",
        "https://images.unsplash.com/photo-1555041469-a586c61ea9bc?w=500&h=500&fit=crop",
    ],
    "Accessories": [
        "https://images.unsplash.com/photo-1523170335258-f5ed11844a49?w=500&h=500&fit=crop",
        "https://images.unsplash.com/photo-1572635196237-14b3f281503f?w=500&h=500&fit=crop",
    ],
}

app = create_app()
with app.app_context():
    partner = Partner.query.first()
    if not partner:
        print("No partner — run seed first")
        raise SystemExit(1)
    existing = {p.name for p in Product.query.all()}
    brands = ["Amazon", "Jumia", "Jiji", "Temu", "eBay", "AliExpress"]
    added = 0
    for i, (name, cat, base_price) in enumerate(NAMES):
        for brand in brands:
            full = f"{brand} {name}"
            if full in existing:
                continue
            # vary price ±20%
            price = int(round(base_price * random.uniform(0.85, 1.15) / 50) * 50)
            commission = round(price * 0.05, 0)
            imgs = IMAGES.get(cat, IMAGES["Accessories"])
            p = Product(
                partner_id=partner.id,
                name=full,
                description=f"Authentic {name} listed via {brand}. Fast delivery across Uganda. Ideal for product review tasks.",
                image=imgs[i % len(imgs)],
                category=cat,
                price=float(price),
                commission=float(commission),
                stock=random.randint(50, 400),
                active=True,
                created_at=datetime.utcnow(),
            )
            db.session.add(p)
            existing.add(full)
            added += 1
    db.session.commit()
    print(f"Added {added} products. Total now: {Product.query.count()}")
