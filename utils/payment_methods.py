"""
Local + global deposit methods.
Admin seeds catalogs, toggles active, and fills account details.
Users only see ACTIVE methods that match their country (or global).
"""

# Country display name -> list of local method labels
COUNTRY_METHODS = {
    # East Africa
    "Uganda": ["MTN Mobile Money", "Airtel Money", "Bank Transfer (UG)"],
    "Kenya": ["M-Pesa", "Airtel Money", "Equitel", "Bank Transfer (KE)"],
    "Tanzania": ["M-Pesa", "Tigo Pesa", "Airtel Money", "HaloPesa", "Bank Transfer (TZ)"],
    "Rwanda": ["MTN Mobile Money", "Airtel Money", "Bank Transfer (RW)"],
    "Burundi": ["Lumicash", "EcoCash", "Bank Transfer (BI)"],
    "South Sudan": ["m-Gurush", "Bank Transfer (SS)"],
    "Ethiopia": ["TeleBirr", "CBE Birr", "Bank Transfer (ET)"],
    "Somalia": ["EVC Plus", "Zaad", "Bank Transfer (SO)"],
    # West / Central Africa
    "Nigeria": ["Bank Transfer (NG)", "Opay", "PalmPay", "Moniepoint", "Chipper Cash"],
    "Ghana": ["MTN MoMo", "Vodafone Cash", "AirtelTigo Money", "Bank Transfer (GH)"],
    "Côte d'Ivoire": ["Orange Money", "MTN MoMo", "Wave", "Bank Transfer (CI)"],
    "Ivory Coast": ["Orange Money", "MTN MoMo", "Wave", "Bank Transfer (CI)"],
    "Senegal": ["Orange Money", "Wave", "Free Money", "Bank Transfer (SN)"],
    "Cameroon": ["MTN MoMo", "Orange Money", "Bank Transfer (CM)"],
    "Congo": ["Airtel Money", "M-Pesa", "Orange Money", "Bank Transfer (CG)"],
    "Democratic Republic of the Congo": ["Airtel Money", "M-Pesa", "Orange Money", "Bank Transfer (CD)"],
    "DR Congo": ["Airtel Money", "M-Pesa", "Orange Money", "Bank Transfer (CD)"],
    "Mali": ["Orange Money", "Moov Money", "Bank Transfer (ML)"],
    "Burkina Faso": ["Orange Money", "Moov Money", "Bank Transfer (BF)"],
    "Benin": ["MTN MoMo", "Moov Money", "Bank Transfer (BJ)"],
    "Togo": ["T-Money", "Flooz", "Bank Transfer (TG)"],
    "Niger": ["Airtel Money", "Orange Money", "Bank Transfer (NE)"],
    "Guinea": ["Orange Money", "MTN MoMo", "Bank Transfer (GN)"],
    "Sierra Leone": ["Orange Money", "Africell Money", "Bank Transfer (SL)"],
    "Liberia": ["Orange Money", "Lonestar Cell MTN", "Bank Transfer (LR)"],
    "Gambia": ["Africell Money", "Bank Transfer (GM)"],
    # Southern Africa
    "South Africa": ["EFT Bank Transfer", "Capitec Pay", "SnapScan", "Ozow"],
    "Zambia": ["Airtel Money", "MTN MoMo", "Zamtel Kwacha", "Bank Transfer (ZM)"],
    "Zimbabwe": ["EcoCash", "OneMoney", "Bank Transfer (ZW)"],
    "Malawi": ["Airtel Money", "TNM Mpamba", "Bank Transfer (MW)"],
    "Mozambique": ["M-Pesa", "e-Mola", "Bank Transfer (MZ)"],
    "Botswana": ["Orange Money", "MyZaka", "Bank Transfer (BW)"],
    "Namibia": ["Bank Transfer (NA)", "eWallet"],
    "Angola": ["Multicaixa", "Bank Transfer (AO)"],
    # North Africa / Middle East
    "Egypt": ["Vodafone Cash", "InstaPay", "Fawry", "Bank Transfer (EG)"],
    "Morocco": ["CashPlus", "Bank Transfer (MA)"],
    "Algeria": ["Baridimob", "Bank Transfer (DZ)"],
    "Tunisia": ["Bank Transfer (TN)", "Flouci"],
    "United Arab Emirates": ["Bank Transfer (AE)", "Emirates NBD Transfer"],
    "Saudi Arabia": ["STC Pay", "Bank Transfer (SA)"],
    "Qatar": ["Bank Transfer (QA)"],
    "Kuwait": ["Bank Transfer (KW)"],
    "Bahrain": ["Bank Transfer (BH)"],
    "Jordan": ["CliQ", "Bank Transfer (JO)"],
    "Lebanon": ["Bank Transfer (LB)"],
    "Turkey": ["Papara", "Bank Transfer (TR)", "Havale/EFT"],
    "Israel": ["Bit", "Bank Transfer (IL)"],
    # Europe
    "Germany": ["SEPA Bank Transfer", "Giropay", "Sofort", "PayPal"],
    "France": ["SEPA Bank Transfer", "PayLib", "PayPal"],
    "Netherlands": ["iDEAL", "SEPA Bank Transfer", "PayPal"],
    "Belgium": ["Bancontact", "SEPA Bank Transfer", "PayPal"],
    "Spain": ["SEPA Bank Transfer", "Bizum", "PayPal"],
    "Italy": ["SEPA Bank Transfer", "PayPal", "Postepay"],
    "Portugal": ["MB Way", "SEPA Bank Transfer", "PayPal"],
    "United Kingdom": ["Faster Payments", "Bank Transfer (UK)", "PayPal"],
    "Ireland": ["SEPA Bank Transfer", "PayPal"],
    "Switzerland": ["Bank Transfer (CH)", "TWINT", "PayPal"],
    "Austria": ["SEPA Bank Transfer", "EPS", "PayPal"],
    "Sweden": ["Swish", "Bank Transfer (SE)", "PayPal"],
    "Norway": ["Vipps", "Bank Transfer (NO)"],
    "Denmark": ["MobilePay", "Bank Transfer (DK)"],
    "Finland": ["MobilePay", "Bank Transfer (FI)"],
    "Poland": ["BLIK", "Bank Transfer (PL)", "PayPal"],
    "Czech Republic": ["Bank Transfer (CZ)", "PayPal"],
    "Romania": ["Bank Transfer (RO)", "PayPal"],
    "Greece": ["Bank Transfer (GR)", "PayPal"],
    "Russia": ["SBP", "Bank Transfer (RU)"],
    "Ukraine": ["Bank Transfer (UA)", "Privat24"],
    # Americas
    "United States": ["Zelle", "Cash App", "Venmo", "Bank ACH Transfer", "PayPal"],
    "Canada": ["Interac e-Transfer", "Bank Transfer (CA)", "PayPal"],
    "Mexico": ["SPEI", "OXXO", "Bank Transfer (MX)"],
    "Brazil": ["Pix", "Bank Transfer (BR)"],
    "Argentina": ["Mercado Pago", "Bank Transfer (AR)"],
    "Colombia": ["Nequi", "Daviplata", "Bank Transfer (CO)"],
    "Chile": ["Bank Transfer (CL)", "Mach"],
    "Peru": ["Yape", "Plin", "Bank Transfer (PE)"],
    # Asia / Pacific
    "India": ["UPI", "Paytm", "PhonePe", "Bank Transfer (IN)"],
    "Pakistan": ["JazzCash", "Easypaisa", "Bank Transfer (PK)"],
    "Bangladesh": ["bKash", "Nagad", "Rocket", "Bank Transfer (BD)"],
    "Sri Lanka": ["Bank Transfer (LK)"],
    "China": ["Alipay", "WeChat Pay", "Bank Transfer (CN)"],
    "Hong Kong": ["FPS", "Bank Transfer (HK)", "PayMe"],
    "Japan": ["Bank Transfer (JP)", "PayPay", "Line Pay"],
    "South Korea": ["Bank Transfer (KR)", "KakaoPay", "Toss"],
    "Indonesia": ["GoPay", "OVO", "DANA", "Bank Transfer (ID)"],
    "Malaysia": ["DuitNow", "Touch 'n Go", "Bank Transfer (MY)"],
    "Singapore": ["PayNow", "Bank Transfer (SG)"],
    "Thailand": ["PromptPay", "TrueMoney", "Bank Transfer (TH)"],
    "Vietnam": ["MoMo", "ZaloPay", "Bank Transfer (VN)"],
    "Philippines": ["GCash", "Maya", "Bank Transfer (PH)"],
    "Australia": ["PayID", "Bank Transfer (AU)", "PayPal"],
    "New Zealand": ["Bank Transfer (NZ)", "PayPal"],
}

GLOBAL_METHODS = [
    "Bank Transfer",
    "PayPal",
    "Wise Transfer",
]

CRYPTO_SEED = [
    {
        "method": "USDT (TRC20)",
        "provider": "Tether TRC20",
        "account_name": "USDT TRC20 Wallet",
        "account_number": "REPLACE_WITH_YOUR_TRC20_ADDRESS",
        "instructions": "Send only USDT on TRON (TRC20). Wrong network = lost funds.",
        "countries": "ALL",
    },
    {
        "method": "USDT (ERC20)",
        "provider": "Tether ERC20",
        "account_name": "USDT ERC20 Wallet",
        "account_number": "REPLACE_WITH_YOUR_ERC20_ADDRESS",
        "instructions": "Send only USDT on Ethereum (ERC20).",
        "countries": "ALL",
    },
    {
        "method": "Bitcoin (BTC)",
        "provider": "Bitcoin",
        "account_name": "BTC Wallet",
        "account_number": "REPLACE_WITH_YOUR_BTC_ADDRESS",
        "instructions": "Send BTC to this address only.",
        "countries": "ALL",
    },
    {
        "method": "Ethereum (ETH)",
        "provider": "Ethereum",
        "account_name": "ETH Wallet",
        "account_number": "REPLACE_WITH_YOUR_ETH_ADDRESS",
        "instructions": "Send ETH on Ethereum mainnet only.",
        "countries": "ALL",
    },
]


def methods_for_country(country: str):
    if not country:
        return list(GLOBAL_METHODS)
    return list(COUNTRY_METHODS.get(country, GLOBAL_METHODS))


def _ensure_countries_column():
    """Add payment_settings.countries if missing."""
    try:
        from extensions import db
        from sqlalchemy import text, inspect
        insp = inspect(db.engine)
        if "payment_settings" not in insp.get_table_names():
            return
        cols = {c["name"] for c in insp.get_columns("payment_settings")}
        if "countries" in cols:
            return
        dialect = db.engine.dialect.name
        if dialect == "postgresql":
            db.session.execute(text(
                "ALTER TABLE payment_settings ADD COLUMN IF NOT EXISTS countries VARCHAR(255) DEFAULT 'ALL'"
            ))
        else:
            db.session.execute(text(
                "ALTER TABLE payment_settings ADD COLUMN countries VARCHAR(255) DEFAULT 'ALL'"
            ))
        db.session.commit()
    except Exception as e:
        try:
            from extensions import db
            db.session.rollback()
        except Exception:
            pass
        print("ensure countries col:", e)


def ensure_crypto_payment_methods():
    """Create crypto rows if missing (inactive by default)."""
    return ensure_catalog_payment_methods(include_local=False, include_crypto=True)


def ensure_catalog_payment_methods(include_local=True, include_crypto=True, activate=False):
    """
    Seed catalog of local + global + crypto methods.
    New rows are inactive unless activate=True — admin toggles on and edits details.
    Returns number of rows created.
    """
    from models.payment_setting import PaymentSetting
    from extensions import db

    _ensure_countries_column()
    created = 0
    seen = set()

    def _add(method, provider=None, account_name=None, account_number=None,
             instructions=None, countries="ALL", active=False):
        nonlocal created
        key = method.strip()
        if not key or key in seen:
            return
        seen.add(key)
        row = PaymentSetting.query.filter_by(method=key).first()
        if row:
            # backfill countries if empty
            if hasattr(row, "countries") and not getattr(row, "countries", None):
                row.countries = countries
            return
        row = PaymentSetting(
            method=key,
            provider=provider or key,
            account_name=account_name or "SET IN ADMIN",
            account_number=account_number or "SET IN ADMIN",
            instructions=instructions or f"Pay via {key}. Admin will publish account details.",
            active=bool(active),
        )
        if hasattr(row, "countries"):
            row.countries = countries
        db.session.add(row)
        created += 1

    if include_local:
        for country, methods in COUNTRY_METHODS.items():
            for m in methods:
                _add(
                    m,
                    provider=m,
                    countries=country,
                    instructions=f"{m} — used in {country}. Set your paybill / account in admin.",
                    active=activate,
                )
        for m in GLOBAL_METHODS:
            _add(m, provider=m, countries="ALL", active=activate)

    if include_crypto:
        for c in CRYPTO_SEED:
            _add(
                c["method"],
                provider=c.get("provider"),
                account_name=c.get("account_name"),
                account_number=c.get("account_number"),
                instructions=c.get("instructions"),
                countries=c.get("countries", "ALL"),
                active=activate,
            )

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print("ensure_catalog_payment_methods:", e)
        return 0
    return created


def active_deposit_methods(user=None, country=None):
    """Active PaymentSetting rows visible for this user/country."""
    from models.payment_setting import PaymentSetting

    _ensure_countries_column()
    rows = (
        PaymentSetting.query.filter(PaymentSetting.active.is_(True))
        .order_by(PaymentSetting.method.asc())
        .all()
    )
    country = country or (getattr(user, "country", None) if user else None)
    if not country:
        return rows

    out = []
    c_norm = str(country).strip().lower()
    for r in rows:
        cs = (getattr(r, "countries", None) or "ALL").strip()
        if not cs or cs.upper() == "ALL":
            out.append(r)
            continue
        parts = [p.strip().lower() for p in cs.split(",") if p.strip()]
        if c_norm in parts:
            out.append(r)
    return out
