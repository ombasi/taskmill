
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


CRYPTO_PAYMENT_DEFAULTS = [
    {
        "method": "USDT (TRC20)",
        "provider": "Tether TRC20",
        "account_name": "USDT TRC20 Wallet",
        "account_number": "REPLACE_WITH_YOUR_TRC20_ADDRESS",
        "instructions": "Send only USDT on TRON (TRC20). Wrong network = lost funds. Paste TxID after payment.",
    },
    {
        "method": "USDT (ERC20)",
        "provider": "Tether ERC20",
        "account_name": "USDT ERC20 Wallet",
        "account_number": "REPLACE_WITH_YOUR_ERC20_ADDRESS",
        "instructions": "Send only USDT on Ethereum (ERC20). Wrong network = lost funds. Paste TxID after payment.",
    },
    {
        "method": "Bitcoin (BTC)",
        "provider": "Bitcoin",
        "account_name": "BTC Wallet",
        "account_number": "REPLACE_WITH_YOUR_BTC_ADDRESS",
        "instructions": "Send BTC only to this address. Confirm network fees. Paste TxID after payment.",
    },
    {
        "method": "Ethereum (ETH)",
        "provider": "Ethereum",
        "account_name": "ETH Wallet",
        "account_number": "REPLACE_WITH_YOUR_ETH_ADDRESS",
        "instructions": "Send ETH only on Ethereum mainnet. Paste TxID after payment.",
    },
]


def ensure_crypto_payment_methods():
    """Create crypto rows if missing so admin can edit addresses anytime."""
    from models.payment_setting import PaymentSetting
    from extensions import db
    created = 0
    for row in CRYPTO_PAYMENT_DEFAULTS:
        exists = PaymentSetting.query.filter_by(method=row["method"]).first()
        if exists:
            continue
        db.session.add(PaymentSetting(
            method=row["method"],
            provider=row["provider"],
            account_name=row["account_name"],
            account_number=row["account_number"],
            instructions=row["instructions"],
            active=True,
        ))
        created += 1
    if created:
        db.session.commit()
        print(f"Payment settings: added {created} crypto method(s)")
    return created
