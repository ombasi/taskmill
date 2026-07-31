"""Re-tag every product with fuzzy-matched category + image from its name."""
from app import create_app
from extensions import db
from models.product import Product
from utils.product_media import match_product

app = create_app()
with app.app_context():
    products = Product.query.order_by(Product.id.asc()).all()
    by_cat = {}
    for i, p in enumerate(products):
        cat, img = match_product(p.name, i)
        p.category = cat
        p.image = img
        by_cat[cat] = by_cat.get(cat, 0) + 1
    db.session.commit()
    print(f"Updated {len(products)} products (fuzzy match).")
    for c, n in sorted(by_cat.items(), key=lambda x: -x[1]):
        print(f"  {c}: {n}")
