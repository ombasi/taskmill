"""Timezone helpers: users see local time; admin console uses EAT (Africa/Nairobi)."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

try:
    EAT = ZoneInfo("Africa/Nairobi")  # UTC+3, no DST
except Exception:
    EAT = timezone(timedelta(hours=3))

UTC = timezone.utc

# Country code → IANA timezone (primary business TZ)
COUNTRY_TZ = {
    "UG": "Africa/Nairobi",
    "KE": "Africa/Nairobi",
    "TZ": "Africa/Nairobi",
    "RW": "Africa/Kigali",
    "BI": "Africa/Bujumbura",
    "CD": "Africa/Kinshasa",
    "CG": "Africa/Brazzaville",
    "NG": "Africa/Lagos",
    "GH": "Africa/Accra",
    "ZA": "Africa/Johannesburg",
    "EG": "Africa/Cairo",
    "ET": "Africa/Addis_Ababa",
    "SS": "Africa/Juba",
    "SO": "Africa/Mogadishu",
    "SD": "Africa/Khartoum",
    "ZM": "Africa/Lusaka",
    "MW": "Africa/Blantyre",
    "MZ": "Africa/Maputo",
    "AO": "Africa/Luanda",
    "CM": "Africa/Douala",
    "CI": "Africa/Abidjan",
    "SN": "Africa/Dakar",
    "DE": "Europe/Berlin",
    "AT": "Europe/Vienna",
    "CH": "Europe/Zurich",
    "NL": "Europe/Amsterdam",
    "BE": "Europe/Brussels",
    "FR": "Europe/Paris",
    "GB": "Europe/London",
    "IE": "Europe/Dublin",
    "IT": "Europe/Rome",
    "ES": "Europe/Madrid",
    "PT": "Europe/Lisbon",
    "PL": "Europe/Warsaw",
    "SE": "Europe/Stockholm",
    "NO": "Europe/Oslo",
    "DK": "Europe/Copenhagen",
    "FI": "Europe/Helsinki",
    "US": "America/New_York",
    "CA": "America/Toronto",
    "MX": "America/Mexico_City",
    "BR": "America/Sao_Paulo",
    "AR": "America/Argentina/Buenos_Aires",
    "IN": "Asia/Kolkata",
    "PK": "Asia/Karachi",
    "BD": "Asia/Dhaka",
    "CN": "Asia/Shanghai",
    "JP": "Asia/Tokyo",
    "KR": "Asia/Seoul",
    "SG": "Asia/Singapore",
    "MY": "Asia/Kuala_Lumpur",
    "PH": "Asia/Manila",
    "TH": "Asia/Bangkok",
    "VN": "Asia/Ho_Chi_Minh",
    "ID": "Asia/Jakarta",
    "AU": "Australia/Sydney",
    "NZ": "Pacific/Auckland",
    "AE": "Asia/Dubai",
    "SA": "Asia/Riyadh",
    "TR": "Europe/Istanbul",
    "RU": "Europe/Moscow",
}

# Country name → code (fallback from user.country string)
NAME_TO_CODE = {
    "uganda": "UG", "kenya": "KE", "tanzania": "TZ", "rwanda": "RW",
    "nigeria": "NG", "ghana": "GH", "germany": "DE", "netherlands": "NL",
    "united states": "US", "usa": "US", "canada": "CA", "united kingdom": "GB",
    "uk": "GB", "france": "FR", "india": "IN", "china": "CN", "south africa": "ZA",
    "congo": "CD", "dr congo": "CD", "ethiopia": "ET", "egypt": "EG",
}


def utcnow():
    return datetime.now(UTC)


def utcnow_naive():
    return datetime.now(UTC).replace(tzinfo=None)


def _as_utc(dt: datetime) -> datetime:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def tz_for_country(country_or_code: str | None) -> ZoneInfo:
    if not country_or_code:
        return EAT
    raw = str(country_or_code).strip()
    code = raw.upper() if len(raw) == 2 else NAME_TO_CODE.get(raw.lower(), "")
    name = COUNTRY_TZ.get(code, "Africa/Nairobi")
    try:
        return ZoneInfo(name)
    except Exception:
        return EAT


def tz_for_user(user) -> ZoneInfo:
    if user is None:
        return EAT
    # Optional explicit override
    pref = getattr(user, "timezone", None)
    if pref:
        try:
            return ZoneInfo(str(pref))
        except Exception:
            pass
    return tz_for_country(getattr(user, "country", None))


def to_user_tz(dt: datetime, user=None) -> datetime | None:
    if not dt:
        return None
    return _as_utc(dt).astimezone(tz_for_user(user))


def to_eat(dt: datetime) -> datetime | None:
    if not dt:
        return None
    return _as_utc(dt).astimezone(EAT)


def format_user(dt, user=None, fmt: str = "%d %b %Y · %H:%M") -> str:
    if not dt:
        return "—"
    try:
        local = to_user_tz(dt, user)
        return local.strftime(fmt)
    except Exception:
        try:
            return dt.strftime(fmt)
        except Exception:
            return "—"


def to_gmt(dt: datetime) -> datetime | None:
    """GMT is equivalent to UTC for display purposes."""
    if not dt:
        return None
    return _as_utc(dt)


def format_gmt(dt, fmt: str = "%d %b %Y · %H:%M") -> str:
    """Format datetime in GMT (UTC) for admin last-seen and global logs."""
    if not dt:
        return "—"
    try:
        return to_gmt(dt).strftime(fmt) + " GMT"
    except Exception:
        try:
            return dt.strftime(fmt) + " GMT"
        except Exception:
            return "—"


def format_eat(dt, fmt: str = "%d %b %Y · %H:%M") -> str:
    if not dt:
        return "—"
    try:
        return to_eat(dt).strftime(fmt)
    except Exception:
        try:
            return dt.strftime(fmt)
        except Exception:
            return "—"


def format_smart(dt, user=None, is_admin_view: bool = False, fmt: str = "%d %b %Y · %H:%M") -> str:
    """Admin views → EAT; user views → user local TZ."""
    if is_admin_view:
        return format_eat(dt, fmt)
    return format_user(dt, user, fmt)
