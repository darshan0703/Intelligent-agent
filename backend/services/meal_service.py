import re
from datetime import date
from database import supabase
from services.modules.m01_dietary_lock import get_item_food_type
from services.recommendation import _is_stock_eligible, _is_expiry_eligible


def _sanitize_error(e) -> str:
    """
    Sanitizes error messages before logging to ensure that sensitive values
    (database passwords, API tokens, credentials, secrets) are redacted.
    """
    msg = str(e) if e is not None else ""
    msg = re.sub(r"://([^:]+):([^@]+)@", r"://\1:***@", msg)
    msg = re.sub(r"\b(token|secret|pass(?:word)?|credential|apikey|key)s?[=:\s]+[^\s,;&]+", r"\1: [REDACTED]", msg, flags=re.IGNORECASE)
    msg = re.sub(r"Bearer\s+[A-Za-z0-9\-\._~\+\/]+=*", "Bearer [REDACTED]", msg, flags=re.IGNORECASE)
    msg = re.sub(r"SYNTHETIC_TEST_[A-Za-z0-9_]+", "[REDACTED]", msg)
    return msg


MEAL_UPGRADE_PRICES = {
    "medium": 140,
    "large": 145,
}


def _parse_price(val):
    """
    Safely extracts and parses price or extra_price into a non-negative float.
    Returns:
      - float >= 0.0 if valid numeric or numeric string
      - None if missing, None, negative, or malformed string ('N/A', 'invalid')
    """
    if val is None:
        return None
    if isinstance(val, dict):
        val = val.get("amount") or val.get("price")
    try:
        f = float(val)
        if f < 0.0:
            return None
        return f
    except (ValueError, TypeError):
        return None


def _is_item_eligible(item, today=None):
    """
    Validates stock and expiry eligibility for an item:
    - Positive stock required.
    - Zero, negative, or missing stock is ineligible.
    - Missing/None expiry is considered eligible (non-perishable/untracked).
    - Expired or malformed expiry is ineligible.
    """
    if not isinstance(item, dict):
        return False
    if today is None:
        today = date.today()

    inv = item.get("inventory")
    stock = item.get("stock")
    expiry = item.get("expiry") or item.get("expiry_date")

    if stock is None:
        if isinstance(inv, dict):
            stock = inv.get("stock")
        elif isinstance(inv, list) and inv:
            stock = inv[0].get("stock")

    if expiry is None:
        if isinstance(inv, dict):
            expiry = inv.get("expiry_date") or inv.get("expiry")
        elif isinstance(inv, list) and inv:
            expiry = inv[0].get("expiry_date") or inv[0].get("expiry")

    eligibility_dict = {
        "stock": stock,
        "expiry": expiry,
    }

    return _is_stock_eligible(eligibility_dict) and _is_expiry_eligible(eligibility_dict, today)


def serialize_meal_option(item, extra_price, is_default=False):
    parsed_price = _parse_price(item.get("price"))
    if parsed_price is None:
        parsed_price = 0.0
    parsed_extra = _parse_price(extra_price)
    if parsed_extra is None:
        parsed_extra = 0.0

    return {
        "id": item.get("id"),
        "name": item.get("name"),
        "image": item.get("image"),
        "price": parsed_price,
        "extra_price": parsed_extra,
        "is_default": is_default,
        "section": item.get("section"),
        "foodType": item.get("food_type"),
    }


def is_veg_meal_item(item):
    """
    Canonical vegetarian check leveraging M01 normalize_food_type.
    """
    return get_item_food_type(item) == "veg"


def get_drink_sections_order(burger_price, default_section, available_sections, is_morning=None):
    """
    Computes dynamic drink section priority order based on time of day and burger price.
    - If burger < 100:
      Morning: BK Café, Cold Drinks, Shakes, Floats
      Else:    Shakes, Cold Drinks, BK Café, Floats
    - If burger >= 100:
      Morning: BK Café, Shakes, Cold Drinks, Floats
      Else:    Shakes, BK Café, Cold Drinks, Floats
    - The default drink's section is placed first so it is immediately visible & active with its red border,
      followed by the rest in exact priority order.
    """
    if is_morning is None:
        from datetime import datetime
        is_morning = (5 <= datetime.now().hour < 12)

    try:
        b_price = float(burger_price) if burger_price is not None else 0.0
    except (ValueError, TypeError):
        b_price = 0.0

    if b_price < 100.0:
        if is_morning:
            target_order = ["BK Café", "Cold Drinks", "Shakes", "Floats"]
        else:
            target_order = ["Shakes", "Cold Drinks", "BK Café", "Floats"]
    else:
        if is_morning:
            target_order = ["BK Café", "Shakes", "Cold Drinks", "Floats"]
        else:
            target_order = ["Shakes", "BK Café", "Cold Drinks", "Floats"]

    matched = []
    avail_list = list(available_sections or [])

    for tgt in target_order:
        norm_tgt = tgt.lower().replace("é", "e").replace("caffe", "cafe").replace("caf", "cafe").strip()
        for act in avail_list:
            norm_act = act.lower().replace("é", "e").replace("caffe", "cafe").replace("caf", "cafe").strip()
            if norm_tgt == norm_act or norm_tgt in norm_act or norm_act in norm_tgt:
                if act not in matched:
                    matched.append(act)

    for act in avail_list:
        if act not in matched:
            matched.append(act)

    # Keep sections in their natural dynamic priority order (do not force default to index 0)

    return matched


def organize_side_options(options, food_preference=None, cart=None, main_product=None):
    """
    Dynamic Side Options Ranking:
    1. If product/pref is Veg -> Veg sides first, then Non-Veg sides.
       If product/pref is Non-Veg -> Non-Veg sides first, then Veg sides.
    2. Within each section: Higher price first (extra_price descending).
       - For Peri Peri burgers: Peri Peri Fries takes precedence over Saucy Fries.
       - Otherwise: Saucy Fries (₹40) > Peri Peri Fries (₹30) > Fries (₹0) > Veg Pizza Puff (₹0).
    3. The default side (is_default=True) retains its is_default flag, but stays in its natural sorted position
       (NOT forced to index 0).
    4. Soft cart exclusion: Items already in cart are moved to the end of their group.
    """
    from services.menu_organizer import is_item_in_cart

    burger_name = str(main_product.get("name") or "").lower() if main_product else ""
    burger_flavor = str(main_product.get("flavor_profile") or "").lower() if main_product else ""
    is_peri_peri_burger = ("peri peri" in burger_name) or ("peri peri" in burger_flavor)

    burger_ft = get_item_food_type(main_product) if main_product else ""
    user_pref = str(food_preference or "").lower().strip()

    if user_pref == "veg":
        primary_diet = "veg"
    elif "non" in user_pref:
        primary_diet = "non_veg"
    else:
        primary_diet = "veg" if burger_ft == "veg" else "non_veg"

    def side_key(item):
        in_cart = 1 if is_item_in_cart(item, cart) else 0

        item_is_veg = (get_item_food_type(item) == "veg")
        if primary_diet == "veg":
            diet_group = 0 if item_is_veg else 1
        else:
            diet_group = 0 if not item_is_veg else 1

        extra = _parse_price(item.get("extra_price")) or 0.0
        item_name = str(item.get("name") or "").lower()

        # Flavor priority for Peri Peri burger vs Saucy fries:
        # If Peri Peri burger: Peri Peri fries first.
        # If normal burger (e.g. Veg Whopper): Saucy fries first.
        flavor_priority = 0
        if is_peri_peri_burger and "peri peri" in item_name:
            flavor_priority = -1000
        elif not is_peri_peri_burger and "saucy" in item_name:
            flavor_priority = -500

        # Potato fries priority over puffs at zero extra price
        tie_break = 0
        if "fries" in item_name:
            tie_break = -10

        # Higher price first: -extra (higher extra_price comes first)
        # Notice: is_default is NOT used in sorting, so default stays in natural position
        return (in_cart, diet_group, flavor_priority, -extra, tie_break)

    return sorted(options, key=side_key)


def organize_drink_options(options, food_preference=None, cart=None, main_product=None):
    """
    Dynamic Drink Options Ranking:
    Within each drink section, sort by higher price/extra_price first,
    preserving default drink's is_default flag in its natural position.
    """
    from services.menu_organizer import is_item_in_cart

    def drink_key(item):
        in_cart = 1 if is_item_in_cart(item, cart) else 0
        extra = _parse_price(item.get("extra_price")) or 0.0
        price = _parse_price(item.get("price")) or 0.0
        return (in_cart, -extra, -price)

    return sorted(options, key=drink_key)


def organize_meal_options(options, food_preference=None, cart=None, main_product=None):
    """
    Universal entry point for meal option ranking.
    Routes to organize_side_options or organize_drink_options based on meal_role.
    """
    if not options:
        return []
    # If contains sides, route to organize_side_options
    sample = options[0]
    cat = str(sample.get("section") or sample.get("category") or "").lower()
    role = str(sample.get("meal_role") or "").lower()

    if role == "drink" or "drink" in cat or "shake" in cat or "caf" in cat:
        return organize_drink_options(options, food_preference=food_preference, cart=cart, main_product=main_product)
    return organize_side_options(options, food_preference=food_preference, cart=cart, main_product=main_product)


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
            .select("*, inventory(stock, expiry_date)")
            .eq("id", default_row["default_side_id"])
            .execute()
        )

        drink = (
            supabase.table("menu_items")
            .select("*, inventory(stock, expiry_date)")
            .eq("id", default_row["default_drink_id"])
            .execute()
        )

        if not side.data or not drink.data:
            return None

        side_item = side.data[0]
        drink_item = drink.data[0]

        # Inventory and availability validation
        if not side_item.get("is_available") or not _is_item_eligible(side_item):
            return None
        if not drink_item.get("is_available") or not _is_item_eligible(drink_item):
            return None

        return {
            "side": side_item,
            "drink": drink_item,
        }
    except Exception as e:
        print(f"Error getting default meal: {_sanitize_error(e)}")
        return None


def get_upgrade_options(meal_size, role=None):
    try:
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
                    is_available,
                    inventory (
                        stock,
                        expiry_date
                    )
                )
            """)
            .eq("meal_size", meal_size)
            .eq("is_enabled", True)
            .execute()
        )

        options = []
        today = date.today()

        for row in response.data or []:
            item = row.get("menu_items")

            if not item:
                continue

            if role is not None and item.get("meal_role") != role:
                continue

            if not item.get("is_available"):
                continue

            if not _is_item_eligible(item, today):
                continue

            # Never silently interpret an invalid extra_price as a valid zero-price upgrade
            parsed_extra = _parse_price(row.get("extra_price"))
            if parsed_extra is None:
                continue

            parsed_price = _parse_price(item.get("price"))
            if parsed_price is None:
                continue

            options.append({
                **item,
                "price": parsed_price,
                "extra_price": parsed_extra,
            })

        return options
    except Exception as e:
        print(f"[WARN] Error fetching upgrade options: {_sanitize_error(e)}")
        return []


def build_meal(item_id, meal_size, food_preference=None, cart=None):
    try:
        burger_res = (
            supabase.table("menu_items")
            .select("*, inventory(stock, expiry_date)")
            .eq("id", item_id)
            .execute()
        )

        if not burger_res.data:
            return None

        burger_data = burger_res.data[0]

        # Only items with meal_role == 'main' can be converted into meal combos
        if burger_data.get("meal_role") != "main" or not burger_data.get("is_meal_available"):
            return None

        if not burger_data.get("is_available") or not _is_item_eligible(burger_data):
            return None

        burger_price = _parse_price(burger_data.get("price"))
        if burger_price is None:
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

        # Organize options with dietary priority, price ranking, and Peri Peri flavor harmony
        side_options = organize_side_options(side_options, food_preference=effective_pref, cart=cart, main_product=burger_data)
        drink_options = organize_drink_options(drink_options, food_preference=effective_pref, cart=cart, main_product=burger_data)

        # Dynamic drink sections ordering
        avail_sections = list(set(d.get("section") for d in drink_options if d.get("section")))
        drink_sections = get_drink_sections_order(
            burger_price=burger_price,
            default_section=drink_default.get("section"),
            available_sections=avail_sections,
        )

        upgrade_price = _parse_price(MEAL_UPGRADE_PRICES.get(meal_size, 140))
        if upgrade_price is None:
            upgrade_price = 140.0

        side_price = _parse_price(side_default.get("price")) or 0.0
        drink_price = _parse_price(drink_default.get("price")) or 0.0

        return {
            "size": meal_size,

            "burger": {
                "id": burger_data["id"],
                "name": burger_data["name"],
                "price": burger_price,
                "image": burger_data.get("meal_image") or burger_data.get("image"),
                "foodType": burger_data.get("food_type"),
            },

            "side": {
                "id": side_default["id"],
                "name": side_default["name"],
                "price": side_price,
                "extra_price": 0.0,
                "image": side_default.get("image"),
                "foodType": side_default.get("food_type"),
                "section": side_default.get("section"),
            },

            "drink": {
                "id": drink_default["id"],
                "name": drink_default["name"],
                "price": drink_price,
                "extra_price": 0.0,
                "image": drink_default.get("image"),
                "foodType": drink_default.get("food_type"),
                "section": drink_default.get("section"),
            },

            "burger_price": burger_price,
            "upgrade_price": upgrade_price,

            "meal_price": burger_price + upgrade_price,

            "side_options": side_options,
            "drink_options": drink_options,
            "drink_sections": drink_sections,
        }
    except Exception as e:
        print(f"Error building meal for item {item_id}: {_sanitize_error(e)}")
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
        print(f"Error getting meal options for item {item_id}: {_sanitize_error(e)}")
        return {
            "success": False,
            "product_id": item_id,
            "is_meal_available": False,
            "message": "Failed to load meal options.",
        }