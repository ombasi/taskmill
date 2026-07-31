"""
Map product names → category + matching image URLs.
Keeps phones looking like phones, shoes like shoes, etc.
"""

# keyword groups: (keywords_tuple, category, image_urls)
CATALOG = [
    (
        ("iphone", "samsung galaxy", "smartphone", "android phone", "mobile phone", "tecno", "infinix", "redmi", "pixel phone"),
        "Phones",
        [
            "https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?w=500&h=500&fit=crop",
            "https://images.unsplash.com/photo-1592899677977-9c10ca588bbd?w=500&h=500&fit=crop",
            "https://images.unsplash.com/photo-1510557880182-3d4d3cba35a5?w=500&h=500&fit=crop",
            "https://images.unsplash.com/photo-1580910051074-3eb694886505?w=500&h=500&fit=crop",
        ],
    ),
    (
        ("phone case", "soft case", "screen protector", "tempered glass", "phone holder", "selfie ring", "charger cable", "lightning cable", "type-c", "usb-c cable", "car charger", "power bank", "earbud", "earphone", "airpod", "neckband"),
        "Phones",
        [
            "https://images.unsplash.com/photo-1601784551446-20c9e07cdbdb?w=500&h=500&fit=crop",
            "https://images.unsplash.com/photo-1609091839311-d5365f9ff1c5?w=500&h=500&fit=crop",
            "https://images.unsplash.com/photo-1583394838336-acd977736f90?w=500&h=500&fit=crop",
            "https://images.unsplash.com/photo-1597872200969-2b65d56bd16b?w=500&h=500&fit=crop",
        ],
    ),
    (
        ("laptop", "macbook", "notebook computer", "chromebook"),
        "Electronics",
        [
            "https://images.unsplash.com/photo-1496181133206-80ce9b88a853?w=500&h=500&fit=crop",
            "https://images.unsplash.com/photo-1517336714731-489689fd1ca8?w=500&h=500&fit=crop",
            "https://images.unsplash.com/photo-1525547719571-a2d4ac8945e2?w=500&h=500&fit=crop",
        ],
    ),
    (
        ("headphone", "headset", "earbud", "earphone"),
        "Electronics",
        [
            "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=500&h=500&fit=crop",
            "https://images.unsplash.com/photo-1484704849700-f032a568e944?w=500&h=500&fit=crop",
            "https://images.unsplash.com/photo-1546435770-a3e426bf472b?w=500&h=500&fit=crop",
        ],
    ),
    (
        ("speaker", "soundbar", "jbl", "bluetooth speaker"),
        "Electronics",
        [
            "https://images.unsplash.com/photo-1545454675-3531b543be5d?w=500&h=500&fit=crop",
            "https://images.unsplash.com/photo-1608043152269-423dbba4e7e1?w=500&h=500&fit=crop",
        ],
    ),
    (
        ("watch", "smartwatch", "smart watch"),
        "Electronics",
        [
            "https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=500&h=500&fit=crop",
            "https://images.unsplash.com/photo-1524805444758-089113d48a6d?w=500&h=500&fit=crop",
            "https://images.unsplash.com/photo-1434056886845-dac89ffe9b56?w=500&h=500&fit=crop",
        ],
    ),
    (
        ("tv", "television", "monitor", "led tv"),
        "Electronics",
        [
            "https://images.unsplash.com/photo-1593359677879-a4b92e8c1c91?w=500&h=500&fit=crop",
            "https://images.unsplash.com/photo-1461151304267-38535e780c79?w=500&h=500&fit=crop",
        ],
    ),
    (
        ("camera", "webcam", "gopro", "drone"),
        "Electronics",
        [
            "https://images.unsplash.com/photo-1516035069371-29a1b244cc32?w=500&h=500&fit=crop",
            "https://images.unsplash.com/photo-1502920917128-1aa500764cbd?w=500&h=500&fit=crop",
        ],
    ),
    (
        ("keyboard", "mouse", "usb hub", "ssd", "flash drive", "memory card", "router", "hdmi"),
        "Electronics",
        [
            "https://images.unsplash.com/photo-1587829741301-dc798b83add3?w=500&h=500&fit=crop",
            "https://images.unsplash.com/photo-1527864550417-7fd91fc51a46?w=500&h=500&fit=crop",
            "https://images.unsplash.com/photo-1597872200969-2b65d56bd16b?w=500&h=500&fit=crop",
        ],
    ),
    (
        ("shoe", "sneaker", "boot", "cleat", "sandal", "running shoe"),
        "Fashion",
        [
            "https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=500&h=500&fit=crop",
            "https://images.unsplash.com/photo-1560769629-975ec94e6a86?w=500&h=500&fit=crop",
            "https://images.unsplash.com/photo-1549298916-b41d501d3772?w=500&h=500&fit=crop",
            "https://images.unsplash.com/photo-1606107557195-0e29a4b5b4aa?w=500&h=500&fit=crop",
        ],
    ),
    (
        ("bag", "handbag", "backpack", "purse", "luggage"),
        "Fashion",
        [
            "https://images.unsplash.com/photo-1548036328-c9fa89d128fa?w=500&h=500&fit=crop",
            "https://images.unsplash.com/photo-1553062407-98eeb64c6a62?w=500&h=500&fit=crop",
        ],
    ),
    (
        ("shirt", "t-shirt", "dress", "jacket", "jean", "trouser", "hoodie", "cap", "hat", "belt", "sock"),
        "Fashion",
        [
            "https://images.unsplash.com/photo-1523381210434-271e8be1f52b?w=500&h=500&fit=crop",
            "https://images.unsplash.com/photo-1489987707025-afc232f7ea0f?w=500&h=500&fit=crop",
            "https://images.unsplash.com/photo-1434389677669-e08bb46a47e2?w=500&h=500&fit=crop",
        ],
    ),
    (
        ("sunglass", "ray-ban", "shades"),
        "Fashion",
        [
            "https://images.unsplash.com/photo-1572635196237-14b3f281503f?w=500&h=500&fit=crop",
            "https://images.unsplash.com/photo-1511499767150-a48a237f0083?w=500&h=500&fit=crop",
        ],
    ),
    (
        ("lipstick", "makeup", "cosmetic", "skincare", "serum", "lotion", "cream", "perfume", "nivea", "maybelline", "beauty"),
        "Beauty",
        [
            "https://images.unsplash.com/photo-1596462502278-27bfdc403348?w=500&h=500&fit=crop",
            "https://images.unsplash.com/photo-1522335789203-aabdacdda6de?w=500&h=500&fit=crop",
            "https://images.unsplash.com/photo-1512496015851-a90fb38ba796?w=500&h=500&fit=crop",
            "https://images.unsplash.com/photo-1571781926291-c77df809dca0?w=500&h=500&fit=crop",
        ],
    ),
    (
        ("hair dryer", "trimmer", "toothbrush"),
        "Beauty",
        [
            "https://images.unsplash.com/photo-1522338242992-e1a54906a8da?w=500&h=500&fit=crop",
            "https://images.unsplash.com/photo-1527799820374-dcf8d9d4a388?w=500&h=500&fit=crop",
        ],
    ),
    (
        ("kettle", "blender", "air fryer", "microwave", "cooker", "frying pan", "knife", "kitchen"),
        "Home",
        [
            "https://images.unsplash.com/photo-1556911220-bff31c812dce?w=500&h=500&fit=crop",
            "https://images.unsplash.com/photo-1574269909862-7e1d70bb8078?w=500&h=500&fit=crop",
            "https://images.unsplash.com/photo-1585515320310-259814833e62?w=500&h=500&fit=crop",
        ],
    ),
    (
        ("sofa", "chair", "desk", "furniture", "table", "bed", "lamp", "clock"),
        "Home",
        [
            "https://images.unsplash.com/photo-1555041469-a586c61ea9bc?w=500&h=500&fit=crop",
            "https://images.unsplash.com/photo-1586023492125-27b2c045efd7?w=500&h=500&fit=crop",
            "https://images.unsplash.com/photo-1507473885765-e6ed057f782c?w=500&h=500&fit=crop",
        ],
    ),
    (
        ("fridge", "refrigerator", "washing machine", "vacuum", "fan", "generator", "solar"),
        "Home",
        [
            "https://images.unsplash.com/photo-1571175443880-49e1d25b2bc5?w=500&h=500&fit=crop",
            "https://images.unsplash.com/photo-1558317374-c4c8c4f5f5f5?w=500&h=500&fit=crop",
            "https://images.unsplash.com/photo-1509391366360-2e959784a276?w=500&h=500&fit=crop",
        ],
    ),
    (
        ("playstation", "xbox", "console", "controller", "game"),
        "Electronics",
        [
            "https://images.unsplash.com/photo-1606144042614-b2417e99c4e3?w=500&h=500&fit=crop",
            "https://images.unsplash.com/photo-1593305841991-05c297ba4575?w=500&h=500&fit=crop",
        ],
    ),
    (
        ("yoga", "football", "ball", "sport"),
        "Accessories",
        [
            "https://images.unsplash.com/photo-1544367567-0f2fcb009e0b?w=500&h=500&fit=crop",
            "https://images.unsplash.com/photo-1579952363873-27f3bade9f55?w=500&h=500&fit=crop",
        ],
    ),
    (
        ("bottle", "umbrella", "tripod", "torch", "bulb", "extension", "cable"),
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


def match_product(name: str, index: int = 0):
    """Return (category, image_url) for a product name."""
    text = (name or "").lower()
    # Prefer longer/more specific keyword matches first within each group
    best = None
    best_len = 0
    for keywords, category, urls in CATALOG:
        for kw in keywords:
            if kw in text and len(kw) > best_len:
                best = (category, urls)
                best_len = len(kw)
    if best:
        category, urls = best
        return category, urls[index % len(urls)]
    cat, urls = DEFAULT
    return cat, urls[index % len(urls)]
