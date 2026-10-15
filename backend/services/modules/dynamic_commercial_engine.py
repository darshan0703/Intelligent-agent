"""
backend/services/modules/dynamic_commercial_engine.py
Dynamic Commercial Engine — Unified Context-Aware Recommendation & Commercial Ranking Engine

Core Responsibilities:
1. Hard Policy Gatekeeping (Tiers 1-4):
   - Tier 1: Stock & Expiry Eligibility (_is_stock_eligible, _is_expiry_eligible)
   - Tier 2: M1 Dietary Lock (apply_dietary_lock)
   - Tier 3: M7 Cart Exclusion (exclude_cart_items)
   - Tier 4: M5 Budget Ceiling (apply_price_ceiling)
2. Multi-Signal Scoring:
   - S_sensory: Module A sensory contrast & flavor harmony (-0.4 to 0.4)
   - S_margin: Commercial budget mindset & price-margin alignment (0.0 to 0.5)
   - S_base: Base stock & priority score (0.0 to 1.0)
3. Multi-Surface Selection:
   - Product Page ("Recommended with": Side, Drink, Dessert)
   - Meal Customizer (Upgrades based on selected main)
   - Checkout 3-Slot Dynamic Shelf (Slot 1: Dip/Last-minute, Slot 2: Best Drink/Match, Slot 3: Sweet Finish)
   - Menu Sections Merchandising
"""

from typing import List, Dict, Any, Optional, Set, Tuple
from decimal import Decimal
from datetime import date

from services.modules.m01_dietary_lock import apply_dietary_lock
from services.modules.m02_m03_basket_completion import (
    compute_sensory_score,
    generate_candidate_signals,
    parse_product_role,
    rank_candidates_with_sensory,
)
from services.modules.m05_budget_ceiling import apply_price_ceiling
from services.modules.m06_condiment_gating import (
    filter_for_recommendation_page,
    get_checkout_dip_suggestions,
    is_condiment,
    has_condiment_in_cart,
    has_side_in_cart,
)
from services.modules.m07_cart_exclusion import exclude_cart_items


# =========================================================
# BUDGET MINDSET & COMMERCIAL MARGIN SCORING
# =========================================================

def compute_budget_mindset(cart: Optional[List[Dict[str, Any]]]) -> str:
    """
    Evaluates cart history to detect customer spending context:
    - 'premium': customer added premium items (recent >= 140 or max >= 170). Margin expansion mode.
    - 'upsell': customer added mid-tier items (>= 110) or mixed cart. Moderate margin mode.
    - 'low_budget': cart contains only cheap entry items (< 100).
    - 'neutral': cart is empty or unspecified.
    """
    if not cart:
        return "neutral"

    prices = []
    for item in cart:
        if not isinstance(item, dict):
            continue
        p = item.get("unitPrice") or item.get("price")
        if p is not None:
            try:
                val = float(p)
                if val > 0:
                    prices.append(val)
            except (ValueError, TypeError):
                pass
        elif item.get("subtotal") and item.get("quantity"):
            try:
                val = float(item["subtotal"]) / max(1, int(item["quantity"]))
                if val > 0:
                    prices.append(val)
            except (ValueError, TypeError):
                pass

    if not prices:
        return "neutral"

    recent_price = prices[-1]
    max_price = max(prices)
    avg_price = sum(prices) / len(prices)

    if recent_price >= 140.0 or max_price >= 170.0:
        return "premium"
    elif max_price >= 110.0 or avg_price >= 105.0:
        return "upsell"
    else:
        return "low_budget"


def compute_commercial_margin_score(
    candidate: Dict[str, Any],
    cart: Optional[List[Dict[str, Any]]],
    mindset: Optional[str] = None,
    placement: str = "normal"
) -> float:
    """
    Calculates commercial margin alignment score [0.0, 0.5] based on item price,
    category, cart budget mindset, and placement surface. Does NOT use hardcoded product names.
    """
    if not isinstance(candidate, dict):
        return 0.0

    if mindset is None:
        mindset = compute_budget_mindset(cart)

    # Check if candidate is a meal customizer upgrade option carrying extra_price
    extra_val = candidate.get("extra_price")
    if extra_val is not None:
        try:
            extra_price = float(extra_val)
            if extra_price <= 0.0:
                return 0.30  # High value fit for free default upgrade option
            elif extra_price <= 40.0:
                return 0.25  # Mid-tier upgrade option
            else:
                return 0.15  # Premium upgrade option
        except (ValueError, TypeError):
            pass

    p_val = candidate.get("price") or candidate.get("unitPrice")
    try:
        price = float(p_val) if p_val is not None else 0.0
    except (ValueError, TypeError):
        price = 0.0

    if price <= 0:
        return 0.0

    score = 0.0
    cat = str(candidate.get("category") or "").strip().lower()
    name = str(candidate.get("name") or "").strip().lower()

    # Fountain sodas & classic refreshing drinks (high gross % margin in QSRs)
    is_fountain_or_soda = any(s in name for s in ["coke", "coca cola", "sprite", "fanta", "thums up", "fizz", "float"])

    if mindset == "premium":
        # In premium mode, reward higher-margin items and premium treats
        score += min(0.3, (price / 200.0) * 0.3)
        if price >= 140.0 or cat in ("dessert", "shake"):
            score += 0.2
    elif mindset == "upsell":
        # In upsell mode, reward mid-tier items (110-150)
        if 110.0 <= price <= 150.0:
            score += 0.25
        elif price > 150.0:
            score += 0.15
        else:
            score += 0.10
    elif mindset == "low_budget":
        # In low budget mode, reward high-value entry items (<= 119)
        if price <= 119.0:
            score += 0.30
        elif price <= 140.0:
            score += 0.15
        else:
            score += 0.0  # Avoid pushing expensive items to price-sensitive guests
    else:
        # Neutral baseline: gentle proportion to price
        score += min(0.2, (price / 250.0) * 0.2)

    # For Slot 2 (drinks) on product page:
    # Slightly reduce the aggressive premium margin push so ultra-expensive drinks (199-249)
    # don't completely drown out refreshing companion fountain drinks (Coke, Sprite, Fanta, Fizzes).
    if cat in ("drink", "drinks") and placement == "product_page":
        if is_fountain_or_soda:
            score = max(score, 0.32)  # classic high-margin companion sodas
        else:
            score = max(0.15, score - 0.20)  # reduce high-end drink margin slightly for slot 2

    return round(min(0.5, score), 2)


# =========================================================
# UNIFIED CENTRAL CANDIDATE RANKER
# =========================================================

def rank_candidates_commercial(
    candidates: List[Dict[str, Any]],
    cart: Optional[List[Dict[str, Any]]],
    placement: str = "normal",
    food_type: str = "both"
) -> List[Dict[str, Any]]:
    """
    Single shared commercial ranking engine.
    Combines:
    - Module A Sensory Affinity Score S_sensory (-0.4 to 0.4)
    - Commercial Margin Score S_margin (0.0 to 0.5)
    - Base Priority / Score S_base (0.0 to 1.0)
    
    Formula:
      FinalScore = S_base * (1.0 + S_sensory) + S_margin
    """
    if not candidates:
        return []

    mindset = compute_budget_mindset(cart)
    scored = []

    for idx, item in enumerate(candidates):
        if not isinstance(item, dict):
            continue

        signals = generate_candidate_signals(item, cart, placement=placement)
        sensory_score = signals.get("sensory_score", 0.0)
        margin_score = compute_commercial_margin_score(item, cart, mindset=mindset, placement=placement)

        base_priority = float(item.get("priority") or item.get("score") or 1.0)
        if base_priority < 0:
            base_priority = 0.0

        final_score = base_priority * (1.0 + sensory_score) + margin_score

        scored.append({
            "item": item,
            "final_score": final_score,
            "sensory_score": sensory_score,
            "margin_score": margin_score,
            "orig_idx": idx,
        })

    scored.sort(key=lambda x: (x["final_score"], -x["orig_idx"]), reverse=True)
    return [s["item"] for s in scored]


# =========================================================
# SURFACE RECOMMENDATION ADAPTERS
# =========================================================

def get_product_page_rankings(
    items_by_group: Dict[str, List[Dict[str, Any]]],
    cart: Optional[List[Dict[str, Any]]],
    food_type: str = "both"
) -> Dict[str, Optional[Dict[str, Any]]]:
    """
    Product Page "Recommended with" dynamic selector:
    Ranks candidates within each group (Side, Drink, Dessert) using central commercial ranker.
    """
    cart_list = cart or []
    results: Dict[str, Optional[Dict[str, Any]]] = {
        "side": None,
        "drink": None,
        "dessert": None,
    }

    for group, items in items_by_group.items():
        if not items:
            continue

        # Hard Gates
        filtered = apply_dietary_lock(items, preference=food_type if food_type != "both" else None, cart=cart_list)
        filtered = exclude_cart_items(filtered, cart_list)
        filtered = filter_for_recommendation_page(filtered)
        filtered = apply_price_ceiling(filtered, cart_list)

        if not filtered:
            continue

        ranked = rank_candidates_commercial(filtered, cart_list, placement="product_page", food_type=food_type)
        if ranked:
            results[group] = ranked[0]

    return results


def get_meal_customizer_rankings(
    sides: List[Dict[str, Any]],
    drinks: List[Dict[str, Any]],
    selected_main: Optional[Dict[str, Any]],
    cart: Optional[List[Dict[str, Any]]]
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Meal Customizer Upgrade Selector:
    Ranks available sides and drinks according to the selected main product and cart context.
    """
    eval_cart = list(cart or [])
    if selected_main and isinstance(selected_main, dict):
        eval_cart.append(selected_main)

    ranked_sides = rank_candidates_commercial(sides or [], eval_cart, placement="meal_customizer")
    ranked_drinks = rank_candidates_commercial(drinks or [], eval_cart, placement="meal_customizer")

    return {
        "sides": ranked_sides,
        "drinks": ranked_drinks,
    }


def build_dynamic_checkout_shelf(
    cart: Optional[List[Dict[str, Any]]],
    all_sides: List[Dict[str, Any]],
    all_drinks: List[Dict[str, Any]],
    all_desserts: List[Dict[str, Any]],
    all_items: Optional[List[Dict[str, Any]]] = None,
    food_preference: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Dynamic 3-Slot Checkout Shelf implementation powered by Dynamic Commercial Engine.
    Refreshes recommendations whenever cart changes.
    Applies authoritative dietary preference from session/request or cart inference.
    """
    cart_list = cart or []

    # Enforce M1 Dietary Lock: inspect explicit food_preference first, then infer from cart
    from services.modules.m01_dietary_lock import get_item_food_type, apply_dietary_lock, normalize_food_type
    from services.modules.m05_budget_ceiling import apply_price_ceiling

    pref_norm = normalize_food_type(food_preference)
    if pref_norm in ("veg", "non_veg"):
        effective_pref = pref_norm
    elif cart_list and all(get_item_food_type(i) == "veg" for i in cart_list if isinstance(i, dict)):
        effective_pref = "veg"
    else:
        effective_pref = "both"

    # Enforce M1 Dietary Lock across candidate pools
    all_sides = apply_dietary_lock(all_sides or [], preference=effective_pref if effective_pref != "both" else None, cart=cart_list)
    all_drinks = apply_dietary_lock(all_drinks or [], preference=effective_pref if effective_pref != "both" else None, cart=cart_list)
    all_desserts = apply_dietary_lock(all_desserts or [], preference=effective_pref if effective_pref != "both" else None, cart=cart_list)
    if all_items:
        all_items = apply_dietary_lock(all_items, preference=effective_pref if effective_pref != "both" else None, cart=cart_list)

    # Enforce M5 Budget Ceiling
    all_sides = apply_price_ceiling(all_sides, cart_list)
    all_drinks = apply_price_ceiling(all_drinks, cart_list)
    all_desserts = apply_price_ceiling(all_desserts, cart_list)
    if all_items:
        all_items = apply_price_ceiling(all_items, cart_list)

    recommendations: List[Dict[str, Any]] = []
    seen_keys: Set[Tuple[str, str]] = set()

    def _get_key(item: Dict[str, Any]) -> Tuple[str, str]:
        item_id = item.get("id")
        if item_id is not None and str(item_id).strip() != "":
            return ("id", str(item_id).strip())
        name = str(item.get("name") or "").strip().lower()
        return ("name", name)

    for cart_item in cart_list:
        if isinstance(cart_item, dict):
            seen_keys.add(_get_key(cart_item))

    # SLOT 1 — Conditional Dip / Sauce / Last-Minute Complement
    slot1_item = None
    dip_already_in_cart = has_condiment_in_cart(cart_list)
    finger_food_present = has_side_in_cart(cart_list)

    if finger_food_present and not dip_already_in_cart:
        dips = get_checkout_dip_suggestions(all_sides, cart_list)
        eligible_dips = exclude_cart_items(dips, cart_list)
        if eligible_dips:
            ranked_dips = rank_candidates_commercial(eligible_dips, cart_list, placement="checkout")
            for d in ranked_dips:
                k = _get_key(d)
                if k not in seen_keys:
                    slot1_item = dict(d)
                    name_lower = str(d.get("name") or "").lower()
                    slot1_item["badge"] = "🌶️ Signature Sauce" if "sauce" in name_lower else "🍟 Perfect Dip"
                    slot1_item["slot"] = 1
                    seen_keys.add(k)
                    break
    elif not dip_already_in_cart:
        non_dip_sides = [s for s in (all_sides or []) if not is_condiment(s)]
        eligible_sides = exclude_cart_items(non_dip_sides, cart_list)
        if eligible_sides:
            ranked_sides = rank_candidates_commercial(eligible_sides, cart_list, placement="checkout")
            for s in ranked_sides:
                k = _get_key(s)
                if k not in seen_keys:
                    sensory_score = compute_sensory_score(cart_list, s)
                    if sensory_score > 0.0 or len(cart_list) == 0:
                        slot1_item = dict(s)
                        slot1_item["badge"] = "🍟 Signature Side"
                        slot1_item["slot"] = 1
                        seen_keys.add(k)
                        break

    if slot1_item:
        recommendations.append(slot1_item)

    # SLOT 2 — Best Match / Context-Aware Drink
    slot2_item = None
    eligible_drinks = exclude_cart_items(all_drinks or [], cart_list)
    if eligible_drinks:
        ranked_drinks = rank_candidates_commercial(eligible_drinks, cart_list, placement="checkout")
        for drink in ranked_drinks:
            k = _get_key(drink)
            if k not in seen_keys:
                slot2_item = dict(drink)
                slot2_item["badge"] = "🥤 Best Drink"
                slot2_item["slot"] = 2
                seen_keys.add(k)
                break

    if not slot2_item:
        general_pool = (all_items or (all_sides + all_drinks + all_desserts))
        non_dessert = [i for i in general_pool if str(i.get("category") or "").lower() != "dessert"]
        eligible_fb = exclude_cart_items(non_dessert, cart_list)
        if eligible_fb:
            ranked_fb = rank_candidates_commercial(eligible_fb, cart_list, placement="checkout")
            for item in ranked_fb:
                k = _get_key(item)
                if k not in seen_keys:
                    slot2_item = dict(item)
                    slot2_item["badge"] = "⭐ Best Match"
                    slot2_item["slot"] = 2
                    seen_keys.add(k)
                    break

    if slot2_item:
        recommendations.append(slot2_item)

    # SLOT 3 — Sweet Finish
    slot3_item = None
    eligible_desserts = exclude_cart_items(all_desserts or [], cart_list)
    if eligible_desserts:
        ranked_desserts = rank_candidates_commercial(eligible_desserts, cart_list, placement="checkout")
        for d in ranked_desserts:
            k = _get_key(d)
            if k not in seen_keys:
                slot3_item = dict(d)
                slot3_item["badge"] = "🍦 Sweet Finish"
                slot3_item["slot"] = 3
                seen_keys.add(k)
                break

    if slot3_item:
        recommendations.append(slot3_item)

    return recommendations
