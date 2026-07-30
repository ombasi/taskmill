
"""
Match product images to product names by keyword (phones, shoes, etc.).
Safe to run anytime — does not wipe users or balances.
"""
import re
from app import create_app
from extensions import db
from models.product import Product

# Keyword → realistic product photos (Unsplash, free to hotlink with params)
IMAGE_MAP = [
    (["phone", "iphone", "samsung", "android", "smartphone", "mobile"], [
        "https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?w=500&h=500&fit=crop",
        "https://images.unsplash.com/photo-1592899677977-9c10ca588bbd?w=500&h=500&fit=crop",
        "https://images.unsplash.com/photo-1510557880182-3d4d3cba35a5?w=500&h=500&fit=crop",
        "https://images.unsplash.com/photo-1580910051074-3eb694886505?w=500&h=500&fit=crop",
    ]),
    (["laptop", "macbook", "notebook", "computer"], [
        "https://images.unsplash.com/photo-1496181133206-80ce9b88a853?w=500&h=500&fit=crop",
        "https://images.unsplash.com/photo-1517336714731-489689fd1ca8?w=500&h=500&fit=crop",
        "https://images.unsplash.com/photo-1525547719571-a2d4ac8945e2?w=500&h=500&fit=crop",
    ]),
    (["headphone", "earbud", "earphone", "airpod", "headset"], [
        "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=500&h=500&fit=crop",
        "https://images.unsplash.com/photo-1484704849700-f032a568e944?w=500&h=500&fit=crop",
        "https://images.unsplash.com/photo-1546435770-a3e426bf472b?w=500&h=500&fit=crop",
    ]),
    (["watch", "smartwatch"], [
        "https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=500&h=500&fit=crop",
        "https://images.unsplash.com/photo-1524805444758-089113d48a6d?w=500&h=500&fit=crop",
        "https://images.unsplash.com/photo-1524592094714-0f0654e20314?w=500&h=500&fit=crop",
    ]),
    (["shoe", "sneaker", "boot", "sandal"], [
        "https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=500&h=500&fit=crop",
        "https://images.unsplash.com/photo-1560769629-975ec94e6a86?w=500&h=500&fit=crop",
        "https://images.unsplash.com/photo-1549298916-b41d501d3772?w=500&h=500&fit=crop",
    ]),
    (["bag", "backpack", "handbag", "purse"], [
        "https://images.unsplash.com/photo-1548036328-c9fa89d128fa?w=500&h=500&fit=crop",
        "https://images.unsplash.com/photo-1553062407-98eeb64c6a62?w=500&h=500&fit=crop",
    ]),
    (["shirt", "dress", "jacket", "cloth", "fashion", "jean", "trouser"], [
        "https://images.unsplash.com/photo-1523381210434-271e8be1f52b?w=500&h=500&fit=crop",
        "https://images.unsplash.com/photo-1489987707025-afc232f7ea0f?w=500&h=500&fit=crop",
        "https://images.unsplash.com/photo-1434389677669-e08bb46a47e2?w=500&h=500&fit=crop",
    ]),
    (["beauty", "makeup", "cosmetic", "lipstick", "cream", "serum"], [
        "https://images.unsplash.com/photo-1596462502278-27bfdc403348?w=500&h=500&fit=crop",
        "https://images.unsplash.com/photo-1522335789203-aabdacdda6de?w=500&h=500&fit=crop",
        "https://images.unsplash.com/photo-1512496015851-a90fb38ba796?w=500&h=500&fit=crop",
    ]),
    (["tv", "television", "monitor", "screen"], [
        "https://images.unsplash.com/photo-1593359677879-a4b92e8c1c91?w=500&h=500&fit=crop",
        "https://images.unsplash.com/photo-1461151304267-38535e780c79?w=500&h=500&fit=crop",
    ]),
    (["camera", "lens", "gopro"], [
        "https://images.unsplash.com/photo-1516035069371-29a1b244cc32?w=500&h=500&fit=crop",
        "https://images.unsplash.com/photo-1502920917128-1aa500764cbd?w=500&h=500&fit=crop",
    ]),
    (["speaker", "bluetooth", "audio"], [
        "https://images.unsplash.com/photo-1545454675-3531b543be5d?w=500&h=500&fit=crop",
        "https://images.unsplash.com/photo-1608043152269-423dbba4e7e1?w=500&h=500&fit=crop",
    ]),
    (["fridge", "kitchen", "cook", "blender", "microwave"], [
        "https://images.unsplash.com/photo-1556911220-bff31c812dce?w=500&h=500&fit=crop",
        "https://images.unsplash.com/photo-1574269909862-7e1d70bb8078?w=500&h=500&fit=crop",
    ]),
    (["sofa", "chair", "furniture", "table", "bed"], [
        "https://images.unsplash.com/photo-1555041469-a586c61ea9bc?w=500&h=500&fit=crop",
        "https://images.unsplash.com/photo-1586023492125-27b2c045efd7?w=500&h=500&fit=crop",
    ]),
    (["toy", "game", "console", "playstation", "xbox"], [
        "https://images.unsplash.com/photo-1606144042614-b2417e99c4e3?w=500&h=500&fit=crop",
        "https://images.unsplash.com/photo-1593305841991-05c297ba4575?w=500&h=500&fit=crop",
    ]),
]

DEFAULT_IMAGES = [
    "https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=500&h=500&fit=crop",
    "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=500&h=500&fit=crop",
    "https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=500&h=500&fit=crop",
    "https://images.unsplash.com/photo-1526170375885-4d8ecf77b99f?w=500&h=500&fit=crop",
]


def pick_image(name, index):
    text = (name or "").lower()
    for keywords, urls in IMAGE_MAP:
        if any(k in text for k in keywords):
            return urls[index % len(urls)]
    return DEFAULT_IMAGES[index % len(DEFAULT_IMAGES)]


app = create_app()
with app.app_context():
    products = Product.query.order_by(Product.id.asc()).all()
    for i, p in enumerate(products):
        p.image = pick_image(p.name, i)
        # Category from keyword
        text = (p.name or "").lower()
        if any(k in text for k in ("phone", "iphone", "samsung", "mobile")):
            p.category = "Phones"
        elif any(k in text for k in ("shoe", "shirt", "dress", "fashion", "bag")):
            p.category = "Fashion"
        elif any(k in text for k in ("beauty", "makeup", "cream")):
            p.category = "Beauty"
        elif any(k in text for k in ("sofa", "chair", "kitchen", "fridge")):
            p.category = "Home"
        elif any(k in text for k in ("laptop", "headphone", "tv", "camera", "speaker")):
            p.category = "Electronics"
        else:
            p.category = p.category or "Accessories"
    db.session.commit()
    print(f"Matched images for {len(products)} products by name keywords.")
