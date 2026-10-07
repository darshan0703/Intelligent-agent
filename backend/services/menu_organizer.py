"""
backend/services/menu_organizer.py
Dynamic Menu Organization for 'View All' Screens:
1. M01 Dietary Lock: Drops non-veg if veg preference active.
2. M05 Budget Ceiling & Dynamic Mindset:
   - Low Budget cart: Floats Value/Affordable sections & items to the top.
   - Premium cart: Floats Gourmet/Whopper/Premium sections & items to the top.
3. M06 Condiment Gating:
   - Drops price == 0 meal-only items (e.g. Peri Peri Chicken Boneless 2Pc).
   - Dips at last only if NO fries/finger food in cart.
   - If fries in cart, Dips is placed right next to Fries!
4. M07 Cart Exclusion:
   - Items already in cart are moved to the VERY LAST of their section.
"""

from typing import List, Dict, Any, Optional
from services.modules.m06_condiment_gating import has_finger_food_in_cart, is_meal_only_item


def compute_budget_mindset(cart: Optional[List[Dict[str, Any]]]) -> str:
    """
    Analyzes the cart items and determines the customer's budget mindset:
    - 'low_budget': cart contains value/budget items (<= 100) or avg <= 140
    - 'premium': cart contains premium/gourmet items or avg >= 180
    - 'neutral': cart is empty or moderate
    """
    if not cart:
        return "neutral"

    prices = []
    for item in cart:
        p = item.get("unitPrice") or item.get("price")
        if p is not None:
            try:
                prices.append(float(p))
            except (ValueError, TypeError):
                pass
        elif item.get("subtotal") and item.get("quantity"):
            try:
                prices.append(float(item["subtotal"]) / max(1, int(item["quantity"])))
            except (ValueError, TypeError):
                pass

    if not prices:
        return "neutral"

    avg_price = sum(prices) / len(prices)
    min_price = min(prices)

    if avg_price <= 140.0 or min_price <= 100.0:
        return "low_budget"
    elif avg_price >= 180.0:
        return "premium"
    return "neutral"


def is_item_in_cart(prod: Dict[str, Any], cart: Optional[List[Dict[str, Any]]]) -> bool:
    """Returns True if the product is already present in the cart or inside a meal combo."""
    if not cart:
        return False

    p_id = prod.get("id")
    p_name = str(prod.get("name", "")).strip().lower()

    for c in cart:
        c_id = c.get("id")
        if c_id is not None and p_id is not None and str(c_id) == str(p_id):
            return True

        c_name = str(c.get("name", "")).strip().lower()
        if c_name and (c_name == p_name or p_name in c_name or c_name in p_name):
            return True

        # Check inside meal combo
        if c.get("type") == "meal":
            main = c.get("main_item") or c.get("burger") or {}
            side = c.get("side") or {}
            drink = c.get("drink") or {}
            if (
                str(main.get("id")) == str(p_id)
                or str(side.get("id")) == str(p_id)
                or str(drink.get("id")) == str(p_id)
            ):
                return True
            if main.get("name") and p_name == str(main.get("name")).strip().lower():
                return True
            if side.get("name") and p_name == str(side.get("name")).strip().lower():
                return True
            if drink.get("name") and p_name == str(drink.get("name")).strip().lower():
                return True

    return False


# Section priority maps based on category and budget mindset
SECTION_PRIORITY_MAPS = {
    "burger": {
        "low_budget": {
            "value burgers": 10,
            "wraps and tacos": 20,
            "crazy deals": 30,
            "whoppers": 40,
            "peri peri": 50,
            "premium burgers": 60,
        },
        "premium": {
            "premium burgers": 10,
            "whoppers": 20,
            "peri peri": 30,
            "crazy deals": 40,
            "value burgers": 50,
            "wraps and tacos": 60,
        },
    },
    "side": {
        "low_budget": {
            "fries": 10,
            "veggie sides": 20,
            "nuggets": 30,
            "dips": 99,
        },
        "premium": {
            "nuggets": 10,
            "fries": 20,
            "veggie sides": 30,
            "dips": 99,
        },
    },
    "drink": {
        "low_budget": {
            "cold drinks": 10,
            "floats": 20,
            "bk café": 30,
            "bk cafe": 30,
            "shakes": 40,
        },
        "premium": {
            "shakes": 10,
            "bk café": 20,
            "bk cafe": 20,
            "floats": 30,
            "cold drinks": 40,
        },
    },
    "dessert": {
        "low_budget": {
            "soft serve": 10,
            "waffle cones": 20,
            "sundaes": 30,
            "special desserts": 40,
        },
        "premium": {
            "special desserts": 10,
            "sundaes": 20,
            "waffle cones": 30,
            "soft serve": 40,
        },
    },
}


def organize_menu_sections(
    category: str,
    raw_sections: List[Dict[str, Any]],
    preference: Optional[str] = None,
    cart: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """
    Applies smart arrangement across full menu sections:
    1. Filters price == 0 meal components.
    2. Applies dietary lock (veg).
    3. Low-budget cart -> Value sections & items first.
    4. Premium cart -> Whoppers/Premium sections & items first.
    5. In Sides: Dips at the very end unless fries/finger-food is in cart (then right after Fries).
    6. Cart exclusion at last: items already in cart are moved to the end of each section.
    """
    cart = cart or []
    mindset = compute_budget_mindset(cart)
    cat_lower = category.lower().strip()
    has_fries = has_finger_food_in_cart(cart)

    pri_map = SECTION_PRIORITY_MAPS.get(cat_lower, {}).get(mindset, {})
    pref_norm = str(preference or "").lower().strip()

    organized_sections = []

    for idx, sec in enumerate(raw_sections):
        products = sec.get("products", [])

        # 1. Filter out meal-only items (price == 0)
        filtered_products = [p for p in products if not is_meal_only_item(p)]

        # 2. Dietary Lock (M01)
        if pref_norm == "veg":
            filtered_products = [
                p for p in filtered_products
                if "veg" in str(p.get("foodType") or p.get("type", "")).lower()
                and "non" not in str(p.get("foodType") or p.get("type", "")).lower()
                and not any(nw in str(p.get("name", "")).lower() for nw in ["chicken", "wings", "nugget", "boneless", "mutton", "fish"])
            ]
        elif "non" in pref_norm:
            filtered_products = [
                p for p in filtered_products
                if "non" in str(p.get("foodType") or p.get("type", "")).lower()
                or any(nw in str(p.get("name", "")).lower() for nw in ["chicken", "wings", "nugget", "boneless"])
            ]

        if not filtered_products:
            continue

        # 3. M07 Cart Exclusion: partition into unadded vs already in cart
        unadded = [p for p in filtered_products if not is_item_in_cart(p, cart)]
        in_cart = [p for p in filtered_products if is_item_in_cart(p, cart)]

        # 4. M05 Budget Ceiling item sorting for unadded items
        if mindset == "low_budget":
            unadded.sort(key=lambda p: float(p.get("price") or 0))
        elif mindset == "premium":
            unadded.sort(key=lambda p: float(p.get("price") or 0), reverse=True)

        # Place carted items at the VERY END of the section
        final_products = unadded + in_cart

        sec_copy = dict(sec)
        sec_copy["products"] = final_products

        # 5. Section ordering
        title_key = str(sec.get("title", "")).lower().strip()
        pri = pri_map.get(title_key)

        if pri is None:
            if mindset == "neutral":
                pri = (idx + 1) * 10
            else:
                avg_sec_price = sum(float(p.get("price") or 0) for p in final_products) / max(1, len(final_products))
                pri = avg_sec_price if mindset == "low_budget" else (1000 - avg_sec_price)

        # Specific rule: Dips at last only if no fries added
        if cat_lower in ("side", "sides") and "dip" in title_key:
            if has_fries:
                pri = 15  # directly after Fries (10)
            else:
                pri = 999  # very last section

        organized_sections.append((pri, sec_copy))

    # Sort sections by priority score
    organized_sections.sort(key=lambda x: x[0])
    return [s[1] for s in organized_sections]
