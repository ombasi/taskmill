from extensions import db


class PaymentSetting(db.Model):
    __tablename__ = "payment_settings"

    id = db.Column(db.Integer, primary_key=True)

    method = db.Column(
        db.String(50),
        unique=True,
        nullable=False
    )

    provider = db.Column(
        db.String(50)
    )

    account_name = db.Column(
        db.String(120)
    )

    account_number = db.Column(
        db.String(255)
    )

    instructions = db.Column(
        db.Text
    )

    logo = db.Column(
    db.String(100)
    )

    qr_code = db.Column(
    db.String(255)
    )

    active = db.Column(
        db.Boolean,
        default=True
    )

    # Comma-separated country names, or ALL for global (crypto, PayPal, etc.)
    countries = db.Column(
        db.String(255),
        default="ALL"
    )

    def __repr__(self):
        return self.method