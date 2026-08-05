
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
        return {"country": "Uganda", "countryCode": "UG", "query": ip}
    try:
        url = f"http://ip-api.com/json/{ip}?fields=status,message,country,countryCode,query"
        with urllib.request.urlopen(url, timeout=4) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        if data.get("status") == "success":
            return data
    except Exception as e:
        print("detect_location:", e)
    return None

def apply_geo_currency(user, ip=None, force=False):
    if user is None:
        return user
    from utils.world_currencies import currency_for_country
    loc = detect_location(ip) if ip else None
    if not loc:
        return user
    country = loc.get("country") or getattr(user, "country", None) or "Uganda"
    code = loc.get("countryCode")
    cur, sym, _flag = currency_for_country(country, code)
    if not force and getattr(user, "country", None) and getattr(user, "currency", None):
        if hasattr(user, "ip_address") and ip:
            user.ip_address = ip
        return user
    user.country = country
    user.currency = cur
    user.currency_symbol = sym
    if ip and hasattr(user, "ip_address"):
        user.ip_address = ip
    return user
