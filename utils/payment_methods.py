
"""Country-aware deposit methods. Crypto is always offered."""

CRYPTO_METHODS = [
    "USDT (TRC20)",
    "USDT (ERC20)",
    "Bitcoin (BTC)",
    "Ethereum (ETH)",
]

COUNTRY_METHODS = {
    "Uganda": ["MTN Mobile Money", "Airtel Money", "Bank Transfer"],
    "Kenya": ["M-Pesa", "Airtel Money", "Bank Transfer"],
    "Tanzania": ["M-Pesa", "Tigo Pesa", "Airtel Money", "Bank Transfer"],
    "Rwanda": ["MTN Mobile Money", "Airtel Money", "Bank Transfer"],
    "Nigeria": ["Bank Transfer", "Opay", "PalmPay"],
    "Ghana": ["MTN MoMo", "Vodafone Cash", "Bank Transfer"],
    "South Africa": ["Bank Transfer", "Capitec Pay", "EFT"],
    "United States": ["Bank Transfer", "Zelle", "Cash App"],
    "Canada": ["Bank Transfer", "Interac e-Transfer"],
    "United Kingdom": ["Bank Transfer", "Faster Payments"],
    "Germany": ["SEPA Bank Transfer", "Giropay", "Sofort"],
    "France": ["SEPA Bank Transfer"],
    "Netherlands": ["SEPA Bank Transfer", "iDEAL"],
    "India": ["UPI", "Bank Transfer", "Paytm"],
    "United Arab Emirates": ["Bank Transfer"],
    "Saudi Arabia": ["Bank Transfer"],
    "China": ["Bank Transfer", "Alipay"],
    "Australia": ["Bank Transfer", "PayID"],
}

DEFAULT_METHODS = ["Bank Transfer", "Mobile Money"]


def methods_for_country(country: str):
    local = list(COUNTRY_METHODS.get(country or "", DEFAULT_METHODS))
    # Crypto always available
    for c in CRYPTO_METHODS:
        if c not in local:
            local.append(c)
    return local


def active_deposit_methods(country: str = None):
    """
    Prefer active PaymentSetting rows filtered by country when possible.
    Always append crypto methods.
    """
    out = []
    seen = set()
    try:
        from models.payment_setting import PaymentSetting
        rows = (
            PaymentSetting.query.filter_by(active=True)
            .order_by(PaymentSetting.method.asc())
            .all()
        )
        country_l = (country or "").lower()
        for r in rows:
            label = (getattr(r, "method", None) or getattr(r, "provider", None) or "").strip()
            if not label:
                continue
            # optional country field on setting
            row_country = (getattr(r, "country", None) or "").strip()
            if row_country and country and row_country.lower() not in (country_l, "all", "global", "crypto"):
                # still allow if method is crypto
                if "usdt" not in label.lower() and "bitcoin" not in label.lower() and "ethereum" not in label.lower() and "crypto" not in label.lower():
                    continue
            if label not in seen:
                seen.add(label)
                out.append(label)
    except Exception as e:
        print("active_deposit_methods:", e)

    if not out:
        out = methods_for_country(country)
    else:
        for c in CRYPTO_METHODS:
            if c not in seen:
                out.append(c)
                seen.add(c)
    return out


PAYMENT_METHODS = DEFAULT_METHODS + CRYPTO_METHODS
