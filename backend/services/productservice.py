from schemas import KioskResponse, ScreenTypes
from services.menu_service import get_product, get_category
from services.modules.m01_dietary_lock import get_item_food_type, normalize_food_type
from services.modules.m07_cart_exclusion import exclude_cart_items
from services.modules.m06_condiment_gating import filter_for_recommendation_page


def get_product_recommendations(product, cart=None, limit=3, preference=None):
    """
    Generate cross-category recommendations for a given product.
    - For Burger  -> pick Sides, Drinks, Desserts
    - For Side    -> pick Burgers, Drinks, Desserts
    - For Drink   -> pick Burgers, Sides, Desserts
    - For Dessert -> pick Burgers, Sides, Drinks

    Applies:
    1. Module 7 Cart Exclusion: drop any items already present in the cart.
    2. Module 6 Condiment Gating: drop dips from product page shelves (dips belong on checkout).
    3. Module 1 Dietary Lock / Smart Preference:
       - If viewing a veg product, or active preference is veg, or cart is 100% veg:
         STRICT VEG ONLY (non-veg items strictly eradicated).
       - If viewing a non-veg product, or preference is non-veg:
         SMART BLEND: can show both veg and non-veg, but prioritizes non-veg items first.
    """
    if not product:
        return []

    cat = str(product.get("category") or "").strip().lower()

    if cat in ("burger", "burgers"):
        target_cats = ["side", "drink", "dessert"]
    elif cat in ("side", "sides"):
        target_cats = ["burger", "drink", "dessert"]
    elif cat in ("drink", "drinks"):
        target_cats = ["burger", "side", "dessert"]
    elif cat in ("dessert", "desserts"):
        target_cats = ["burger", "side", "drink"]
    else:
        target_cats = ["burger", "side", "drink"]

    # Determine effective dietary preference
    product_food_type = get_item_food_type(product)
    eff_pref = normalize_food_type(preference)

    if not eff_pref:
        if product_food_type:
            eff_pref = product_food_type
        elif cart:
            if all(get_item_food_type(item) == "veg" for item in cart):
                eff_pref = "veg"
            else:
                eff_pref = "both"
        else:
            eff_pref = "both"

    recommendations = []
    seen_ids = {product.get("id")}
    seen_names = {str(product.get("name", "")).strip().lower()}

    def filter_and_sort_candidates(items):
        # 1. Exclude items already in cart & filter out condiments/dips (M6 Gating)
        candidates = filter_for_recommendation_page(exclude_cart_items(items, cart=cart or []))

        if eff_pref == "veg":
            # Strict veg only
            filtered = [i for i in candidates if get_item_food_type(i) == "veg"]
        elif eff_pref == "non_veg":
            # Smart blend: prioritize non-veg first, then veg
            non_veg_list = [i for i in candidates if get_item_food_type(i) == "non_veg"]
            veg_list = [i for i in candidates if get_item_food_type(i) == "veg"]
            filtered = non_veg_list + veg_list
        else:
            filtered = candidates

        # Module A: Apply soft sensory contrast ranking within the fixed category slot
        from services.modules.m02_m03_basket_completion import rank_candidates_with_sensory
        cart_ctx = (cart or []) + ([product] if product else [])
        return rank_candidates_with_sensory(filtered, cart=cart_ctx, placement="normal")

    # Pick 1 item from each target category
    for target_cat in target_cats:
        cat_items = get_category(target_cat) or []
        candidates = filter_and_sort_candidates(cat_items)
        for item in candidates:
            item_id = item.get("id")
            item_name = str(item.get("name", "")).strip().lower()
            if item_id not in seen_ids and item_name not in seen_names:
                recommendations.append(item)
                seen_ids.add(item_id)
                seen_names.add(item_name)
                break
        if len(recommendations) >= limit:
            break

    # If limit is not reached (e.g. fewer categories available), backfill
    if len(recommendations) < limit:
        for target_cat in target_cats:
            cat_items = get_category(target_cat) or []
            candidates = filter_and_sort_candidates(cat_items)
            for item in candidates:
                item_id = item.get("id")
                item_name = str(item.get("name", "")).strip().lower()
                if item_id not in seen_ids and item_name not in seen_names:
                    recommendations.append(item)
                    seen_ids.add(item_id)
                    seen_names.add(item_name)
                    if len(recommendations) >= limit:
                        break
            if len(recommendations) >= limit:
                break

    return recommendations[:limit]


def handle_product(item_name, conversation_context):

    product = get_product(item_name)

    if not product:
        return KioskResponse(
            screen=ScreenTypes.HOME,
            message="Sorry, I couldn't find that item."
        )

    # ==========================================
    # START A NEW PRODUCT / MEAL INTERACTION
    # ==========================================

    conversation_context["meal_flow"] = {
        "item_id": product["id"],
        "status": "pending"
    }

    # ==========================================
    # RECOMMENDATIONS (CROSS-CATEGORY + CART EXCLUSION)
    # ==========================================

    cart = conversation_context.get("cart", [])
    pref = conversation_context.get("food_preference")
    recommendations = get_product_recommendations(product, cart=cart, preference=pref)

    return KioskResponse(
        screen=ScreenTypes.PRODUCT,
        data={
            "product": product,
            "recommendations": recommendations
        }
    )