from database import supabase


MEAL_UPGRADE_PRICES = {
    "medium": 140,
    "large": 145,
}


def serialize_meal_option(item, extra_price, is_default=False):
    return {
        "id": item["id"],
        "name": item["name"],
        "image": item["image"],
        "price": float(item["price"]),
        "extra_price": float(extra_price),
        "is_default": is_default,
        "section": item["section"],
        "foodType": item.get("food_type"),
    }


def is_veg_meal_item(item):
    ft = str(item.get("foodType") or item.get("food_type") or "").lower().strip()
    name = str(item.get("name", "")).lower()
    if "non" in ft or any(k in name for k in ["chicken", "wings", "nugget", "boneless", "mutton", "fish"]):
        return False
    return True


def organize_meal_options(options, food_preference=None, cart=None):
    """
    Organizes meal upgrade options:
    - If food_preference is 'veg': Veg items first, Non-veg items after.
    - If food_preference is 'non_veg': Non-veg items first, Veg items after.
    - Cart Exclusion: items already in cart are moved to the VERY LAST!
    - Within each group: default first, then lower extra_price first.
    """
    from services.menu_organizer import is_item_in_cart
    cart = cart or []
    pref = str(food_preference or "veg").lower().strip()

    def option_key(item):
        in_cart = 1 if is_item_in_cart(item, cart) else 0
        is_veg = is_veg_meal_item(item)

        if pref == "veg":
            diet_pri = 0 if is_veg else 1
        elif "non" in pref:
            diet_pri = 1 if is_veg else 0
        else:
            diet_pri = 0 if is_veg else 1

        is_def = 0 if item.get("is_default") else 1
        extra = float(item.get("extra_price") or 0)
        return (in_cart, diet_pri, is_def, extra)

    return sorted(options, key=option_key)


def get_default_meal(meal_size):
    try:
        default = (
            supabase.table("meal_defaults")
            .select("default_side_id, default_drink_id")
            .eq("meal_size", meal_size)
            .execute()
        )

        if not default.data:
            return None

        default_row = default.data[0]

        side = (
            supabase.table("menu_items")
            .select("*")
            .eq("id", default_row["default_side_id"])
            .execute()
        )

        drink = (
            supabase.table("menu_items")
            .select("*")
            .eq("id", default_row["default_drink_id"])
            .execute()
        )

        if not side.data or not drink.data:
            return None

        return {
            "side": side.data[0],
            "drink": drink.data[0],
        }
    except Exception as e:
        print(f"Error getting default meal: {e}")
        return None


def get_upgrade_options(meal_size, role=None):
    response = (
        supabase.table("meal_upgrade_rules")
        .select("""
            extra_price,
            menu_items!inner(
                id,
                name,
                image,
                price,
                section,
                meal_role,
                food_type,
                is_available
            )
        """)
        .eq("meal_size", meal_size)
        .eq("is_enabled", True)
        .execute()
    )

    options = []

    for row in response.data or []:
        item = row.get("menu_items")

        if not item:
            continue

        if role is not None and item.get("meal_role") != role:
            continue

        if not item.get("is_available"):
            continue

        options.append({
            **item,
            "extra_price": row["extra_price"],
        })

    return options


def build_meal(item_id, meal_size, food_preference=None, cart=None):
    try:
        burger_res = (
            supabase.table("menu_items")
            .select("*")
            .eq("id", item_id)
            .execute()
        )

        if not burger_res.data:
            return None

        burger_data = burger_res.data[0]

        # Only items with meal_role == 'main' can be converted into meal combos
        if burger_data.get("meal_role") != "main" or not burger_data.get("is_meal_available"):
            return None

        defaults = get_default_meal(meal_size)

        if not defaults:
            return None

        side_default = defaults["side"]
        drink_default = defaults["drink"]

        # Context-aware dietary preference:
        # If user explicitly selected 'veg' or 'non_veg', respect it.
        # If user is in 'both'/unset, infer directly from the burger's food_type!
        user_pref = str(food_preference or "").lower().strip()
        burger_ft = str(burger_data.get("food_type") or "").lower().strip()
        if user_pref == "veg" or "non" in user_pref:
            effective_pref = "veg" if user_pref == "veg" else "non_veg"
        else:
            effective_pref = "veg" if burger_ft == "veg" else "non_veg"

        upgrade_options = get_upgrade_options(meal_size)

        side_options = [
            serialize_meal_option(
                item,
                item["extra_price"],
                item["id"] == side_default["id"],
            )
            for item in upgrade_options
            if item.get("meal_role") == "side"
        ]

        drink_options = [
            serialize_meal_option(
                item,
                item["extra_price"],
                item["id"] == drink_default["id"],
            )
            for item in upgrade_options
            if item.get("meal_role") == "drink"
        ]

        # Organize options with dietary priority and cart exclusion
        side_options = organize_meal_options(side_options, food_preference=effective_pref, cart=cart)
        drink_options = organize_meal_options(drink_options, food_preference=effective_pref, cart=cart)

        upgrade_price = MEAL_UPGRADE_PRICES.get(meal_size, 140)

        return {
            "size": meal_size,

            "burger": {
                "id": burger_data["id"],
                "name": burger_data["name"],
                "price": float(burger_data["price"]),
                "image": burger_data.get("meal_image") or burger_data.get("image"),
                "foodType": burger_data.get("food_type"),
            },

            "side": {
                "id": side_default["id"],
                "name": side_default["name"],
                "price": float(side_default["price"]),
                "image": side_default.get("image"),
                "foodType": side_default.get("food_type"),
            },

            "drink": {
                "id": drink_default["id"],
                "name": drink_default["name"],
                "price": float(drink_default["price"]),
                "image": drink_default.get("image"),
                "foodType": drink_default.get("food_type"),
            },

            "burger_price": float(burger_data["price"]),
            "upgrade_price": float(upgrade_price),

            "meal_price": (
                float(burger_data["price"])
                + float(upgrade_price)
            ),

            "side_options": side_options,
            "drink_options": drink_options,
        }
    except Exception as e:
        print(f"Error building meal for item {item_id}: {e}")
        return None


def get_meal_options(item_id, food_preference=None, cart=None):
    try:
        product_res = (
            supabase.table("menu_items")
            .select("*")
            .eq("id", item_id)
            .execute()
        )

        if not product_res.data:
            return {
                "success": False,
                "product_id": item_id,
                "is_meal_available": False,
                "message": "Product not found",
            }

        product = product_res.data[0]

        if not product.get("is_meal_available") or product.get("meal_role") != "main":
            return {
                "success": True,
                "product_id": product["id"],
                "product_name": product["name"],
                "is_meal_available": False,
            }

        medium_meal = build_meal(item_id, "medium", food_preference=food_preference, cart=cart)
        large_meal = build_meal(item_id, "large", food_preference=food_preference, cart=cart)

        if not medium_meal and not large_meal:
            return {
                "success": True,
                "product_id": product["id"],
                "product_name": product["name"],
                "is_meal_available": False,
            }

        return {
            "success": True,
            "product_id": product["id"],
            "product_name": product["name"],
            "is_meal_available": True,
            "meals": {
                "medium": medium_meal,
                "large": large_meal,
            },
        }
    except Exception as e:
        print(f"Error getting meal options for item {item_id}: {e}")
        return {
            "success": True,
            "product_id": item_id,
            "is_meal_available": False,
            "message": str(e),
        }