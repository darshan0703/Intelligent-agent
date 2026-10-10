"""
backend/services/modules/m02_m03_basket_completion.py
Module A: Role-Aware Basket Completion & Sensory Pairing Engine

Core Responsibilities:
1. Structured Role & Metadata Parsing:
   Extracts `meal_role`, `subrole`, `satisfies_roles` from product dictionary.
   Missing or empty metadata returns 'unassigned' without inventing roles.
2. Soft Sensory Affinity Scoring:
   Evaluates temperature, texture, and flavor profile contrast between cart items
   and candidates. Returns a soft additive score [0.0, 1.0]. Missing sensory metadata
   returns a neutral score of 0.0 without penalizing or eliminating valid candidates.
3. Structured Candidate Signal Generation:
   Emits explicit signal dictionaries for downstream central coordination:
   { candidate_id, candidate_name, role_fit, sensory_score, confidence, reason_codes }
4. Slot-Aware Candidate Ranking:
   - Product Page Placement: Ranks candidates WITHIN fixed category groups (Side, Drink, Dessert)
     using base score + sensory score.
   - Checkout Placement:
     * Slot 1: Gated Dip / Complement (M6 checkout cross-sell flow).
     * Slot 2: Best Match (High-Confidence Complement — NOT meal-gap detection).
     * Slot 3: Sweet Finish / Treat (Sundaes, Lava Cakes).
"""

from typing import List, Dict, Any, Optional, Set, Tuple


# =========================================================
# CONFIGURABLE SENSORY CONTRAST AFFINITY MATRIX
# =========================================================

SENSORY_AFFINITY_MATRIX: Dict[str, Dict[str, float]] = {
    # Temperature contrast (Hot cart item -> Cold candidate)
    "temp_hot_cold": 0.30,
    # Texture contrast (Crunchy cart item -> Smooth dip/sauce candidate)
    "texture_crunchy_smooth": 0.35,
    # Flavor contrast (Spicy cart item -> Sweet/Creamy candidate)
    "flavor_spicy_sweet": 0.25,
    # Flavor complementary (Savory main -> Refreshing beverage)
    "flavor_savory_refreshing": 0.20,
    # Flavor harmony / theme matching (Peri Peri <-> Peri Peri, Cheese <-> Cheese)
    "flavor_harmony": 0.30,
}


# =========================================================
# STRUCTURED ROLE & METADATA PARSER
# =========================================================

def parse_product_role(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    Safely extracts structured role and metadata from a product dictionary.
    Does NOT invent or hallucinate missing roles.
    
    Returns:
      {
        "meal_role": str | "unassigned",
        "subrole": str | "unassigned",
        "satisfies_roles": list[str],
        "category": str,
        "temperature": str | None,
        "texture": str | None,
        "flavor_profile": str | None
      }
    """
    if not isinstance(item, dict):
        return {
            "meal_role": "unassigned",
            "subrole": "unassigned",
            "satisfies_roles": [],
            "category": "unassigned",
            "temperature": None,
            "texture": None,
            "flavor_profile": None,
        }

    cat = str(item.get("category") or item.get("section") or "").strip().lower()

    # Explicit metadata fields
    meal_role = item.get("meal_role") or item.get("mealRole")
    subrole = item.get("subrole") or item.get("sub_role")
    satisfies = item.get("satisfies_roles") or item.get("satisfiesRoles")

    # If satisfies_roles is specified as a string, normalize to list
    if isinstance(satisfies, str):
        satisfies = [s.strip().lower() for s in satisfies.split(",") if s.strip()]
    elif not isinstance(satisfies, list):
        satisfies = []

    # Derive canonical meal_role if missing using category classification (no hardcoded product names)
    if not meal_role:
        if cat in ("burger", "burgers", "mains"):
            meal_role = "main"
        elif cat in ("side", "sides", "snack", "snacks", "fries"):
            meal_role = "side"
        elif cat in ("drink", "drinks", "beverage", "beverages", "beverage & cafe", "cafe"):
            meal_role = "drink"
        elif cat in ("dessert", "desserts", "sweet", "sweets"):
            meal_role = "dessert"
        elif cat in ("sauce", "sauces", "dip", "dips"):
            meal_role = "sauce"
        else:
            meal_role = "unassigned"

    # Normalize meal_role & subrole
    meal_role = str(meal_role).strip().lower() if meal_role else "unassigned"
    subrole = str(subrole).strip().lower() if subrole else "unassigned"

    # Ensure satisfies_roles includes meal_role if valid
    if meal_role != "unassigned" and meal_role not in satisfies:
        satisfies.append(meal_role)

    # Shakes: rich drinks that satisfy 'drink' and optionally 'dessert' for sensory affinity,
    # but do NOT count as a solid dessert that suppresses sundaes.
    name_lower = str(item.get("name") or "").strip().lower()
    if "shake" in name_lower or "frappe" in name_lower:
        if "drink" not in satisfies:
            satisfies.append("drink")

    return {
        "meal_role": meal_role,
        "subrole": subrole,
        "satisfies_roles": satisfies,
        "category": cat,
        "temperature": item.get("temperature"),
        "texture": item.get("texture"),
        "flavor_profile": item.get("flavor_profile"),
    }


# =========================================================
# SOFT SENSORY AFFINITY MATRIX & FLAVOR HARMONY
# =========================================================

def compute_sensory_score(cart: Optional[List[Dict[str, Any]]], candidate: Dict[str, Any]) -> float:
    """
    Computes a soft sensory score [0.0, 1.0] evaluating sensory contrast AND flavor harmony
    between items in cart and a candidate. Missing attributes return a neutral score of 0.0
    without penalizing or eliminating valid candidates.
    """
    if not cart or not isinstance(candidate, dict):
        return 0.0

    cand_meta = parse_product_role(candidate)
    cand_temp = str(cand_meta.get("temperature") or candidate.get("temperature") or "").lower()
    cand_texture = str(cand_meta.get("texture") or candidate.get("texture") or "").lower()
    cand_flavor = str(cand_meta.get("flavor_profile") or candidate.get("flavor_profile") or candidate.get("flavor") or "").lower()
    cand_name = str(candidate.get("name") or "").lower()
    cand_cat = cand_meta["category"]

    # Name-based heuristic fallbacks when explicit sensory attributes are absent
    if not cand_temp:
        if any(w in cand_name or w in cand_cat for w in ["iced", "cold", "sundae", "shake", "coca cola", "coke", "sprite", "fanta", "ice"]):
            cand_temp = "cold"
        elif any(w in cand_name or w in cand_cat for w in ["hot", "warm", "coffee", "latte", "espresso", "lava"]):
            cand_temp = "hot"

    if not cand_texture:
        if any(w in cand_name or w in cand_cat for w in ["fries", "nuggets", "rings", "crunchy", "crispy"]):
            cand_texture = "crunchy"
        elif any(w in cand_name or w in cand_cat for w in ["dip", "sauce", "sundae", "mousse"]):
            cand_texture = "smooth"

    if not cand_flavor:
        if any(w in cand_name or w in cand_cat for w in ["peri peri", "fiery", "spicy", "chilli"]):
            cand_flavor = "spicy"
        elif any(w in cand_name or w in cand_cat for w in ["chocolate", "sweet", "sundae", "shake", "kitkat", "mango", "berry"]):
            cand_flavor = "sweet"
        elif any(w in cand_name or w in cand_cat for w in ["burger", "whopper", "nuggets"]):
            cand_flavor = "savory"

    total_sensory = 0.0

    for cart_item in cart:
        if not isinstance(cart_item, dict):
            continue
        cart_meta = parse_product_role(cart_item)
        cart_temp = str(cart_meta.get("temperature") or cart_item.get("temperature") or "").lower()
        cart_texture = str(cart_meta.get("texture") or cart_item.get("texture") or "").lower()
        cart_flavor = str(cart_meta.get("flavor_profile") or cart_item.get("flavor_profile") or cart_item.get("flavor") or "").lower()
        cart_name = str(cart_item.get("name") or "").lower()
        cart_cat = cart_meta["category"]

        if not cart_temp:
            if any(w in cart_name or w in cart_cat for w in ["burger", "whopper", "fries", "nuggets", "hot"]):
                cart_temp = "hot"
            elif any(w in cart_name or w in cart_cat for w in ["iced", "cold", "coke", "shake"]):
                cart_temp = "cold"

        if not cart_texture:
            if any(w in cart_name or w in cart_cat for w in ["fries", "nuggets", "rings", "crispy"]):
                cart_texture = "crunchy"

        if not cart_flavor:
            if any(w in cart_name or w in cart_cat for w in ["peri peri", "spicy", "fiery"]):
                cart_flavor = "spicy"
            elif any(w in cart_name or w in cart_cat for w in ["burger", "whopper"]):
                cart_flavor = "savory"

        # 1. Hot cart item -> Cold drink/dessert candidate (Sensory Contrast)
        if cart_temp == "hot" and cand_temp == "cold":
            total_sensory += SENSORY_AFFINITY_MATRIX["temp_hot_cold"]

        # 2. Crunchy cart item -> Smooth dip candidate (Sensory Contrast)
        if cart_texture == "crunchy" and cand_texture == "smooth":
            total_sensory += SENSORY_AFFINITY_MATRIX["texture_crunchy_smooth"]

        # 3. Spicy cart item -> Sweet treat candidate (Sensory Contrast)
        if cart_flavor == "spicy" and cand_flavor == "sweet":
            total_sensory += SENSORY_AFFINITY_MATRIX["flavor_spicy_sweet"]

        # 4. Savory cart item -> Refreshing drink candidate (Sensory Contrast)
        if cart_flavor == "savory" and (cand_temp == "cold" or cand_meta["meal_role"] == "drink"):
            total_sensory += SENSORY_AFFINITY_MATRIX["flavor_savory_refreshing"]

        # 5. Flavor Harmony / Theme Matching (e.g. Peri Peri Burger <-> Peri Peri Fries)
        cart_tokens = set()
        cand_tokens = set()
        known_themes = ["peri peri", "cheese", "cheesy", "smoky", "barbeque", "bbq", "spicy", "fiery", "chocolate", "berry", "makhani", "tandoori"]
        
        for t in [cart_flavor, cart_name] + (cart_item.get("tags") or []):
            for token in known_themes:
                if token in str(t).lower():
                    cart_tokens.add(token)

        for t in [cand_flavor, cand_name] + (candidate.get("tags") or []):
            for token in known_themes:
                if token in str(t).lower():
                    cand_tokens.add(token)

        if cart_tokens and cand_tokens and (cart_tokens & cand_tokens):
            total_sensory += SENSORY_AFFINITY_MATRIX["flavor_harmony"]

    # Cap soft score at 1.0
    return min(1.0, round(total_sensory, 2))


# =========================================================
# STRUCTURED SIGNAL GENERATOR
# =========================================================

def generate_candidate_signals(
    candidate: Dict[str, Any],
    cart: Optional[List[Dict[str, Any]]],
    placement: str = "normal"
) -> Dict[str, Any]:
    """
    Emits structured signal dictionary for downstream central coordination layer.
    """
    meta = parse_product_role(candidate)
    sensory = compute_sensory_score(cart, candidate)

    reasons = []
    if sensory > 0:
        reasons.append("SENSORY_AFFINITY_BOOST")
    if meta["meal_role"] != "unassigned":
        reasons.append(f"ROLE_MATCH_{meta['meal_role'].upper()}")

    # Confidence calculation: bounded [0.5, 0.95]
    confidence = 0.50
    if meta["meal_role"] != "unassigned":
        confidence += 0.20
    if sensory > 0:
        confidence += 0.15
    if candidate.get("price"):
        confidence += 0.10

    return {
        "candidate_id": candidate.get("id"),
        "candidate_name": candidate.get("name"),
        "role_fit": meta["meal_role"],
        "subrole": meta["subrole"],
        "satisfies_roles": meta["satisfies_roles"],
        "sensory_score": sensory,
        "confidence": round(min(0.95, confidence), 2),
        "reason_codes": reasons,
        "placement": placement,
    }


# =========================================================
# RANKING & SLOT SELECTION
# =========================================================

def rank_candidates_with_sensory(
    candidates: List[Dict[str, Any]],
    cart: Optional[List[Dict[str, Any]]],
    placement: str = "normal"
) -> List[Dict[str, Any]]:
    """
    Ranks a candidate pool using base score + Module A soft sensory affinity score.
    Preserves original menu order as tie-breaker.
    """
    if not candidates:
        return []

    scored_candidates = []
    for idx, cand in enumerate(candidates):
        if not isinstance(cand, dict):
            continue
        signals = generate_candidate_signals(cand, cart, placement=placement)
        base_priority = float(cand.get("priority") or cand.get("score") or 1.0)
        # Multiplicative soft sensory boost so sensory contrast influences ranking proportionally
        final_rank_score = base_priority * (1.0 + signals["sensory_score"])

        scored_candidates.append({
            "item": cand,
            "rank_score": final_rank_score,
            "signals": signals,
            "orig_idx": idx,
        })

    # Sort descending by rank_score, preserving original order on tie
    scored_candidates.sort(key=lambda x: (x["rank_score"], -x["orig_idx"]), reverse=True)
    return [c["item"] for c in scored_candidates]


# =========================================================
# CHECKOUT 3-SLOT RECOMMENDATION BUILDER
# =========================================================

def build_checkout_3slot_recommendations(
    cart: Optional[List[Dict[str, Any]]],
    all_sides: List[Dict[str, Any]],
    all_drinks: List[Dict[str, Any]],
    all_desserts: List[Dict[str, Any]],
    all_items: Optional[List[Dict[str, Any]]] = None
) -> List[Dict[str, Any]]:
    """
    Builds the 3 distinct dynamic recommendation slots for the Checkout Page:
      Slot 1: Conditional Dip / Sauce (Single highest-ranked dip when finger food is present & no dip in cart;
              if dip is already added, dip opportunity is completely suppressed;
              if dip condition does not apply, surfaces a meaningful last-minute side complement ONLY if justified by evidence).
      Slot 2: Best Match / Context-Aware Drink (Most relevant additional drink/product based on cart sensory & price fit).
      Slot 3: Sweet Finish (Best eligible true dessert, avoiding items in cart; suppresses unsuitable/forced items).
      
    Guarantees:
      - Dynamic refresh on cart changes.
      - Candidate deduplication across slots.
      - Returns 0, 1, 2, or 3 cards dynamically without forcing unnecessary upsells.
    """
    from services.modules.m06_condiment_gating import (
        get_checkout_dip_suggestions,
        is_condiment,
        has_condiment_in_cart,
        has_side_in_cart,
    )
    from services.modules.m07_cart_exclusion import exclude_cart_items

    cart_list = cart or []
    recommendations: List[Dict[str, Any]] = []
    seen_keys: Set[Tuple[str, str]] = set()

    def _get_key(item: Dict[str, Any]) -> Tuple[str, str]:
        item_id = item.get("id")
        if item_id is not None and str(item_id).strip() != "":
            return ("id", str(item_id).strip())
        name = str(item.get("name") or "").strip().lower()
        return ("name", name)

    # Track items already in cart to prevent recommending duplicates
    for cart_item in cart_list:
        if isinstance(cart_item, dict):
            seen_keys.add(_get_key(cart_item))

    # ---------------------------------------------------------
    # SLOT 1: CONDITIONAL DIP / SAUCE
    # ---------------------------------------------------------
    slot1_item = None
    dip_already_in_cart = has_condiment_in_cart(cart_list)
    finger_food_present = has_side_in_cart(cart_list)

    if finger_food_present and not dip_already_in_cart:
        # Show ONLY the single highest-ranked dip
        dips = get_checkout_dip_suggestions(all_sides, cart_list)
        eligible_dips = exclude_cart_items(dips, cart_list)
        if eligible_dips:
            ranked_dips = rank_candidates_with_sensory(eligible_dips, cart_list, placement="checkout")
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
        # If dip condition does not apply (no finger food), show a meaningful side complement ONLY if justified by evidence
        non_dip_sides = [s for s in (all_sides or []) if not is_condiment(s)]
        eligible_sides = exclude_cart_items(non_dip_sides, cart_list)
        if eligible_sides:
            ranked_sides = rank_candidates_with_sensory(eligible_sides, cart_list, placement="checkout")
            for s in ranked_sides:
                k = _get_key(s)
                if k not in seen_keys:
                    # Check if evidence justifies recommending this complement (e.g. sensory score > 0 or empty cart baseline)
                    sensory_score = compute_sensory_score(cart_list, s)
                    if sensory_score > 0.0 or len(cart_list) == 0:
                        slot1_item = dict(s)
                        slot1_item["badge"] = "🍟 Signature Side"
                        slot1_item["slot"] = 1
                        seen_keys.add(k)
                        break

    if slot1_item:
        recommendations.append(slot1_item)

    # ---------------------------------------------------------
    # SLOT 2: BEST MATCH / CONTEXT-AWARE DRINK
    # ---------------------------------------------------------
    slot2_item = None
    eligible_drinks = exclude_cart_items(all_drinks or [], cart_list)
    if eligible_drinks:
        ranked_drinks = rank_candidates_with_sensory(eligible_drinks, cart_list, placement="checkout")
        for drink in ranked_drinks:
            k = _get_key(drink)
            if k not in seen_keys:
                slot2_item = dict(drink)
                slot2_item["badge"] = "🥤 Best Drink"
                slot2_item["slot"] = 2
                seen_keys.add(k)
                break

    # Fallback for Slot 2 if no drink is eligible/available: general non-dessert item with evidence fit
    if not slot2_item:
        general_pool = (all_items or (all_sides + all_drinks + all_desserts))
        non_dessert = [i for i in general_pool if str(i.get("category") or "").lower() != "dessert"]
        eligible_fb = exclude_cart_items(non_dessert, cart_list)
        if eligible_fb:
            ranked_fb = rank_candidates_with_sensory(eligible_fb, cart_list, placement="checkout")
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

    # ---------------------------------------------------------
    # SLOT 3: SWEET FINISH
    # ---------------------------------------------------------
    slot3_item = None
    eligible_desserts = exclude_cart_items(all_desserts or [], cart_list)
    if eligible_desserts:
        ranked_desserts = rank_candidates_with_sensory(eligible_desserts, cart_list, placement="checkout")
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

