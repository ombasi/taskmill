
"""Deposit methods from Payment Settings only (toggle active in admin)."""

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

# Seed helpers only — NOT auto-shown unless created + active in Payment Settings
CRYPTO_SEED = [
    {
        "method": "USDT (TRC20)",
        "provider": "Tether TRC20",
        "account_name": "USDT TRC20 Wallet",
        "account_number": "REPLACE_WITH_YOUR_TRC20_ADDRESS",
        "instructions": "Send only USDT on TRON (TRC20). Wrong network = lost funds.",
        "country": "all",
    },
    {
        "method": "USDT (ERC20)",
        "provider": "Tether ERC20",
        "account_name": "USDT ERC20 Wallet",
        "account_number": "REPLACE_WITH_YOUR_ERC20_ADDRESS",
        "instructions": "Send only USDT on Ethereum (ERC20).",
        "country": "all",
    },
    {
        "method": "Bitcoin (BTC)",
        "provider": "Bitcoin",
        "account_name": "BTC Wallet",
        "account_number": "REPLACE_WITH_YOUR_BTC_ADDRESS",
        "instructions": "Send BTC to this address only.",
        "country": "all",
    },
    {
        "method": "Ethereum (ETH)",
        "provider": "Ethereum",
        "account_name": "ETH Wallet",
        "account_number": "REPLACE_WITH_YOUR_ETH_ADDRESS",
        "instructions": "Send ETH on Ethereum mainnet only.",
        "country": "all",
    },
]


def methods_for_country(country: str):
    """Fallback labels only — prefer active_deposit_methods()."""
    return list(COUNTRY_METHODS.get(country or "", DEFAULT_METHODS))


def active_deposit_methods(country: str = None):
    """
    Only methods that exist in Payment Settings AND are active.
    Crypto appears only if those rows are active (admin toggle).
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
        country_l = (country or "").strip().lower()
        for r in rows:
            label = (getattr(r, "method", None) or getattr(r, "provider", None) or "").strip()
            if not label or label.lower() in seen:
                continue
            row_country = (getattr(r, "country", None) or "").strip().lower()
            if row_country and row_country not in ("", "all", "global", "any", "crypto"):
                if country_l and row_country != country_l:
                    continue
            item = {
                "id": getattr(r, "id", None),
                "method": label,
                "name": label,
                "provider": getattr(r, "provider", None) or label,
                "account_name": getattr(r, "account_name", None) or "",
                "account_number": getattr(r, "account_number", None) or "",
                "instructions": getattr(r, "instructions", None) or "",
                "qr_image": getattr(r, "qr_image", None) or getattr(r, "logo", None),
            }
            out.append(item)
            seen.add(label.lower())
    except Exception as e:
        print("active_deposit_methods:", e)

    # If admin has no payment settings yet, soft fallback (no crypto)
    if not out:
        for label in methods_for_country(country):
            if label.lower() not in seen:
                out.append({"method": label, "provider": label, "account_name": "", "account_number": "", "instructions": ""})
                seen.add(label.lower())
    return out


def ensure_crypto_rows():
    """Create crypto PaymentSetting rows if missing (inactive by default)."""
    try:
        from models.payment_setting import PaymentSetting
        from extensions import db
        for spec in CRYPTO_SEED:
            exists = PaymentSetting.query.filter_by(method=spec["method"]).first()
            if exists:
                continue
            row = PaymentSetting(
                method=spec["method"],
                provider=spec.get("provider"),
                account_name=spec.get("account_name"),
                account_number=spec.get("account_number"),
                instructions=spec.get("instructions"),
                active=False,  # admin must toggle on
            )
            if hasattr(PaymentSetting, "country"):
                row.country = spec.get("country", "all")
            db.session.add(row)
        db.session.commit()
    except Exception as e:
        print("ensure_crypto_rows:", e)
        try:
            from extensions import db
            db.session.rollback()
        except Exception:
            pass


def ensure_crypto_payment_methods():
    """Backward-compatible alias."""
    return ensure_crypto_rows()
