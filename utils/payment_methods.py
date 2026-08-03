
COUNTRY_METHODS = {
    "Uganda": ["MTN Mobile Money", "Airtel Money"],
    "Kenya": ["M-Pesa", "Airtel Money"],
    "Tanzania": ["M-Pesa", "Tigo Pesa", "Airtel Money"],
    "Nigeria": ["Bank Transfer", "Opay", "PalmPay"],
    "Ghana": ["MTN MoMo", "Vodafone Cash"],
    "Rwanda": ["MTN Mobile Money", "Airtel Money"],
    "South Africa": ["Bank Transfer", "Capitec Pay"],
}

DEFAULT_METHODS = ["MTN Mobile Money", "Airtel Money", "Bank Transfer"]


def methods_for_country(country: str):
    """Fallback list by country when no PaymentSetting rows exist."""
    if not country:
        return list(DEFAULT_METHODS)
    return list(COUNTRY_METHODS.get(country, DEFAULT_METHODS))


def active_deposit_methods(country: str = None):
    """
    Methods shown on the deposit page.
    Prefer active PaymentSetting.method values; never show inactive ones.
    """
    try:
        from models.payment_setting import PaymentSetting
        rows = (
            PaymentSetting.query.filter_by(active=True)
            .order_by(PaymentSetting.method.asc())
            .all()
        )
        if rows:
            # unique method labels preserving order
            seen = set()
            out = []
            for r in rows:
                label = (getattr(r, "method", None) or getattr(r, "provider", None) or "").strip()
                if label and label not in seen:
                    seen.add(label)
                    out.append(label)
            if out:
                return out
    except Exception as e:
        print("active_deposit_methods:", e)
    return methods_for_country(country)


PAYMENT_METHODS = DEFAULT_METHODS
