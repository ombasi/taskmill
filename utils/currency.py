
from utils.world_currencies import COUNTRY_CURRENCY as COUNTRIES  # noqa: F401
from utils.world_currencies import currency_for_country, all_country_names  # noqa: F401

def money(user, amount):
    from helpers.currency import money as format_money
    return format_money(user, amount)
