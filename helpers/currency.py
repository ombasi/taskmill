"""
Currency helpers for Taskmill.
Primary currency is Uganda Shillings (UGX).
"""


def money(user, amount):
    """
    Format amount for display.
    Always prefers UGX style as per project requirements.
    Example: UGX 15,000
    """
    if amount is None:
        amount = 0
    try:
        amount = float(amount)
    except (TypeError, ValueError):
        amount = 0.0

    # Prefer user's currency if set, otherwise UGX
    currency = getattr(user, "currency", None) or "UGX"
    symbol = getattr(user, "currency_symbol", None) or "UGX"

    if currency == "UGX" or symbol in ("UGX", "USh", "UShs"):
        # Integer-style for Ugandan Shillings (no decimals needed)
        return f"UGX {amount:,.0f}"

    # Fallback for other currencies
    return f"{symbol} {amount:,.2f}"


def money_value(currency, symbol, amount):
    """Format without a user object."""
    if amount is None:
        amount = 0
    try:
        amount = float(amount)
    except (TypeError, ValueError):
        amount = 0.0

    if currency == "UGX" or symbol in ("UGX", "USh", "UShs"):
        return f"UGX {amount:,.0f}"
    return f"{symbol} {amount:,.2f}"
