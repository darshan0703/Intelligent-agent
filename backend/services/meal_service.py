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
    }


def get_default_meal(meal_size):
    default = (
        supabase.table("meal_defaults")
        .select("default_side_id, default_drink_id")
        .eq("meal_size", meal_size)
        .single()
        .execute()
    )

    if not default.data:
        return None

    side = (
        supabase.table("menu_items")
        .select("*")
        .eq("id", default.data["default_side_id"])
        .single()
        .execute()
    )

    drink = (
        supabase.table("menu_items")
        .select("*")
        .eq("id", default.data["default_drink_id"])
        .single()
        .execute()
    )

    if not side.data or not drink.data:
        return None

    return {
        "side": side.data,
        "drink": drink.data,
    }


def get_upgrade_options(meal_size, role=None):
    """
    Fetch meal upgrade rules only once for a meal size.

    If role is supplied, filter the result in Python.
    This avoids making duplicate Supabase requests for
    side and drink options during the same meal build.
    """

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


def build_meal(item_id, meal_size):
    burger = (
        supabase.table("menu_items")
        .select("*")
        .eq("id", item_id)
        .eq("meal_role", "main")
        .single()
        .execute()
    )

    if not burger.data:
        return None

    defaults = get_default_meal(meal_size)

    if not defaults:
        return None

    side_default = defaults["side"]
    drink_default = defaults["drink"]

    # ==========================================================
    # FETCH ALL UPGRADE OPTIONS ONCE
    # ==========================================================

    upgrade_options = get_upgrade_options(meal_size)

    # ==========================================================
    # SPLIT THEM LOCALLY
    # ==========================================================

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

    upgrade_price = MEAL_UPGRADE_PRICES[meal_size]

    return {
        "size": meal_size,

        "burger": {
            "id": burger.data["id"],
            "name": burger.data["name"],
            "price": float(burger.data["price"]),
            "image": burger.data["meal_image"],
            "foodType": burger.data["food_type"],
        },

        "side": {
            "id": side_default["id"],
            "name": side_default["name"],
            "price": float(side_default["price"]),
            "image": side_default["image"],
        },

        "drink": {
            "id": drink_default["id"],
            "name": drink_default["name"],
            "price": float(drink_default["price"]),
            "image": drink_default["image"],
        },

        "burger_price": float(burger.data["price"]),
        "upgrade_price": float(upgrade_price),

        "meal_price": (
            float(burger.data["price"])
            + float(upgrade_price)
        ),

        "side_options": side_options,
        "drink_options": drink_options,
    }


def get_meal_options(item_id):
    product = (
        supabase.table("menu_items")
        .select("*")
        .eq("id", item_id)
        .single()
        .execute()
    )

    if not product.data:
        return None

    if not product.data["is_meal_available"]:
        return {
            "success": True,
            "product_id": product.data["id"],
            "product_name": product.data["name"],
            "is_meal_available": False,
        }

    return {
        "success": True,
        "product_id": product.data["id"],
        "product_name": product.data["name"],
        "is_meal_available": True,
        "meals": {
            "medium": build_meal(item_id, "medium"),
            "large": build_meal(item_id, "large"),
        },
    }