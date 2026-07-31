"""
Map product names → category + matching image URLs.
Uses fuzzy / token matching so "iPhone", "iphne", "Apple Phone 14"
still resolve to Phones — not shoes.
"""

from difflib import SequenceMatcher

# (keywords, category, image_urls)
# Longer / more specific keywords are preferred.
CATALOG = [
    (
        ("iphone", "samsung galaxy", "smartphone", "android phone", "mobile phone",
         "tecno spark", "tecno camon", "infinix", "redmi", "pixel phone", "galaxy a",
         "phone 12", "phone 13", "phone 14", "phone 15"),
        "Phones",
        [
            "https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?w=500&h=500&fit=crop",
            "https://images.unsplash.com/photo-1592899677977-9c10ca588bbd?w=500&h=500&fit=crop",
            "https://images.unsplash.com/photo-1510557880182-3d4d3cba35a5?w=500&h=500&fit=crop",
            "https://images.unsplash.com/photo-1580910051074-3eb694886505?w=500&h=500&fit=crop",
        ],
    ),
    (
        ("phone case", "soft case", "screen protector", "tempered glass", "phone holder",
         "selfie ring", "charger cable", "lightning cable", "type-c", "usb-c cable",
         "car charger", "power bank", "powerbank", "oraimo", "baseus"),
        "Phones",
        [
            "https://images.unsplash.com/photo-1601784551446-20c9e07cdbdb?w=500&h=500&fit=crop",
            "https://images.unsplash.com/photo-1609091839311-d5365f9ff1c5?w=500&h=500&fit=crop",
            "https://images.unsplash.com/photo-1583394838336-acd977736f90?w=500&h=500&fit=crop",
            "https://images.unsplash.com/photo-1597872200969-2b65d56bd16b?w=500&h=500&fit=crop",
        ],
    ),
    (
        ("earbud", "earphone", "airpod", "airpods", "neckband", "tws", "wired earphone"),
        "Electronics",
        [
            "https://images.unsplash.com/photo-1590658268037-6bf12165a8df?w=500&h=500&fit=crop",
            "https://images.unsplash.com/photo-1484704849700-f032a568e944?w=500&h=500&fit=crop",
            "https://images.unsplash.com/photo-1606220945770-b5b6c2c55bf1?w=500&h=500&fit=crop",
        ],
    ),
    (
        ("laptop", "macbook", "notebook", "chromebook", "ultrabook"),
        "Electronics",
        [
            "https://images.unsplash.com/photo-1496181133206-80ce9b88a853?w=500&h=500&fit=crop",
            "https://images.unsplash.com/photo-1517336714731-489689fd1ca8?w=500&h=500&fit=crop",
            "https://images.unsplash.com/photo-1525547719571-a2d4ac8945e2?w=500&h=500&fit=crop",
        ],
    ),
    (
        ("headphone", "headset", "gaming headset"),
        "Electronics",
        [
            "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=500&h=500&fit=crop",
            "https://images.unsplash.com/photo-1546435770-a3e426bf472b?w=500&h=500&fit=crop",
        ],
    ),
    (
        ("speaker", "soundbar", "bluetooth speaker", "jbl go", "jbl clip"),
        "Electronics",
        [
            "https://images.unsplash.com/photo-1545454675-3531b543be5d?w=500&h=500&fit=crop",
            "https://images.unsplash.com/photo-1608043152269-423dbba4e7e1?w=500&h=500&fit=crop",
        ],
    ),
    (
        ("smartwatch", "smart watch", "wrist watch", "analog watch", "fossil watch", "watch band"),
        "Electronics",
        [
            "https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=500&h=500&fit=crop",
            "https://images.unsplash.com/photo-1524805444758-089113d48a6d?w=500&h=500&fit=crop",
            "https://images.unsplash.com/photo-1434056886845-dac89ffe9b56?w=500&h=500&fit=crop",
        ],
    ),
    (
        ("television", "led tv", "smart tv", "monitor screen", "tv 32", "tv 43"),
        "Electronics",
        [
            "https://images.unsplash.com/photo-1593359677879-a4b92e8c1c91?w=500&h=500&fit=crop",
            "https://images.unsplash.com/photo-1461151304267-38535e780c79?w=500&h=500&fit=crop",
        ],
    ),
    (
        ("camera", "webcam", "gopro", "action camera", "drone"),
        "Electronics",
        [
            "https://images.unsplash.com/photo-1516035069371-29a1b244cc32?w=500&h=500&fit=crop",
            "https://images.unsplash.com/photo-1502920917128-1aa500764cbd?w=500&h=500&fit=crop",
        ],
    ),
    (
        ("keyboard", "wireless mouse", "usb mouse", "usb hub", "external ssd",
         "flash drive", "memory card", "wifi router", "hdmi cable"),
        "Electronics",
        [
            "https://images.unsplash.com/photo-1587829741301-dc798b83add3?w=500&h=500&fit=crop",
            "https://images.unsplash.com/photo-1527864550417-7fd91fc51a46?w=500&h=500&fit=crop",
        ],
    ),
    (
        ("tablet", "ipad"),
        "Electronics",
        [
            "https://images.unsplash.com/photo-1544244015-0df4b3ffc6b0?w=500&h=500&fit=crop",
            "https://images.unsplash.com/photo-1561154464-82e9adf32764?w=500&h=500&fit=crop",
        ],
    ),
    (
        ("playstation", "xbox", "console", "game controller", "ps5", "ps4"),
        "Electronics",
        [
            "https://images.unsplash.com/photo-1606144042614-b2417e99c4e3?w=500&h=500&fit=crop",
            "https://images.unsplash.com/photo-1593305841991-05c297ba4575?w=500&h=500&fit=crop",
        ],
    ),
    (
        ("running shoe", "sneakers", "cleat", "boot", "sandal", "trainer", "shoe "),
        "Fashion",
        [
            "https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=500&h=500&fit=crop",
            "https://images.unsplash.com/photo-1560769629-975ec94e6a86?w=500&h=500&fit=crop",
            "https://images.unsplash.com/photo-1549298916-b41d501d3772?w=500&h=500&fit=crop",
            "https://images.unsplash.com/photo-1606107557195-0e29a4b5b4aa?w=500&h=500&fit=crop",
        ],
    ),
    (
        ("handbag", "backpack", "purse", "luggage", "school bag", "travel bag"),
        "Fashion",
        [
            "https://images.unsplash.com/photo-1548036328-c9fa89d128fa?w=500&h=500&fit=crop",
            "https://images.unsplash.com/photo-1553062407-98eeb64c6a62?w=500&h=500&fit=crop",
        ],
    ),
    (
        ("t-shirt", "tshirt", "hoodie", "denim", "jacket", "trouser", "jeans",
         "dress", "ankara", "sports cap", " cap", "baseball cap", "leather belt", "socks", "adidas", "nike", "puma"),
        "Fashion",
        [
            "https://images.unsplash.com/photo-1523381210434-271e8be1f52b?w=500&h=500&fit=crop",
            "https://images.unsplash.com/photo-1489987707025-afc232f7ea0f?w=500&h=500&fit=crop",
            "https://images.unsplash.com/photo-1434389677669-e08bb46a47e2?w=500&h=500&fit=crop",
        ],
    ),
    (
        ("sunglasses", "sunglass", "shades", "ray-ban", "rayban"),
        "Fashion",
        [
            "https://images.unsplash.com/photo-1572635196237-14b3f281503f?w=500&h=500&fit=crop",
            "https://images.unsplash.com/photo-1511499767150-a48a237f0083?w=500&h=500&fit=crop",
        ],
    ),
    (
        ("lipstick", "makeup", "cosmetic", "skincare", "serum", "body lotion",
         "face cream", "perfume", "nivea", "maybelline", "beauty set"),
        "Beauty",
        [
            "https://images.unsplash.com/photo-1596462502278-27bfdc403348?w=500&h=500&fit=crop",
            "https://images.unsplash.com/photo-1522335789203-aabdacdda6de?w=500&h=500&fit=crop",
            "https://images.unsplash.com/photo-1512496015851-a90fb38ba796?w=500&h=500&fit=crop",
        ],
    ),
    (
        ("hair dryer", "hairdryer", "trimmer", "toothbrush", "shaver"),
        "Beauty",
        [
            "https://images.unsplash.com/photo-1522338242992-e1a54906a8da?w=500&h=500&fit=crop",
            "https://images.unsplash.com/photo-1527799820374-dcf8d9d4a388?w=500&h=500&fit=crop",
        ],
    ),
    (
        ("kettle", "blender", "air fryer", "microwave", "cooker", "frying pan",
         "knife set", "kitchen"),
        "Home",
        [
            "https://images.unsplash.com/photo-1556911220-bff31c812dce?w=500&h=500&fit=crop",
            "https://images.unsplash.com/photo-1574269909862-7e1d70bb8078?w=500&h=500&fit=crop",
            "https://images.unsplash.com/photo-1585515320310-259814833e62?w=500&h=500&fit=crop",
        ],
    ),
    (
        ("sofa", "office chair", "study desk", "furniture", "coffee table",
         "bed frame", "desk lamp", "wall clock"),
        "Home",
        [
            "https://images.unsplash.com/photo-1555041469-a586c61ea9bc?w=500&h=500&fit=crop",
            "https://images.unsplash.com/photo-1586023492125-27b2c045efd7?w=500&h=500&fit=crop",
            "https://images.unsplash.com/photo-1507473885765-e6ed057f782c?w=500&h=500&fit=crop",
        ],
    ),
    (
        ("refrigerator", "fridge", "washing machine", "vacuum cleaner",
         "standing fan", "generator", "solar panel"),
        "Home",
        [
            "https://images.unsplash.com/photo-1571175443880-49e1d25b2bc5?w=500&h=500&fit=crop",
            "https://images.unsplash.com/photo-1509391366360-2e959784a276?w=500&h=500&fit=crop",
        ],
    ),
    (
        ("yoga mat", "football", "soccer ball", "sport bottle"),
        "Accessories",
        [
            "https://images.unsplash.com/photo-1544367567-0f2fcb009e0b?w=500&h=500&fit=crop",
            "https://images.unsplash.com/photo-1579952363873-27f3bade9f55?w=500&h=500&fit=crop",
        ],
    ),
    (
        ("water bottle", "umbrella", "tripod", "torch", "led bulb",
         "extension cable", "power strip"),
        "Accessories",
        [
            "https://images.unsplash.com/photo-1602143407151-7111542de6e8?w=500&h=500&fit=crop",
            "https://images.unsplash.com/photo-1563297007-0686b7003af7?w=500&h=500&fit=crop",
        ],
    ),
]

DEFAULT = (
    "Accessories",
    [
        "https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=500&h=500&fit=crop",
        "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=500&h=500&fit=crop",
    ],
)

# Tokens to ignore when scoring
STOP = {
    "amazon", "jumia", "jiji", "temu", "ebay", "aliexpress", "kilimall",
    "shopify", "the", "and", "for", "with", "from", "pack", "set", "new",
    "official", "style", "compatible", "pcs", "pc", "ugx",
}


def _tokens(text: str):
    raw = "".join(c.lower() if c.isalnum() else " " for c in (text or ""))
    return [t for t in raw.split() if t and t not in STOP and len(t) > 1]


def _ratio(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def _score_keyword(name_tokens, name_text: str, keyword: str) -> float:
    """
    Score how well a keyword matches the product name.
    Combines: exact substring, token overlap, fuzzy token similarity.
    """
    kw = keyword.lower().strip()
    if not kw:
        return 0.0

    # Strong: full phrase inside name
    if kw in name_text:
        return 1.0 + len(kw) * 0.02

    kw_tokens = _tokens(kw)
    if not kw_tokens or not name_tokens:
        return 0.0

    token_scores = []
    strong_hits = 0
    for kt in kw_tokens:
        best = 0.0
        for nt in name_tokens:
            if kt == nt:
                best = 1.0
            elif len(kt) >= 4 and len(nt) >= 4 and (kt in nt or nt in kt):
                best = max(best, 0.9)
            elif len(kt) >= 4 and len(nt) >= 4:
                r = _ratio(kt, nt)
                if r >= 0.84:
                    best = max(best, r)
        if best >= 0.84:
            strong_hits += 1
        token_scores.append(best)

    if not token_scores or strong_hits == 0:
        return 0.0

    avg = sum(token_scores) / len(token_scores)
    if avg < 0.8:
        return 0.0
    return avg + len(kw) * 0.005


def match_product(name: str, index: int = 0):
    """
    Return (category, image_url) using fuzzy name matching.
    """
    text = (name or "").lower()
    name_tokens = _tokens(name)

    best_score = 0.0
    best_cat = None
    best_urls = None

    for keywords, category, urls in CATALOG:
        for kw in keywords:
            score = _score_keyword(name_tokens, text, kw)
            if score > best_score:
                best_score = score
                best_cat = category
                best_urls = urls

    # Minimum confidence — otherwise default (avoids random wrong category)
    if best_cat is None or best_score < 0.8:
        cat, urls = DEFAULT
        return cat, urls[index % len(urls)]

    return best_cat, best_urls[index % len(best_urls)]
