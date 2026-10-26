import threading
import time
from database import supabase

BRANCH_ID = 1

# ==========================================================
# COMMON SERIALIZER
# ==========================================================

def serialize_menu_item(row):
    img = row.get("image")
    if img and not img.startswith("http") and not img.startswith("/"):
        img = "/" + img

    meal_img = row.get("meal_image")
    if meal_img and not meal_img.startswith("http") and not meal_img.startswith("/"):
        meal_img = "/" + meal_img

    return {
        "id": row["id"],
        "name": row["name"],
        "shortDescription": row["short_description"],
        "longDescription": row["long_description"],
        "price": float(row["price"]),
        "image": img,
        "meal_image": meal_img,
        "type": row["serving_type"] if row["category"] == "drink" else row["food_type"],
        "foodType": row["food_type"],
        "is_meal_available": row["is_meal_available"],
        "stock": row["stock"],
        "expiry": row["expiry_date"],
        "category": row["category"],
        "section": row["section"],
        "section_order": row["section_order"],
        "display_order": row["display_order"],
        "meal_role": row.get("meal_role"),
        "is_meal_only": bool(row.get("is_meal_only", False)),
    }


# ==========================================================
# IN-MEMORY TTL CACHE CONFIGURATION & STATE
# ==========================================================

DEFAULT_CACHE_TTL = 60.0  # seconds

# Process-local in-memory cache keyed by branch_id:
# {
#     branch_id: {
#         "rows": list[dict],
#         "cached_at": float,
#         "expires_at": float,
#     }
# }
_CACHE = {}
_CACHE_LOCK = threading.RLock()
_STATS_LOCK = threading.Lock()

_CACHE_STATS = {
    "hits": 0,
    "misses": 0,
    "refreshes": 0,
    "errors": 0,
}

# Retained for backwards compatibility with any existing diagnostics
_MENU_ROWS_CACHE = []


# Version counter for cache invalidation across dependent indexes
_MENU_VERSION = 1


def get_menu_version() -> int:
    """Return current menu cache epoch/version counter."""
    with _CACHE_LOCK:
        return _MENU_VERSION


def get_menu_cache_stats() -> dict:
    """Return a snapshot of cache performance metrics."""
    with _STATS_LOCK:
        return dict(_CACHE_STATS)


def clear_menu_cache() -> None:
    """
    Clear all cached menu data and reset cache statistics.
    Useful for testing and explicit cache invalidation.
    """
    global _MENU_ROWS_CACHE, _MENU_VERSION
    with _CACHE_LOCK:
        _CACHE.clear()
        _MENU_ROWS_CACHE = []
        _MENU_VERSION += 1
    with _STATS_LOCK:
        _CACHE_STATS["hits"] = 0
        _CACHE_STATS["misses"] = 0
        _CACHE_STATS["refreshes"] = 0
        _CACHE_STATS["errors"] = 0




# ==========================================================
# BASE QUERY WITH TTL CACHING
# ==========================================================

def fetch_menu_rows(
    branch_id: int = BRANCH_ID,
    force_refresh: bool = False,
    ttl: float = DEFAULT_CACHE_TTL,
):
    """
    Fetch available menu rows for a branch with positive stock.
    Results are cached in-memory with a configurable TTL (default 60s) to avoid
    repeated round-trips to Supabase.
    Thread-safe and coalesces concurrent requests to prevent duplicate fetches.
    """
    global _MENU_ROWS_CACHE

    # 1. Fast-path: Check valid cache outside lock
    if not force_refresh:
        now = time.monotonic()
        entry = _CACHE.get(branch_id)
        if entry is not None and now < entry["expires_at"]:
            with _STATS_LOCK:
                _CACHE_STATS["hits"] += 1
            return [dict(r) for r in entry["rows"]]

    # 2. Synchronized fetch / request coalescing under lock
    with _CACHE_LOCK:
        global _MENU_ROWS_CACHE, _MENU_VERSION
        now = time.monotonic()

        entry = _CACHE.get(branch_id)
        if not force_refresh and entry is not None and now < entry["expires_at"]:
            with _STATS_LOCK:
                _CACHE_STATS["hits"] += 1
            return [dict(r) for r in entry["rows"]]

        with _STATS_LOCK:
            _CACHE_STATS["misses"] += 1
        last_err = None

        for attempt in range(2):
            try:
                response = (
                    supabase.table("inventory")
                    .select(
                        """
                        stock,
                        expiry_date,
                        menu_items!inner(
                            id,
                            name,
                            short_description,
                            long_description,
                            price,
                            image,
                            meal_image,
                            category,
                            food_type,
                            serving_type,
                            section,
                            section_order,
                            display_order,
                            meal_role,
                            is_meal_only,
                            is_meal_available,
                            is_available
                        )
                        """
                    )
                    .eq("branch_id", branch_id)
                    .gt("stock", 0)
                    .execute()
                )

                rows = []
                for item in response.data or []:
                    menu = item["menu_items"]

                    if not menu["is_available"]:
                        continue

                    merged = {**menu}
                    merged["stock"] = item["stock"]
                    merged["expiry_date"] = item["expiry_date"]

                    rows.append(merged)

                if rows:
                    _MENU_ROWS_CACHE = rows
                    _CACHE[branch_id] = {
                        "rows": rows,
                        "serialized": [serialize_menu_item(r) for r in rows],
                        "cached_at": now,
                        "expires_at": now + ttl,
                    }
                    _MENU_VERSION += 1
                    with _STATS_LOCK:
                        _CACHE_STATS["refreshes"] += 1
                return [dict(r) for r in rows]

            except Exception as e:
                last_err = e

        with _STATS_LOCK:
            _CACHE_STATS["errors"] += 1

        # Explicit fallback handling:
        # If a prior cached entry exists, log an explicit warning that stale cached
        # data is being served as a fallback due to Supabase query failure.
        if entry is not None and entry.get("rows"):
            print(
                f"[WARN] fetch_menu_rows Supabase query failed ({last_err}), "
                f"using expired cached rows for branch {branch_id}."
            )
            return [dict(r) for r in entry["rows"]]
        elif _MENU_ROWS_CACHE:
            print(
                f"[WARN] fetch_menu_rows Supabase query failed ({last_err}), "
                f"using cached menu rows."
            )
            return [dict(r) for r in _MENU_ROWS_CACHE]

        raise last_err


# ==========================================================
# CATEGORY NORMALIZATION
# ==========================================================

CATEGORY_MAP = {
    "burger": "burger",
    "burgers": "burger",
    "drink": "drink",
    "drinks": "drink",
    "side": "side",
    "sides": "side",
    "dessert": "dessert",
    "desserts": "dessert",
}


def normalize_category(category):
    if not category or not isinstance(category, str):
        return None
    cat = str(category).strip().lower().replace("-", " ").replace("_", " ")
    return CATEGORY_MAP.get(cat)


# ==========================================================
# MENU SECTIONS
# ==========================================================

def get_menu_sections(category, preference=None):
    norm_cat = normalize_category(category)
    if not norm_cat:
        return []

    rows = [
        r for r in fetch_menu_rows()
        if str(r.get("category", "")).lower() == norm_cat
    ]

    rows.sort(key=lambda x: (x["section_order"], x["display_order"]))

    sections = {}

    for row in rows:

        if row["section"] not in sections:
            sections[row["section"]] = {
                "id": row["section"].lower().replace(" ", "-"),
                "title": row["section"],
                "products": []
            }

        sections[row["section"]]["products"].append(
            serialize_menu_item(row)
        )

    return list(sections.values())


def get_available(branch_id: int = BRANCH_ID):
    """
    Return available serialized menu items with defensive copying.
    Guarantees:
    - Cache freshness: shares TTL and invalidation lifecycle with fetch_menu_rows().
    - Mutation safety: returns fresh dict copies so caller mutations cannot corrupt cache.
    - Consistency: reflects the authoritative database source of truth.
    """
    now = time.monotonic()
    entry = _CACHE.get(branch_id)
    if entry is None or now >= entry.get("expires_at", 0) or "serialized" not in entry:
        rows = fetch_menu_rows(branch_id=branch_id)
        entry = _CACHE.get(branch_id)
        if entry is None or "serialized" not in entry:
            return [serialize_menu_item(r) for r in rows]

    return [dict(item) for item in entry["serialized"]]




# ==========================================================
# CATEGORY ITEMS
# ==========================================================

def _normalize_key(val: str) -> str:
    return str(val or "").strip().lower().replace("-", " ").replace("_", " ")


def get_category(category):

    rows = fetch_menu_rows()
    norm_cat = _normalize_key(category)

    if norm_cat in ("veg", "non veg"):
        rows = [r for r in rows if _normalize_key(r.get("food_type")) == norm_cat]
    else:
        cat_target = "side" if norm_cat in ("side", "sides") else norm_cat
        rows = [r for r in rows if _normalize_key(r.get("category")).rstrip("s") == cat_target.rstrip("s")]

    return [serialize_menu_item(r) for r in rows]


# ==========================================================
# PRODUCT LOOKUP
# ==========================================================

def get_product(item_name):

    rows = fetch_menu_rows()

    for row in rows:
        if row["name"].lower() == item_name.lower():
            return serialize_menu_item(row)

    return None


# ==========================================================
# ADD TO CART (READ ONLY)
# ==========================================================

def add_to_cart(item_name):

    product = get_product(item_name)

    if not product:
        return {
            "success": False,
            "message": "Item not found."
        }

    if product["stock"] <= 0:
        return {
            "success": False,
            "message": "Item out of stock."
        }

    return {
        "success": True,
        "item": product
    }


# ==========================================================
# INVENTORY (DISABLED - READ ONLY)
# ==========================================================

def deduct_inventory(item_id, quantity):
    return {
        "success": False,
        "message": "Read-only database connection."
    }