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
# BASE QUERY
# ==========================================================

_MENU_ROWS_CACHE = []

def fetch_menu_rows():
    global _MENU_ROWS_CACHE
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
                .eq("branch_id", BRANCH_ID)
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
            return rows
        except Exception as e:
            last_err = e

    if _MENU_ROWS_CACHE:
        print(f"[WARN] fetch_menu_rows Supabase query failed ({last_err}), using cached menu rows.")
        return _MENU_ROWS_CACHE

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


# ==========================================================
# AVAILABLE ITEMS
# ==========================================================

def get_available():
    return [serialize_menu_item(r) for r in fetch_menu_rows()]


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