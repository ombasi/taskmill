
import requests


def get_client_ip(request):
    """Best-effort client IP behind proxies / Render."""
    xff = request.headers.get("X-Forwarded-For", "")
    if xff:
        return xff.split(",")[0].strip()
    xri = request.headers.get("X-Real-IP", "")
    if xri:
        return xri.strip()
    return (request.remote_addr or "").strip()


def detect_location(ip):
    if not ip or ip in ("127.0.0.1", "::1", "localhost"):
        return {"country": "Uganda", "countryCode": "UG", "query": ip}
    try:
        data = requests.get(
            f"http://ip-api.com/json/{ip}?fields=status,message,country,countryCode,query",
            timeout=4,
        ).json()
        if data.get("status") == "success":
            return data
    except Exception as e:
        print("detect_location:", e)
    return None


def apply_geo_currency(user, ip=None, force=False):
    """
    Set user.country, currency, currency_symbol from IP.
    Does not convert stored balances (still UGX base).
    force=True always updates; else only if country empty or still default Uganda on first login.
    """
    if user is None:
        return user
    from utils.world_currencies import currency_for_country

    loc = detect_location(ip) if ip else None
    if not loc:
        return user

    country = loc.get("country") or user.country or "Uganda"
    code = loc.get("countryCode")
    cur, sym, _flag = currency_for_country(country, code)

    # User rules: Germany → EUR already; USA/Canada → USD already in map
    if not force and getattr(user, "country", None) and getattr(user, "currency", None):
        # still refresh IP
        if hasattr(user, "ip_address") and ip:
            user.ip_address = ip
        return user

    user.country = country
    user.currency = cur
    user.currency_symbol = sym
    if ip and hasattr(user, "ip_address"):
        user.ip_address = ip
    return user
