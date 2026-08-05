
"""
FX rates relative to base UGX.
Balances & product prices stay stored in UGX; display converts to user currency.
"""
from __future__ import annotations
import json
import time
from pathlib import Path

BASE = "UGX"
CACHE_SECONDS = 6 * 3600  # 6 hours
_CACHE = {"ts": 0, "rates": {}}  # code → units of currency per 1 UGX? 
# We store: rates[CODE] = how many CODE equal 1 USD, then convert via USD.

def _cache_path():
    try:
        from flask import current_app
        root = Path(current_app.root_path) / "instance"
    except Exception:
        root = Path("instance")
    root.mkdir(parents=True, exist_ok=True)
    return root / "fx_cache.json"


def _load_disk():
    p = _cache_path()
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if time.time() - data.get("ts", 0) < CACHE_SECONDS:
            return data.get("rates") or {}
    except Exception:
        pass
    return None


def _save_disk(rates):
    try:
        p = _cache_path()
        p.write_text(json.dumps({"ts": time.time(), "rates": rates}), encoding="utf-8")
    except Exception as e:
        print("fx cache save:", e)


def fetch_rates_usd_base():
    """Return dict currency→rate vs USD (1 USD = rate units of currency)."""
    global _CACHE
    if _CACHE["rates"] and time.time() - _CACHE["ts"] < CACHE_SECONDS:
        return _CACHE["rates"]

    disk = _load_disk()
    if disk:
        _CACHE = {"ts": time.time(), "rates": disk}
        return disk

    rates = {"USD": 1.0, "UGX": 3800.0}  # safe fallback
    try:
        import urllib.request
        url = "https://open.er-api.com/v6/latest/USD"
        with urllib.request.urlopen(url, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        if data.get("result") == "success" and data.get("rates"):
            rates = {k: float(v) for k, v in data["rates"].items()}
    except Exception as e:
        print("fx fetch:", e)
        # secondary fallback static-ish
        rates.update({
            "EUR": 0.92, "GBP": 0.79, "KES": 129.0, "TZS": 2600.0,
            "RWF": 1300.0, "NGN": 1600.0, "GHS": 15.5, "ZAR": 18.5,
            "CAD": 1.36, "AUD": 1.52, "INR": 83.0, "CNY": 7.2,
            "JPY": 155.0, "CHF": 0.88, "AED": 3.67, "SAR": 3.75,
        })

    _CACHE = {"ts": time.time(), "rates": rates}
    _save_disk(rates)
    return rates


def ugx_to(amount_ugx, currency_code):
    """Convert UGX amount to target currency."""
    amount_ugx = float(amount_ugx or 0)
    code = (currency_code or "UGX").upper()
    if code == "UGX":
        return amount_ugx
    rates = fetch_rates_usd_base()
    ugx_per_usd = float(rates.get("UGX") or 3800)
    if ugx_per_usd <= 0:
        ugx_per_usd = 3800
    usd = amount_ugx / ugx_per_usd
    if code == "USD":
        return usd
    target = float(rates.get(code) or 0)
    if target <= 0:
        return amount_ugx  # unknown → show UGX number
    return usd * target


def to_ugx(amount_local, currency_code):
    """Convert local currency amount entered by user → UGX for storage."""
    amount_local = float(amount_local or 0)
    code = (currency_code or "UGX").upper()
    if code == "UGX":
        return amount_local
    rates = fetch_rates_usd_base()
    ugx_per_usd = float(rates.get("UGX") or 3800)
    if code == "USD":
        return amount_local * ugx_per_usd
    target = float(rates.get(code) or 0)
    if target <= 0:
        return amount_local
    usd = amount_local / target
    return usd * ugx_per_usd


def format_local(amount_ugx, currency_code, symbol=None):
    local = ugx_to(amount_ugx, currency_code)
    code = (currency_code or "UGX").upper()
    sym = symbol or code
    # whole numbers for most African currencies / JPY / KRW
    if code in ("UGX", "KES", "TZS", "RWF", "NGN", "JPY", "KRW", "VND", "IDR", "GNF", "BIF", "MGA"):
        return f"{sym} {local:,.0f}"
    return f"{sym} {local:,.2f}"
