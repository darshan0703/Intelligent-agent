"""
backend/services/menu_organizer.py
Dynamic Menu Organization for 'View All' Screens:
1. M01 Dietary Lock: Drops non-veg if veg preference active.
2. M07 Cart Exclusion: Excludes items already present in cart.
3. M05 Budget Ceiling & Dynamic Mindset:
   - Low Budget cart: Soft boost to Value/Affordable items.
   - Premium cart: Soft boost to Gourmet/Whopper/Premium items.
4. Formula-Driven Category Opportunity:
   - Product Relevance S(P) = S_base + 1.5 * S_affinity + 1.2 * S_budget + 0.8 * S_recency
   - Category Score S(C) = Average(Top 3 Product Scores in C) * (1 + 0.05 * Count)
   - Categories and products inside them are dynamically ordered descending by relevance.
"""

from typing import List, Dict, Any, Optional
from services.modules.m06_condiment_gating import has_finger_food_in_cart, is_meal_only_item
from services.modules.m07_cart_exclusion import exclude_cart_items


def is_item_in_cart(item: Dict[str, Any], cart: Optional[List[Dict[str, Any]]]) -> bool:
    """Checks if an item (by ID or normalized name) is already in the cart."""
    if not cart or not item:
        return False
    item_id = item.get("id")
    item_name = str(item.get("name") or "").strip().lower()

    for c in cart:
        if item_id is not None and c.get("id") == item_id:
            return True
        c_name = str(c.get("name") or "").strip().lower()
        if item_name and c_name == item_name:
            return True
    return False


def compute_budget_mindset(cart: Optional[List[Dict[str, Any]]]) -> str:
    """
    Margin-aware & Recency-driven Customer Context Detection:
    - 'premium': customer added a premium item (recent >= 140 or max >= 170). Margin expansion mode.
    - 'upsell': customer added mid-tier items (>= 110) or mixed cart. Moderate margin mode.
    - 'low_budget': cart contains only cheap entry items (< 100).
    - 'neutral': cart is empty.
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

    recent_price = prices[-1]
    max_price = max(prices)
    avg_price = sum(prices) / len(prices)

    # Margin Intelligence: If the customer adds a premium item (e.g. ₹200 burger),
    # immediately switch to 'premium' mode regardless of earlier cheap items!
    if recent_price >= 140.0 or max_price >= 170.0:
        return "premium"
    elif max_price >= 110.0 or avg_price >= 105.0:
        return "upsell"
    else:
        return "low_budget"


def _arrange_strategic_top4(ranked_products: List[Dict[str, Any]], mindset: str) -> List[Dict[str, Any]]:
    """
    QSR Commercial 4-Card Portfolio Merchandising:
    Arranges the top 4 cards visible on the initial screen viewport for maximum sales & margin:
    - Slot 1: Flagship High-Margin Hero Item (Whopper, Royale, Premium)
    - Slot 2: Contextual Affinity / Best-Seller Item
    - Slot 3: High-Perceived Value / Conversion Hook Item (<= 119)
    - Slot 4: Cravings / Premium Treat / Specialty Item
    """
    if len(ranked_products) <= 3:
        return ranked_products

    pool = list(ranked_products)
    top4: List[Dict[str, Any]] = []

    # Slot 1: Hero / Margin Leader (Highest price or Whopper/Royale/Premium from top 4 pool)
    hero_idx = 0
    for i, p in enumerate(pool[:4]):
        p_price = float(p.get("price") or 0)
        p_name = str(p.get("name") or "").lower()
        if p_price >= 140.0 or any(k in p_name for k in ["whopper", "royale", "peri peri", "cold coffee"]):
            hero_idx = i
            break
    top4.append(pool.pop(hero_idx))

    # Slot 2: Best overall remaining item (Top remaining relevance score)
    top4.append(pool.pop(0))

    # Slot 3: Value Anchor / Conversion Hook (Item <= 119 to prevent price bounce for budget guests)
    value_idx = None
    for i, p in enumerate(pool):
        p_price = float(p.get("price") or 0)
        if p_price <= 119.0:
            value_idx = i
            break
    if value_idx is not None:
        top4.append(pool.pop(value_idx))
    else:
        top4.append(pool.pop(0))

    # Slot 4: Remaining top item (Treat / Indulgence / Specialty)
    if pool:
        top4.append(pool.pop(0))

    return top4 + pool


def organize_menu_sections(
    category: str,
    raw_sections: List[Dict[str, Any]],
    preference: Optional[str] = None,
    cart: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """
    Applies formula-driven dynamic arrangement across full menu sections:
    PRODUCT RELEVANCE -> CATEGORY OPPORTUNITY -> CATEGORY ORDER -> PRODUCT ORDER

    1. Filters price == 0 meal components.
    2. Applies dietary lock (M01).
    3. Ranks un-carted candidates by Product Relevance S(P).
    4. Applies QSR 4-Card Portfolio Merchandising to top 4 viewport cards.
    5. Places already-carted items at the END of each section (instead of removing them).
    6. Calculates Category Opportunity S(C) from top-3 products.
    7. Dynamically orders categories and products inside them.
    """
    cart = cart or []
    mindset = compute_budget_mindset(cart)
    cat_lower = category.lower().strip()
    pref_norm = str(preference or "").lower().strip()

    cart_names = [(item.get("name") or "").lower() for item in cart]
    recent_cart_item = cart[-1] if cart else None

    has_fries = has_finger_food_in_cart(cart)

    scored_sections: List[tuple[float, Dict[str, Any]]] = []

    for sec in raw_sections:
        products = sec.get("products", [])

        # 1. Filter out meal-only items (price == 0)
        filtered_products = [p for p in products if not is_meal_only_item(p)]

        # 2. M01 Dietary Lock
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

        # 3. Separate unadded candidates vs already-carted products
        unadded = exclude_cart_items(filtered_products, cart)
        unadded_set = {id(p) for p in unadded}
        carted = [p for p in filtered_products if id(p) not in unadded_set]

        candidates_to_score = unadded if unadded else filtered_products

        # 4. Calculate Product Relevance Scores
        scored_prods: List[tuple[float, float, Dict[str, Any]]] = []
        for p in candidates_to_score:
            p_price = float(p.get("price") or 0)
            p_name = str(p.get("name") or "").lower()

            base_score = 1.0
            if any(k in p_name for k in ["whopper", "royale", "classic cold coffee", "peri peri fries"]):
                base_score += 0.5

            # Affinity score
            affinity_score = 0.0
            for c_name in cart_names:
                words = [w for w in c_name.split() if len(w) > 3]
                if any(w in p_name for w in words):
                    affinity_score += 0.5
                if "spicy" in c_name and any(w in p_name for w in ["peri", "chilli", "fiery"]):
                    affinity_score += 0.4
                if "fries" in c_name and "dip" in p_name:
                    affinity_score += 0.6

            # M05 Margin & Budget Fit
            budget_fit_score = 0.0
            if mindset == "premium":
                # High-Margin / Premium Mode: Max price to low price sorting preference
                budget_fit_score += (p_price / 100.0) * 0.8  # Linear price-weighting boost
                if p_price >= 140.0 or any(k in p_name for k in ["whopper", "royale", "double", "gourmet", "shake"]):
                    budget_fit_score += 1.0
            elif mindset == "upsell":
                # Medium-High Margin Mode: Boost mid-to-high items
                if 100.0 <= p_price <= 180.0:
                    budget_fit_score += 1.2
                elif p_price > 180.0:
                    budget_fit_score += 0.8
            else:
                # Low Budget Mode: Soft boost to budget items, keeping margin expansion visible
                if p_price <= 79.0:
                    budget_fit_score += 0.8
                elif 80.0 <= p_price <= 130.0:
                    budget_fit_score += 0.6

            # Recency score
            recency_score = 0.0
            if recent_cart_item:
                r_name = str(recent_cart_item.get("name") or "").lower()
                r_words = [w for w in r_name.split() if len(w) > 3]
                if any(w in p_name for w in r_words):
                    recency_score += 0.8

            prod_score = base_score + (affinity_score * 1.5) + (budget_fit_score * 1.2) + (recency_score * 0.8)
            scored_prods.append((prod_score, p_price, p))

        # Rank unadded products descending: Highest relevance score first, then highest price first (Max to Low)
        scored_prods.sort(key=lambda x: (x[0], x[1]), reverse=True)
        ranked_unadded = [x[2] for x in scored_prods]

        # Strategic 4-Card Portfolio Merchandising on initial viewport cards
        strategic_top4 = _arrange_strategic_top4(ranked_unadded, mindset)

        # Combine: Strategic Top 4 + Remaining unadded + Carted products AT THE VERY LAST
        final_section_products = strategic_top4 + carted if unadded else strategic_top4

        # 5. Calculate Derived Category Opportunity Score
        top_prods_scores = [x[0] for x in scored_prods[:3]] if scored_prods else [1.0]
        avg_top_score = sum(top_prods_scores) / len(top_prods_scores)
        count_bonus = 1.0 + (0.05 * len(ranked_unadded))
        cat_score = avg_top_score * count_bonus

        # Special condiment gating: Dips section placed right next to Fries if fries in cart
        sec_title = str(sec.get("title", "")).lower()
        if cat_lower in ("side", "sides") and "dip" in sec_title:
            if has_fries:
                cat_score += 5.0
            else:
                cat_score = 0.01  # Push to bottom if no fries in cart

        sec_copy = dict(sec)
        sec_copy["products"] = final_section_products
        scored_sections.append((cat_score, sec_copy))

    # Rank categories descending by derived CategoryScore
    scored_sections.sort(key=lambda x: x[0], reverse=True)
    return [s[1] for s in scored_sections if len(s[1].get("products", [])) > 0]
