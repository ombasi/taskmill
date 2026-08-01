
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
    if not country:
        return DEFAULT_METHODS
    return COUNTRY_METHODS.get(country, DEFAULT_METHODS)

PAYMENT_METHODS = DEFAULT_METHODS
