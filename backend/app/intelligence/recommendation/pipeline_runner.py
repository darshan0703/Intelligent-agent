"""
pipeline_runner.py
Master Pipeline Orchestrator for TheAtom Recommendation Engine.
Executes the 13 modular stages in strict 4-Phase order.
Guarantees strict mutual exclusion between Priority, Premium, and Additional slots:
  - Priority: Top 2 items (Popular)
  - Premium: Top 2 highest-priced luxury items (Strictly excluding items in Priority)
  - Additional: Top 4 remaining items (Strictly excluding items in Priority & Premium)
Zero duplicate items across tiers.
"""
from typing import Dict, Any, List, Set

# Import all 13 independent modules
from .modules.m01_dietary_lock import apply_dietary_lock
from .modules.m02_anti_redundancy import score_anti_redundancy
from .modules.m03_flavor_synergy import score_flavor_synergy
from .modules.m04_dual_role_saturation import get_fulfilled_pillars, filter_saturated_candidates
from .modules.m05_budget_ceiling import apply_price_ceiling
from .modules.m06_condiment_gating import has_finger_food_host, filter_or_boost_condiments
from .modules.m07_cart_exclusion import exclude_cart_items
from .modules.m08_gatekeeper_killswitch import apply_gatekeeper_killswitch
from .modules.m09_margin_multiplier import score_margin_multiplier
from .modules.m10_sensory_contrast import score_sensory_contrast
from .modules.m11_session_fatigue import apply_session_fatigue
from .modules.m12_circadian_craving import score_circadian_craving
from .modules.m13_subrole_mmr import rerank_subrole_diversity


def run_recommendation_pipeline(
    candidates: List[Dict[str, Any]],
    preference: str | None = None,
    cart: List[Dict[str, Any]] | None = None,
    anchor_item: Dict[str, Any] | None = None,
    shown_counts: Dict[str, int] | None = None,
    hour: int | None = None,
    is_checkout: bool = False
) -> Dict[str, List[Dict[str, Any]]]:
    cart_items = cart or []
    impressions = shown_counts or {}
    anchor_price = float(anchor_item.get("price") or anchor_item.get("original_price", 0)) if anchor_item else None

    # ==========================================================
    # PHASE 1: HARD EXCLUSIONS & SATURATION GATES
    # ==========================================================
    pool = list(candidates)

    # Module 1: Strict Dietary Lock
    pool = apply_dietary_lock(pool, preference, cart_items)

    # Module 7: Absolute Cart Exclusion
    pool = exclude_cart_items(pool, cart_items)

    # Module 4: Dining Pillars & Dual-Role Saturation
    fulfilled_pillars = get_fulfilled_pillars(cart_items)
    if is_checkout:
        pool = filter_saturated_candidates(pool, fulfilled_pillars)
        # Module 8: Gatekeeper Kill-Switch
        pool = apply_gatekeeper_killswitch(pool, fulfilled_pillars)
        if not pool:
            return {"priority": [], "premium": [], "additional": []}

    # Module 6: Condiment Host Gating (Hard Gate)
    host_present = has_finger_food_host(cart_items, anchor_item)
    pool = filter_or_boost_condiments(pool, host_present)

    if not pool:
        return {"priority": [], "premium": [], "additional": []}

    # ==========================================================
    # PHASE 2: BUDGET & MARGIN PROTECTION
    # ==========================================================
    # Module 5: Bulk Elastic Budget & Hard Price Ceiling (on product pages)
    if anchor_price and not is_checkout:
        pool = apply_price_ceiling(pool, anchor_price, max_ratio=1.5)

    # ==========================================================
    # PHASE 3: SENSORY & CULINARY SCORING
    # ==========================================================
    scored_pool = []
    for item in pool:
        item_copy = dict(item)
        base_score = float(item_copy.get("priority", item_copy.get("stock", 10)))

        # Module 2: Anti-Redundancy
        m2 = score_anti_redundancy(item_copy, anchor_item)
        # Module 3: Flavor Anti-Clash & Cuisine Synergy
        m3 = score_flavor_synergy(item_copy, anchor_item, cart_items)
        # Module 9: Tiered Margin Multiplier
        m9 = score_margin_multiplier(item_copy, anchor_price)
        # Module 10: Sensory Contrast
        m10 = score_sensory_contrast(item_copy, anchor_item)
        # Module 11: Session Fatigue
        m11 = apply_session_fatigue(item_copy, impressions)
        # Module 12: Circadian Craving Analyzer
        m12 = score_circadian_craving(item_copy, hour)

        final_score = base_score * m2 * m3 * m9 * m10 * m11 * m12
        item_copy["computed_score"] = final_score
        scored_pool.append(item_copy)

    # Sort by computed score descending
    scored_pool.sort(key=lambda x: x["computed_score"], reverse=True)

    # ==========================================================
    # PHASE 4: SUB-ROLE MMR DIVERSITY RE-RANKING
    # ==========================================================
    ranked = rerank_subrole_diversity(scored_pool, top_k=max(8, len(scored_pool)))

    # ==========================================================
    # STRICT MUTUAL EXCLUSION SLICING (8 DISTINCT ITEMS)
    # ==========================================================
    # 1. Priority (Popular): Top 2 ranked items
    priority = ranked[:2]
    used_ids: Set[Any] = {i.get("id") or i.get("name") for i in priority}

    # 2. Premium: Top 2 highest-priced items STRICTLY EXCLUDING items in Priority
    remaining_for_premium = [i for i in ranked if (i.get("id") or i.get("name")) not in used_ids]
    remaining_for_premium.sort(key=lambda x: float(x.get("price") or x.get("original_price", 0)), reverse=True)
    premium = remaining_for_premium[:2]
    used_ids.update({i.get("id") or i.get("name") for i in premium})

    # 3. Additional: Top 4 remaining items STRICTLY EXCLUDING Priority and Premium
    remaining_for_additional = [i for i in ranked if (i.get("id") or i.get("name")) not in used_ids]
    additional = remaining_for_additional[:4]

    return {
        "priority": priority,
        "premium": premium,
        "additional": additional,
    }
