from typing import Dict, Any, List

def _get_item_price(item: Dict[str, Any]) -> float:
    p = item.get("price")
    if p is None:
        p = item.get("original_price")
    if p is None:
        p = item.get("unitPrice")
    if isinstance(p, dict):
        p = p.get("amount") or p.get("price")
    try:
        return float(p) if p is not None else 0.0
    except (TypeError, ValueError):
        return 0.0

def _get_item_category(item: Dict[str, Any]) -> str:
    cat = item.get("category")
    if cat:
        return str(cat).strip().lower()
    return ""

def _extract_cart_items(cart: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Decomposes the cart into individual items for budget evaluation:
    - Normal standalone items contribute their own price and category.
    - Meal combos contribute their individual component items (main_item, side, drink).
    - The meal's bundle price (unitPrice / subtotal) is never used as an anchor.
    """
    items = []
    for item in cart:
        if not isinstance(item, dict):
            continue

        # Check if item is a composite meal combo
        is_meal = (
            item.get("type") == "meal"
            or isinstance(item.get("main_item"), dict)
            or isinstance(item.get("side"), dict)
            or isinstance(item.get("drink"), dict)
        )

        if is_meal:
            main = item.get("main_item") or item.get("burger")
            if isinstance(main, dict):
                cat = main.get("category") or "burger"
                items.append({**main, "category": cat})

            side = item.get("side")
            if isinstance(side, dict):
                cat = side.get("category") or "side"
                items.append({**side, "category": cat})

            drink = item.get("drink")
            if isinstance(drink, dict):
                cat = drink.get("category") or "drink"
                items.append({**drink, "category": cat})
        else:
            items.append(item)

    return items

def apply_price_ceiling(
    candidates: List[Dict[str, Any]],
    cart: List[Dict[str, Any]],
    default_max_ratio: float = 1.5
) -> List[Dict[str, Any]]:
    if not cart:
        return candidates

    eval_items = _extract_cart_items(cart)
    if not eval_items:
        return candidates

    mains = [item for item in eval_items if _get_item_category(item) in ("burger", "burgers", "main")]
    if mains:
        anchor_item = max(mains, key=_get_item_price)
    else:
        anchor_item = max(eval_items, key=_get_item_price)
        
    anchor_price = _get_item_price(anchor_item)
    anchor_category = _get_item_category(anchor_item)

    if anchor_price <= 0:
        return candidates

    if anchor_price < 100:
        max_ratio = 2.0  
    elif anchor_price < 200:
        max_ratio = 1.75
    else:
        max_ratio = default_max_ratio

    ceiling = anchor_price * max_ratio
    survivors = []
    
    for item in candidates:
        price = _get_item_price(item)
        item_category = _get_item_category(item)
        
        # M5 SPEC: Only applies to CROSS-SELLS. 
        # If the user is browsing the same category as the anchor (e.g. browsing burgers while having a burger),
        # they are exploring main options, so M5 shouldn't brutally restrict them.
        if (anchor_category and item_category == anchor_category) or price <= ceiling:
            survivors.append(item)

    if len(survivors) >= 2:
        return survivors

    return candidates

