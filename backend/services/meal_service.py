from database import supabase

MEAL_UPGRADE_PRICES = {
    "medium": 140,
    "large": 145
}


def serialize_meal_option(item, extra_price, is_default=False):
    return {
        "id": item["id"],
        "name": item["name"],
        "image": item["image"],
        "price": float(item["price"]),
        "extra_price": float(extra_price),
        "is_default": is_default,
        "section": item["section"]
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

    return {
        "side": side.data,
        "drink": drink.data
    }

def serialize_meal_option(menu_item, extra_price, is_default=False):

    return {
        "id": menu_item.id,
        "name": menu_item.name,
        "image": menu_item.image,
        "price": float(menu_item.price),
        "extra_price": float(extra_price),
        "is_default": is_default,
        "section": menu_item.section
    }

def get_side_options(
    db: Session,
    meal_size: str,
    default_side=None,
):
    if default_side is None:
        default_data = get_default_meal(db, meal_size)
        default_side = default_data["side"] if default_data else None

    default_side_id = default_side.id if default_side else None
    options = []

    upgrades = (
        db.query(MealUpgradeRule, MenuItem)
        .join(
            MenuItem,
            MenuItem.id == MealUpgradeRule.item_id
        )
        .filter(
            MealUpgradeRule.meal_size == meal_size,
            MealUpgradeRule.is_enabled == True,
            MenuItem.meal_role == "side",
            MenuItem.is_available == True
        )
        .all()
    )

    for rule, item in upgrades:
        options.append(
            serialize_meal_option(
                item,
                rule.extra_price,
                item.id == default_side_id
            )
        )

    return options

def get_drink_options(
    db: Session,
    meal_size: str,
    default_drink=None,
):
    if default_drink is None:
        default_data = get_default_meal(db, meal_size)
        default_drink = default_data["drink"] if default_data else None

    default_drink_id = default_drink.id if default_drink else None
    options = []

    upgrades = (
        db.query(MealUpgradeRule, MenuItem)
        .join(
            MenuItem,
            MenuItem.id == MealUpgradeRule.item_id
        )
        .filter(
            MealUpgradeRule.meal_size == meal_size,
            MealUpgradeRule.is_enabled == True,
            MenuItem.meal_role == "drink",
            MenuItem.is_available == True
        )
        .all()
    )

    for rule, item in upgrades:
        options.append(
            serialize_meal_option(
                item,
                rule.extra_price,
                item.id == default_drink_id
            )
        )

    return options

def build_meal(
    db: Session,
    item_id: int,
    meal_size: str,
    burger=None,
):
    if burger is None:
        burger = (
            db.query(MenuItem)
            .filter(
                MenuItem.id == item_id,
                MenuItem.meal_role == "main"
            )
            .first()
        )

    if not burger or burger.meal_role != "main":
        return None

    defaults = get_default_meal(meal_size)

    if not defaults or not defaults.get("side") or not defaults.get("drink"):
        return None

    side_default = defaults["side"]
    drink_default = defaults["drink"]

    side_options = get_side_options(
        db,
        meal_size,
        default_side=defaults["side"]
    )

    drink_options = get_drink_options(
        db,
        meal_size,
        default_drink=defaults["drink"]
    )

    return {
        "size": meal_size,
        "burger": {
            "id": burger.id,
            "name": burger.name,
            "price": float(burger.price),
            "image": burger.meal_image,
            "foodType": burger.food_type
        },
        "side": {
            "id": side_default["id"],
            "name": side_default["name"],
            "price": float(side_default["price"]),
            "image": side_default["image"]
        },
        "drink": {
            "id": drink_default["id"],
            "name": drink_default["name"],
            "price": float(drink_default["price"]),
            "image": drink_default["image"]
        },
        "burger_price": float(burger.price),
        "upgrade_price": float(upgrade_price),
        "meal_price": float(burger.price) + float(upgrade_price),
        "side_options": side_options,
        "drink_options": drink_options
    }


def get_meal_options(item_id: int):
    db: Session = SessionLocal()

    try:
        product = (
            db.query(MenuItem)
            .filter(MenuItem.id == item_id)
            .first()
        )

        if not product:
            return None

        if not product.is_meal_available:
            return {
                "success": True,
                "product_id": product.id,
                "product_name": product.name,
                "is_meal_available": False
            }

        medium = build_meal(
            db,
            item_id,
            "medium",
            burger=product
        )

        large = build_meal(
            db,
            item_id,
            "large",
            burger=product
        )

    if not product.data["is_meal_available"]:
        return {
            "success": True,
            "product_id": product.data["id"],
            "product_name": product.data["name"],
            "is_meal_available": False
        }

    return {
        "success": True,
        "product_id": product.data["id"],
        "product_name": product.data["name"],
        "is_meal_available": True,
        "meals": {
            "medium": build_meal(item_id, "medium"),
            "large": build_meal(item_id, "large")
        }
    }