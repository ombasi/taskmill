
"""Legacy COUNTRIES map — prefer utils.world_currencies."""
from utils.world_currencies import COUNTRY_CURRENCY as COUNTRIES, currency_for_country, all_country_names

def money(user, amount):
    from helpers.currency import money as _m
    return _m(user, amount)
