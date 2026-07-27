from app import create_app
from extensions import db
app = create_app()
with app.app_context():
    db.session.execute(db.text("ALTER TABLE users ADD COLUMN set2_unlocked BOOLEAN DEFAULT 0"))
    db.session.commit()