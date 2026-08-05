
"""Display money in user local currency. Storage base = UGX."""
from __future__ import annotations

def money(user, amount):
    try:
        amount = float(amount or 0)
    except (TypeError, ValueError):
        amount = 0.0
    currency = "UGX"
    symbol = "UGX"
    if user is not None:
        currency = getattr(user, "currency", None) or "UGX"
        symbol = getattr(user, "currency_symbol", None) or currency
    try:
        from utils.fx import format_local
        return format_local(amount, currency, symbol)
    except Exception:
        if currency == "UGX" or symbol in ("UGX", "USh", "UShs"):
            return f"UGX {amount:,.0f}"
        return f"{symbol} {amount:,.2f}"

def money_value(currency, symbol, amount):
    try:
        amount = float(amount or 0)
    except (TypeError, ValueError):
        amount = 0.0
    try:
        from utils.fx import format_local
        return format_local(amount, currency or "UGX", symbol or currency or "UGX")
    except Exception:
        if (currency or "UGX") == "UGX":
            return f"UGX {amount:,.0f}"
        return f"{symbol or currency} {amount:,.2f}"
