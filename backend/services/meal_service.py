from httpx import options
from sqlalchemy.orm import Session

from database import SessionLocal
from models import MenuItem, MealDefault, MealUpgradeRule

MEAL_UPGRADE_PRICES = {
    "medium": 140,
    "large": 145
}

def get_default_meal(db: Session, meal_size: str):

    default = (
        db.query(MealDefault)
        .filter(MealDefault.meal_size == meal_size)
        .first()
    )

    if not default:
        return None

    side = (
        db.query(MenuItem)
        .filter(MenuItem.id == default.default_side_id)
        .first()
    )

    drink = (
        db.query(MenuItem)
        .filter(MenuItem.id == default.default_drink_id)
        .first()
    )

    return {
        "side": side,
        "drink": drink
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
    meal_size: str
):

    default = get_default_meal(
        db,
        meal_size
    )["side"]

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
                item.id == default.id
            )

        )

    return options

def get_drink_options(
    db: Session,
    meal_size: str
):

    default = get_default_meal(
        db,
        meal_size
    )["drink"]

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
    print("\n========== QUERY RESULT ==========")
    print(f"Meal Size: {meal_size}")
    print(f"Rows: {len(upgrades)}")

    for rule, item in upgrades:
        print(
            item.id,
            item.name,
            item.meal_role,
            rule.extra_price
        )

    for rule, item in upgrades:

        options.append(

            serialize_meal_option(
                item,
                rule.extra_price,
                item.id == default.id
            )

        )

        print("\n========== OPTIONS ==========")
    print(f"Options: {len(options)}")

    for option in options:
        print(option)

    return options

def build_meal(
    db: Session,
    item_id: int,
    meal_size: str
):

    burger = (
        db.query(MenuItem)
        .filter(
            MenuItem.id == item_id,
            MenuItem.meal_role == "main"
        )
        .first()
    )

    if not burger:
        return None

    defaults = get_default_meal(
        db,
        meal_size
    )

    if not defaults:
        return None

    upgrade_price = MEAL_UPGRADE_PRICES.get(meal_size)

    if upgrade_price is None:
        return None

    side_options = get_side_options(
        db,
        meal_size
    )

    drink_options = get_drink_options(
        db,
        meal_size
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
            "id": defaults["side"].id,
            "name": defaults["side"].name,
            "price": float(defaults["side"].price),
            "image": defaults["side"].image
        },

        "drink": {
            "id": defaults["drink"].id,
            "name": defaults["drink"].name,
            "price": float(defaults["drink"].price),
            "image": defaults["drink"].image
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
            "medium"
        )

        large = build_meal(
            db,
            item_id,
            "large"
        )

        return {
            "success": True,
            "product_id": product.id,
            "product_name": product.name,
            "is_meal_available": True,
            "meals": {
                "medium": medium,
                "large": large
            }
        }

    finally:
        db.close()
