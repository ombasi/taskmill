
import json
import urllib.request


def get_client_ip(request):
    xff = request.headers.get("X-Forwarded-For", "")
    if xff:
        return xff.split(",")[0].strip()
    xri = request.headers.get("X-Real-IP", "")
    if xri:
        return xri.strip()
    return (request.remote_addr or "").strip()


def detect_location(ip):
    if not ip or ip in ("127.0.0.1", "::1", "localhost"):
        # Localhost: leave geo unknown so we do not force Uganda over real VPN IP
        return None
    try:
        url = f"http://ip-api.com/json/{ip}?fields=status,message,country,countryCode,query"
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        if data.get("status") == "success":
            return data
    except Exception as e:
        print("detect_location:", e)
    return None


def apply_geo_currency(user, ip=None, force=False):
    """
    Sync country + currency from IP.
    When IP country is known and differs from stored (or force), update.
    Localhost IP is ignored so VPN public IP on proxies still works via X-Forwarded-For.
    """
    if user is None:
        return user
    from utils.world_currencies import currency_for_country

    if ip and hasattr(user, "ip_address"):
        user.ip_address = ip

    loc = detect_location(ip) if ip else None
    if not loc:
        return user

    country = loc.get("country") or "Uganda"
    code = loc.get("countryCode")
    cur, sym, _flag = currency_for_country(country, code)

    # Always update when IP geo is available (VPN change → new currency)
    if force or True:
        user.country = country
        user.currency = cur
        user.currency_symbol = sym
    return user
