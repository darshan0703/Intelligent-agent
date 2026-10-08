from typing import Dict, Any, List

def _get_item_price(item: Dict[str, Any]) -> float:
    p = item.get("price")
    if p is None:
        p = item.get("original_price")
    if isinstance(p, dict):
        p = p.get("amount") or p.get("price")
    try:
        return float(p) if p is not None else 0.0
    except (TypeError, ValueError):
        return 0.0

def _get_item_category(item: Dict[str, Any]) -> str:
    cat = item.get("category")
    if cat:
        return str(cat).lower()
    try:
        from services.menu_service import get_product
        p = get_product(item.get("name", ""))
        if p and p.get("category"):
            return str(p["category"]).lower()
    except Exception:
        pass
    return ""

def apply_price_ceiling(
    candidates: List[Dict[str, Any]],
    cart: List[Dict[str, Any]],
    default_max_ratio: float = 1.5
) -> List[Dict[str, Any]]:
    if not cart:
        return candidates

    mains = [item for item in cart if _get_item_category(item) in ("burger", "burgers", "main")]
    if mains:
        anchor_item = max(mains, key=_get_item_price)
    else:
        anchor_item = max(cart, key=_get_item_price)
        
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
        price = float(item.get("price") or item.get("original_price", 0))
        item_category = _get_item_category(item)
        
        # M5 SPEC: Only applies to CROSS-SELLS. 
        # If the user is browsing the same category as the anchor (e.g. browsing burgers while having a burger),
        # they are exploring main options, so M5 shouldn't brutally restrict them.
        if (anchor_category and item_category == anchor_category) or price <= ceiling:
            survivors.append(item)

    if len(survivors) >= 2:
        return survivors

    return candidates

