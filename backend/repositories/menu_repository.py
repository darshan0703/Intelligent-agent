import time
from database import supabase

BRANCH_ID = 1

_MENU_CACHE = None
_MENU_CACHE_TIME = 0
MENU_CACHE_TTL_SECONDS = 60

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
    }


# ==========================================================
# BASE QUERY
# ==========================================================

def fetch_menu_rows(force_refresh=False):
    global _MENU_CACHE, _MENU_CACHE_TIME
    now = time.time()
    if not force_refresh and _MENU_CACHE is not None and (now - _MENU_CACHE_TIME) < MENU_CACHE_TTL_SECONDS:
        return _MENU_CACHE

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
                is_meal_available,
                is_available
            )
            """
        )
        .eq("branch_id", BRANCH_ID)
        .gt("stock", 0)
        .execute()
    )

    rows = []

    for item in response.data:
        menu = item["menu_items"]

        if not menu["is_available"]:
            continue

        merged = {**menu}
        merged["stock"] = item["stock"]
        merged["expiry_date"] = item["expiry_date"]

        rows.append(merged)

    _MENU_CACHE = rows
    _MENU_CACHE_TIME = now
    return rows


# ==========================================================
# MENU SECTIONS
# ==========================================================

def get_menu_sections(category, preference=None):

    rows = [
        r for r in fetch_menu_rows()
        if r["category"].lower() == category.lower()
    ]

    if preference:
        pref = str(preference).lower().replace("-", " ").replace("_", " ").strip()
        if pref == "veg":
            rows = [
                r for r in rows
                if "veg" in str(r.get("food_type", "")).lower()
                and "non" not in str(r.get("food_type", "")).lower()
            ]
        elif "non" in pref:
            rows = [
                r for r in rows
                if "non" in str(r.get("food_type", "")).lower()
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


# ==========================================================
# AVAILABLE ITEMS
# ==========================================================

def get_available():
    return [serialize_menu_item(r) for r in fetch_menu_rows()]


# ==========================================================
# CATEGORY ITEMS
# ==========================================================

def get_category(category):

    rows = fetch_menu_rows()

    if category in ["veg", "non_veg"]:
        rows = [r for r in rows if r["food_type"].lower() == category.lower()]
    else:
        rows = [r for r in rows if r["category"].lower() == category.lower()]

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