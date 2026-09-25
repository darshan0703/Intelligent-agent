"""
app/intelligence/recommendation/scoring.py
TheAtom Recommendation Engine — 13-Module Deterministic Pipeline (V1 Specification).

Executes strictly in 4 ordered phases:

PHASE 1 — HARD EXCLUSIONS & SATURATION GATES (Modules 1, 4, 7, 8)
  Module 1: Strict Dietary Lock
  Module 7: Absolute Cart Exclusion
  Module 4: Dual-Role Saturation (Milkshake Paradox)
  Module 8: Gatekeeper Kill-Switch (Meal Saturation)

PHASE 2 — BUDGET & MARGIN PROTECTION (Modules 5, 9, 13)
  Module 5: Bulk Elastic Budgeting & Hard Price Ceiling (1.5x)
  Module 9: Margin Multiplier with Diminishing Returns
  Module 13: Anti-Gamification (Zero Deals, Winback = False)

PHASE 3 — SENSORY & CULINARY LOGIC (Modules 2, 3, 6, 10)
  Module 2: Anti-Redundancy & Universal Overrides
  Module 3: Flavor Anti-Clash & Cuisine Synergy
  Module 6: Condiment Host Gating
  Module 10: Sensory Contrast (Neuro-Gastronomy)

PHASE 4 — REAL-TIME HEURISTICS (Modules 11, 12)
  Module 11: Session Fatigue (Impression Damping)
  Module 12: Circadian Craving Analyzer

100% deterministic — zero random jitter, zero ML inference, zero DB writes.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Optional

from app.domain.catalog.entities import MenuItem
from app.intelligence.recommendation.heuristics.circadian_clock import CircadianCravingAnalyzer
from app.intelligence.recommendation.heuristics.kitchen_load import KitchenLoadTracker
from app.intelligence.recommendation.llm_merchandising_engine import get_impression_penalty


# ─────────────────────────────────────────────────────────────────────────────
# CONTEXT OBJECT
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class RecommendationContext:
    """
    Unified context object for the 13-module pipeline.
    Accepts anonymous session state; enrichable with user profile later.
    """
    session_id: str
    user_id: Optional[str] = None
    user_profile: Optional[dict[str, Any]] = None
    cart_lines: list[Any] = None
    dismissed_item_ids: set[int] = None
    dietary_lock: Optional[str] = None
    intent_mode: str = "standard"
    branch_id: int = 1
    circadian_phase: str = "afternoon_dip"
    anchor_item: Optional[MenuItem] = None
    session_context: Optional[dict[str, Any]] = None
    # Real-time heuristic fields
    active_affinities: list[str] = None
    rejected_categories: list[str] = None
    active_affinity: dict[str, Any] = None
    rejected_sub_roles: list[str] = None
    velocity_state: Optional[str] = None

    def __post_init__(self):
        if self.cart_lines is None:
            self.cart_lines = []
        if self.dismissed_item_ids is None:
            self.dismissed_item_ids = set()
        if self.session_context is None:
            self.session_context = {}
        # Normalise real-time heuristic fields from session_context or explicit args
        if self.active_affinities is None:
            raw = self.session_context.get("active_affinities", [])
            self.active_affinities = [str(a).strip().lower() for a in raw if a]
        else:
            self.active_affinities = [str(a).strip().lower() for a in self.active_affinities if a]
        if self.rejected_categories is None:
            raw = self.session_context.get("rejected_categories", [])
            self.rejected_categories = [str(r).strip().lower() for r in raw if r]
        else:
            self.rejected_categories = [str(r).strip().lower() for r in self.rejected_categories if r]
        if self.active_affinity is None:
            self.active_affinity = self.session_context.get("active_affinity", {})
        if self.rejected_sub_roles is None:
            raw = self.session_context.get("rejected_sub_roles", [])
            self.rejected_sub_roles = [str(r).strip().lower() for r in raw if r]
        else:
            self.rejected_sub_roles = [str(r).strip().lower() for r in self.rejected_sub_roles if r]
        if self.velocity_state is None:
            v = self.session_context.get("velocity_state")
            self.velocity_state = str(v).strip().lower() if v else None
        else:
            self.velocity_state = str(self.velocity_state).strip().lower()

        # Auto-resolve dietary_lock from session_context or SessionLearner profile if not provided
        if not self.dietary_lock:
            ctx_pref = str(self.session_context.get("preference") or self.session_context.get("food_preference") or "").strip().lower()
            if ctx_pref in ("veg", "non_veg", "non veg"):
                self.dietary_lock = "veg" if ctx_pref == "veg" else "non_veg"
            elif self.session_id:
                try:
                    from app.intelligence.recommendation.session_learner import SessionLearner
                    prof = SessionLearner.get_or_create_profile(self.session_id)
                    if prof and prof.dietary_lock:
                        self.dietary_lock = prof.dietary_lock
                except Exception:
                    pass


# ─────────────────────────────────────────────────────────────────────────────
# CATALOG MAPS (Static, in-memory — zero DB reads at runtime)
# ─────────────────────────────────────────────────────────────────────────────

CATALOG_SPICE_MAP: dict[int, int] = {
    83: 15,  # Fiery Hell Dip
    84: 6,   # Chilli Sauce With Oregano
    19: 8,   # Peri Peri Veg
    20: 8,   # Peri Peri Chicken
    21: 8,   # Peri Peri Paneer
    22: 8,   # Peri Peri Cheese
    23: 8,   # Peri Peri Chicken Burger
    67: 8,   # Peri Peri Fries (Medium)
    68: 8,   # Peri Peri Fries (King)
    74: 8,   # Peri Peri Chicken Nuggets 4 Pc
    75: 8,   # Peri Peri Chicken Nuggets 6 Pc
    76: 8,   # Peri Peri Chicken Wings 4pc
    77: 8,   # Peri Peri Chicken Boneless 4pc
    78: 8,   # Peri Peri Chicken Boneless 7pc
    85: 8,   # Peri Peri Chicken Boneless 2 Pc
    82: 2,   # Masala Hashbrown
    46: 2,   # Masala Fizz (Small)
    47: 2,   # Masala Fizz (Medium)
    3:  3,   # Chicken Makhani
    4:  3,   # Veg Makhani
}

CATALOG_SUB_ROLE_MAP: dict[int, str] = {
    50: "thick_shake", 51: "thick_shake", 52: "thick_shake", 53: "thick_shake",
    27: "hot_coffee",  28: "hot_coffee",  29: "hot_coffee",  30: "hot_coffee",
    32: "hot_coffee",  33: "hot_coffee",  34: "hot_coffee",  35: "hot_coffee",
    36: "hot_coffee",  37: "hot_coffee",  38: "hot_coffee",
    24: "cold_coffee", 25: "cold_coffee", 26: "cold_coffee", 31: "cold_coffee",
    39: "soda", 40: "soda", 41: "soda", 42: "soda", 43: "soda",
    45: "soda", 46: "soda", 47: "soda",
    48: "float", 49: "float",
    54: "softie", 55: "softie", 56: "softie", 57: "softie",
    58: "sundae", 59: "sundae", 60: "sundae", 61: "sundae", 62: "sundae",
    63: "premium_dessert", 64: "premium_dessert",
    72: "sharing_bucket", 73: "sharing_bucket",
    78: "sharing_bucket", 79: "sharing_bucket", 80: "sharing_bucket",
    65: "individual_snack", 66: "individual_snack",
    67: "individual_snack", 68: "individual_snack", 69: "individual_snack",
    70: "individual_snack", 71: "individual_snack",
    74: "individual_snack", 75: "individual_snack",
    76: "individual_snack", 77: "individual_snack",
    81: "individual_snack", 82: "individual_snack",
    83: "condiment", 84: "condiment",
    85: "individual_snack",
}


# ─────────────────────────────────────────────────────────────────────────────
# HELPER UTILITIES
# ─────────────────────────────────────────────────────────────────────────────

def _item_name(item: Any) -> str:
    """Returns lowercase item name safely from both MenuItem and dict."""
    if item is None:
        return ""
    if isinstance(item, dict):
        return str(item.get("name") or item.get("item_name") or "").lower()
    return str(getattr(item, "name", "") or "").lower()


def _item_price(item: Any) -> float:
    """Returns item price as float, handling Price value objects and plain numerics."""
    if item is None:
        return 0.0
    p = getattr(item, "price", None) if not isinstance(item, dict) else item.get("price") or item.get("unit_price")
    if p is None:
        return 0.0
    if hasattr(p, "amount"):
        return float(p.amount)
    try:
        return float(p)
    except (ValueError, TypeError):
        return 0.0


def _item_category(item: Any) -> str:
    """Returns lowercase category string."""
    if item is None:
        return ""
    cat = getattr(item, "category", None) if not isinstance(item, dict) else item.get("category", "")
    if cat is None:
        return ""
    return str(cat.value if hasattr(cat, "value") else cat).lower()


def _cart_names(cart_lines: list[Any]) -> list[str]:
    """Returns lowercased item names from all cart lines."""
    names = []
    for l in cart_lines:
        n = str(
            getattr(l, "item_name", None) or getattr(l, "name", None)
            or (l.get("item_name") or l.get("name") if isinstance(l, dict) else "")
            or ""
        ).lower()
        names.append(n)
    return names


def get_item_spice_level(item: Any) -> int:
    """Returns candidate spice scalar (0–15 scale)."""
    if not item:
        return 0
    for attr in ("spice", "Spice"):
        v = getattr(item, attr, None) if not isinstance(item, dict) else item.get(attr)
        if v is not None:
            try:
                return int(v)
            except (ValueError, TypeError):
                pass
    item_id = getattr(item, "id", None) or (item.get("id") if isinstance(item, dict) else None)
    if item_id is not None:
        try:
            iid = int(item_id)
            if iid in CATALOG_SPICE_MAP:
                return CATALOG_SPICE_MAP[iid]
        except (ValueError, TypeError):
            pass
    name = _item_name(item)
    if "fiery hell" in name or "fiery" in name:
        return 15
    if "peri peri" in name or "peri-peri" in name:
        return 8
    if "chilli" in name:
        return 6
    if "makhani" in name:
        return 3
    if "masala" in name:
        return 2
    return 0


def get_item_sub_role(item: Any) -> str:
    """Returns candidate sub-role, e.g. thick_shake, condiment, sharing_bucket."""
    if not item:
        return ""
    sub = getattr(item, "sub_role", None)
    if sub is None and isinstance(item, dict):
        sub = item.get("sub_role")
    if sub:
        return str(sub).strip().lower()
    item_id = getattr(item, "id", None) or (item.get("id") if isinstance(item, dict) else None)
    if item_id is not None:
        try:
            iid = int(item_id)
            if iid in CATALOG_SUB_ROLE_MAP:
                return CATALOG_SUB_ROLE_MAP[iid]
        except (ValueError, TypeError):
            pass
    name = _item_name(item)
    if "shake" in name:
        return "thick_shake"
    if any(w in name for w in ["cappuccino", "latte", "americano", "espresso", "hot chocolate"]) and "iced" not in name and "cold" not in name:
        return "hot_coffee"
    if "sundae" in name:
        return "sundae"
    if "softie" in name:
        return "softie"
    if "lava" in name or "mousse" in name:
        return "premium_dessert"
    if any(w in name for w in ["18pc", "18 pc", "15 pcs", "15pc", "8 pcs", "9pc", "9 pc", "7pc", "7 pc", "bucket", "sharing"]):
        return "sharing_bucket"
    if "dip" in name or "sauce" in name:
        return "condiment"
    if any(w in name for w in ["fries", "hashbrown", "strips", "nuggets", "puff"]):
        return "individual_snack"
    return ""


def extract_candidate_tags(candidate: Any) -> set[str]:
    """Extracts all tags for real-time heuristic matching."""
    tags: set[str] = set()
    if candidate is None:
        return tags
    cand_tags = getattr(candidate, "tags", None)
    if cand_tags is None and isinstance(candidate, dict):
        cand_tags = candidate.get("tags")
    if cand_tags:
        for t in cand_tags:
            tags.add(str(t).strip().lower())
    ft = getattr(candidate, "food_type", None) or (candidate.get("food_type") if isinstance(candidate, dict) else None)
    if ft:
        ft_str = str(ft.value if hasattr(ft, "value") else ft).lower()
        tags.add(ft_str)
        if "non" in ft_str:
            tags.update(["non_veg", "non-veg", "meat"])
        elif "veg" in ft_str:
            tags.update(["veg", "vegetarian"])
    cat = _item_category(candidate)
    if cat:
        tags.add(cat)
        tags.add(cat.rstrip("s"))
    sub = get_item_sub_role(candidate)
    if sub:
        tags.add(sub)
    name = _item_name(candidate)
    desc = f"{getattr(candidate, 'short_description', '') or ''} {getattr(candidate, 'long_description', '') or ''}".lower()
    full_text = f"{name} {desc}"
    for word in full_text.replace("(", " ").replace(")", " ").replace("-", " ").split():
        w_clean = word.strip().lower()
        if len(w_clean) >= 3:
            tags.add(w_clean)
    common_affinities = [
        "spicy", "peri peri", "peri-peri", "chicken", "paneer", "cheese", "cheesy",
        "crispy", "crunchy", "chocolate", "vanilla", "mango", "berry", "hot", "fiery",
        "sweet", "savory", "potato", "fries", "shake", "sundae", "coffee", "drink",
    ]
    for aff in common_affinities:
        if aff in full_text:
            tags.add(aff)
    return tags


# ─────────────────────────────────────────────────────────────────────────────
# MODULE 1 — STRICT DIETARY LOCK
# ─────────────────────────────────────────────────────────────────────────────

def module1_dietary_lock(candidate: MenuItem, dietary_lock: str | None) -> tuple[bool, str]:
    """
    Phase 1 / Module 1: Strict Dietary Lock.
    If dietary_lock == 'veg', eradicate all Non-Veg SKUs from the pool.
    Intelligence NEVER overrides dietary reality.
    """
    if not dietary_lock or dietary_lock.lower() != "veg":
        return True, "dietary_pass"

    it_is_veg = bool(
        candidate.food_type
        and "veg" in str(candidate.food_type).lower()
        and "non" not in str(candidate.food_type).lower()
    )
    name = _item_name(candidate)
    # Tokenised whole-word check to prevent 'egg' matching inside 'veggie'
    tokens = set(name.replace("(", " ").replace(")", " ").replace("-", " ").split())
    has_meat = (
        any(w in name for w in ["chicken", "mutton", "fish", "beef", "meat", "wings", "nugget", "nuggets"])
        or any(w in tokens for w in ["egg", "eggs"])
    )
    if not it_is_veg or has_meat:
        return False, "module1_dietary_veg_lock"
    return True, "dietary_pass"


# ─────────────────────────────────────────────────────────────────────────────
# MODULE 7 — ABSOLUTE CART EXCLUSION
# ─────────────────────────────────────────────────────────────────────────────

def module7_cart_exclusion(
    candidate: MenuItem,
    cart_ids: set[int],
    cart_names: set[str],
    anchor_id: int | None = None,
) -> tuple[bool, str]:
    """
    Phase 1 / Module 7: Absolute Cart Exclusion.
    Extract all item_ids in the cart. If a candidate matches, drop it permanently.
    """
    cand_id = candidate.id
    if cand_id is not None:
        if cand_id in cart_ids:
            return False, "module7_cart_exclusion_by_id"
        if anchor_id is not None and cand_id == anchor_id:
            return False, "module7_anchor_exclusion"

    import re
    cand_name = _item_name(candidate)
    clean_cand = re.sub(r"\s*\(.*?\)", "", cand_name).strip()
    for c_name in cart_names:
        clean_cart = re.sub(r"\s*\(.*?\)", "", c_name).strip()
        if cand_name == c_name or clean_cand == clean_cart:
            return False, "module7_cart_exclusion_by_name"
        if len(clean_cart) >= 4 and (clean_cart in cand_name or cand_name in clean_cart):
            return False, "module7_cart_exclusion_name_substring"
    return True, "cart_exclusion_pass"


# ─────────────────────────────────────────────────────────────────────────────
# MODULE 4 — DUAL-ROLE SATURATION & MEAL PILLAR TRACKING
# ─────────────────────────────────────────────────────────────────────────────

def module4_evaluate_meal_pillars(cart_lines: list[Any]) -> dict[str, bool]:
    """
    Phase 1 / Module 4: Dual-Role Saturation (Milkshake Paradox).
    Evaluates the 4 meal pillars: Main, Side, Drink, Dessert.
    A Shake/Float/heavy-dairy beverage simultaneously fulfils BOTH Drink AND Dessert.
    Returns: { 'main': bool, 'side': bool, 'drink': bool, 'dessert': bool }
    """
    pillars = {"main": False, "side": False, "drink": False, "dessert": False}

    for line in cart_lines:
        cat = _item_category(line)
        name = _item_name(line)

        if any(k in cat for k in ["burger", "whopper", "entree", "main", "taco", "wrap", "sandwich"]) or \
           any(k in name for k in ["burger", "whopper", "taco", "wrap", "crispy veg"]):
            pillars["main"] = True

        if "side" in cat or any(w in name for w in ["fries", "hashbrown", "strips", "nuggets", "puff", "wings"]):
            pillars["side"] = True

        if any(k in cat for k in ["drink", "beverage", "coffee", "shake", "cola", "fizz", "soda"]):
            pillars["drink"] = True
            # Dual-role: heavy dairy drink also fulfils dessert
            if any(w in name for w in ["shake", "frappe", "float"]):
                pillars["dessert"] = True
            else:
                from app.intelligence.recommendation.data_quality_gate import CulinaryTagger
                item_id = getattr(line, "id", None) or (line.get("id") or line.get("item_id") if isinstance(line, dict) else None)
                desc = f"{getattr(line, 'short_description', '') or ''} {getattr(line, 'long_description', '') or ''}".lower()
                if item_id:
                    prof = CulinaryTagger.extract_profile(item_id, name, desc)
                    if prof.dairy_content >= 0.7:
                        pillars["dessert"] = True

        if "dessert" in cat or any(w in name for w in ["sundae", "softie", "lava", "mousse", "choco", "cake", "brownie"]):
            pillars["dessert"] = True

    return pillars


# ─────────────────────────────────────────────────────────────────────────────
# MODULE 8 — GATEKEEPER KILL-SWITCH
# ─────────────────────────────────────────────────────────────────────────────

def module8_gatekeeper_kill_switch(pillars: dict[str, bool]) -> bool:
    """
    Phase 1 / Module 8: Gatekeeper Kill-Switch.
    If all 4 pillars are fulfilled, the meal is biologically complete.
    Returns True if the kill-switch fires (pipeline should halt, return []).
    """
    return all(pillars[p] for p in ("main", "side", "drink", "dessert"))


# ─────────────────────────────────────────────────────────────────────────────
# MODULE 5 — BULK ELASTIC BUDGETING & HARD PRICE CEILING
# ─────────────────────────────────────────────────────────────────────────────

def calculate_effective_anchor(cart_lines: list[Any], default_anchor: float = 100.0) -> float:
    """
    Phase 2 / Module 5: Bulk Elastic Budgeting.
    effective_anchor = max(highest_single_entree_price, total_entree_spend / total_entree_qty).
    Protects budget group-buyers while exploiting premium outliers (>= ₹150).
    """
    if not cart_lines:
        return default_anchor

    total_entree_spend = 0.0
    total_entrees = 0
    highest_main_price = 0.0

    for line in cart_lines:
        p = _item_price(line)
        qty = int(getattr(line, "quantity", 1) if not isinstance(line, dict) else (line.get("quantity") or 1))
        cat = _item_category(line)
        name = _item_name(line)
        is_main = (
            any(k in cat for k in ["burger", "whopper", "entree", "main", "taco", "wrap", "sandwich"])
            or any(k in name for k in ["burger", "whopper", "taco", "wrap", "crispy veg"])
        )
        if is_main:
            total_entree_spend += p * qty
            total_entrees += qty
            if p > highest_main_price:
                highest_main_price = p

    if total_entrees > 0:
        avg = total_entree_spend / total_entrees
        # If a premium outlier (>= ₹150) exists, let it raise the ceiling
        if highest_main_price >= 150.0:
            return float(round(highest_main_price, 2))
        return float(round(avg, 2))

    # Fallback: use the highest single item price
    highest = max((_item_price(l) for l in cart_lines), default=default_anchor)
    return float(max(highest, default_anchor))


def module5_hard_price_ceiling(
    candidate: MenuItem,
    anchor_price: float,
    is_product_page: bool,
) -> tuple[bool, str]:
    """
    Phase 2 / Module 5: Hard Price Ceiling on Product Pages.
    CRITICAL: if candidate.price > anchor.price * 1.5, apply 0.0x kill-score (drop immediately).
    This is a BOOLEAN GATE, not a soft sigmoid.
    Sharing buckets bypass this ceiling (group-order items).
    """
    if not is_product_page or anchor_price <= 0:
        return True, "price_ceiling_pass"

    cand_sub = get_item_sub_role(candidate)
    if cand_sub == "sharing_bucket":
        return True, "sharing_bucket_ceiling_bypass"

    p_cand = _item_price(candidate)
    if p_cand > anchor_price * 1.5:
        return False, f"module5_hard_price_ceiling:{p_cand:.0f}>{anchor_price * 1.5:.0f}"
    return True, "price_ceiling_pass"


# ─────────────────────────────────────────────────────────────────────────────
# MODULE 9 — MARGIN MULTIPLIER WITH DIMINISHING RETURNS
# ─────────────────────────────────────────────────────────────────────────────

def module9_margin_multiplier(candidate: MenuItem, anchor_price: float) -> float:
    """
    Phase 2 / Module 9: Margin Multiplier with Diminishing Returns.
    High-margin fountain sodas receive a boost scaled by anchor price per directive:
      anchor < ₹100  → max 1.1x  (directive: cap prevents soda dominance on value buyers)
      anchor >= ₹169 → max 1.3x  (premium buyer accepts upsell)
      else           → 1.2x
    Low-margin packaged water → 0.85x dampener.
    """
    name = _item_name(candidate)
    desc = f"{getattr(candidate, 'short_description', '') or ''} {getattr(candidate, 'long_description', '') or ''}".lower()
    text = f"{name} {desc}"

    # Low-margin utility water dampener
    if any(w in text for w in ["packaged drinking water", "bottled water", "mineral water", "kinley", "aquafina"]) or \
       ("water" in name and not any(f in name for f in ["watermelon", "watering"])):
        return 0.85

    # High-margin fountain sodas/carbonated, shakes, and desserts
    if any(s in text for s in ["coca-cola", "coke", "sprite", "fizz", "fanta", "thums up", "pepsi", "mirinda", "soda", "shake", "thick shake"]):
        if anchor_price < 100.0:
            return 1.10  # Directive: max_margin_boost = 1.1x for anchor < 100
        elif anchor_price >= 169.0:
            return 1.30
        else:
            return 1.20

    return 1.0


# ─────────────────────────────────────────────────────────────────────────────
# MODULE 13 — ANTI-GAMIFICATION (WINBACK ERADICATION & ZERO DEALS)
# ─────────────────────────────────────────────────────────────────────────────

def module13_anti_gamification_check(candidate: MenuItem) -> tuple[bool, str]:
    """
    Phase 2 / Module 13: Anti-Gamification.
    Asserts offer_price == original_price on every candidate.
    Any candidate carrying a micro-deal or discount is eradicated.
    """
    has_micro_deal = getattr(candidate, "has_micro_deal", False)
    discount_pct = getattr(candidate, "discount_pct", 0.0) or 0.0
    deal_tag = getattr(candidate, "deal_tag", None)
    if has_micro_deal or float(discount_pct) > 0 or deal_tag:
        return False, "module13_anti_gamification_deal_detected"
    return True, "anti_gamification_pass"


# ─────────────────────────────────────────────────────────────────────────────
# MODULE 2 — ANTI-REDUNDANCY & UNIVERSAL OVERRIDES
# ─────────────────────────────────────────────────────────────────────────────

def module2_anti_redundancy_score(candidate: MenuItem, anchor_item: MenuItem | None) -> float:
    """
    Phase 3 / Module 2: Base-Ingredient Anti-Redundancy.
    If anchor.base_ingredient == candidate.base_ingredient, apply 0.35x severe penalty.
    EXCEPTION: If candidate name contains 'Nuggets' or 'Fries', bypass entirely.
    Returns a score multiplier (0.35 or 1.0).
    """
    if not anchor_item:
        return 1.0

    from app.intelligence.recommendation.constraints import AntiRedundancyConstraint

    # Universal bypass: NEVER penalise Nuggets or Fries regardless of redundancy
    if AntiRedundancyConstraint.is_universal_side(candidate):
        return 1.0

    cat = _item_category(candidate)
    if "side" not in cat:
        return 1.0

    if AntiRedundancyConstraint.is_redundant_side(candidate, anchor_item):
        return 0.35

    return 1.0


# ─────────────────────────────────────────────────────────────────────────────
# MODULE 3 — FLAVOR ANTI-CLASH & CUISINE SYNERGY
# ─────────────────────────────────────────────────────────────────────────────

def module3_flavor_anti_clash_penalty(candidate: MenuItem, cart_lines: list[Any]) -> float:
    """
    Phase 3 / Module 3 (part A): Flavor Anti-Clash.
    If any cart item shares the exact dominant_flavor with the candidate, apply 0.25x penalty.
    Explicit mango-clash check is included.
    Returns a multiplier (0.25 or 1.0).
    """
    from app.intelligence.recommendation.constraints import AntiRedundancyConstraint
    if not cart_lines:
        return 1.0
    cand_name = _item_name(candidate)
    # Explicit mango anti-clash
    has_mango_cart = any("mango" in _item_name(l) for l in cart_lines)
    if has_mango_cart and "mango" in cand_name:
        return 0.25
    has_clash, _ = AntiRedundancyConstraint.has_flavor_clash(candidate, cart_lines)
    if has_clash:
        return 0.25
    return 1.0


def module3_cuisine_synergy(candidate: MenuItem, anchor_item: MenuItem | None, cart_lines: list[Any]) -> float:
    """
    Phase 3 / Module 3 (part B): Cuisine Synergy.
    CRITICAL: If anchor.name contains 'Makhani', 'Paneer', or 'Tandoor',
    apply 1.5x synergy boost to candidates containing 'Masala' (regional alignment).
    Also checks cart items for the same cuisine markers.
    """
    cand_name = _item_name(candidate)
    if "masala" not in cand_name:
        return 1.0

    # Check anchor
    if anchor_item:
        anc_n = _item_name(anchor_item)
        if any(k in anc_n for k in ["makhani", "paneer", "tandoor"]):
            return 1.50

    # Check cart items
    for line in cart_lines:
        line_name = _item_name(line)
        if any(k in line_name for k in ["makhani", "paneer", "tandoor"]):
            return 1.50

    return 1.0


# ─────────────────────────────────────────────────────────────────────────────
# MODULE 6 — CONDIMENT HOST GATING
# ─────────────────────────────────────────────────────────────────────────────

def _has_valid_condiment_host(cart_lines: list[Any], anchor_item: MenuItem | None) -> bool:
    """
    Returns True if a qualifying finger-food host item (Fries/Nuggets/Strips)
    is present in the cart or anchor.
    """
    host_keywords = ["fries", "french fries", "nugget", "nuggets", "strips", "veggie strips", "chicken strips"]
    for line in cart_lines:
        name = _item_name(line)
        if any(w in name for w in host_keywords):
            return True
    if anchor_item:
        name = _item_name(anchor_item)
        if any(w in name for w in host_keywords):
            return True
    return False


def module6_condiment_host_gate(
    candidate: MenuItem,
    cart_lines: list[Any],
    anchor_item: MenuItem | None,
    has_spice_affinity: bool = False,
) -> tuple[float, str]:
    """
    Phase 3 / Module 6: Absolute Condiment Gating (The UI Lock).
    Condiment gating is an absolute Boolean lock.
    If candidate is a condiment (sub_role == 'condiment', or dip/sauce/mayo/chilli sauce),
    scan the cart/anchor payload.
    If 'Fries', 'Nuggets', or 'Strips' are NOT present, return 0.0x.
    Dips must be mathematically invisible unless a finger-food host is present.
    """
    cand_name = _item_name(candidate)
    sub = get_item_sub_role(candidate)
    is_condiment = (
        sub == "condiment"
        or any(w in cand_name for w in ["dip", "sauce", "mayo", "chilli sauce", "hell dip"])
    )

    if not is_condiment:
        return 1.0, "not_condiment"

    # Absolute Boolean lock: require finger-food host (Fries, Nuggets, Strips)
    if _has_valid_condiment_host(cart_lines, anchor_item):
        return 1.5, "condiment_host_boost"

    # No finger-food host present -> mathematically invisible (0.0x kill)
    return 0.0, "module6_condiment_no_host_kill"


# ─────────────────────────────────────────────────────────────────────────────
# MODULE 10 — SENSORY CONTRAST (NEURO-GASTRONOMY)
# ─────────────────────────────────────────────────────────────────────────────

def module10_sensory_contrast(
    candidate: MenuItem,
    anchor_item: MenuItem | None,
    cart_lines: list[Any],
) -> float:
    """
    Phase 3 / Module 10: Sensory Contrast.
    Calculates biological counter-balance pairings:
      - High spice anchor → boost high-dairy / cold items (Vanilla Softie, Cold Coffee, Shake)
      - Heavy / rich anchor → boost carbonated / acidic items (Coke, Sprite, Fizz)
      - Crispy anchor → boost potato sides and refreshing drinks
      - Any burger → boost drink > side > dessert (structural meal completion)
    """
    cand_name = _item_name(candidate)
    cand_cat = _item_category(candidate)
    cand_price = _item_price(candidate)

    cart_name_list = _cart_names(cart_lines)
    has_spicy = any("peri" in n or "spicy" in n or "fiery" in n or "chilli" in n or "jalapeno" in n for n in cart_name_list)
    has_rich = False
    has_crispy = False
    has_burger = False
    anchor_price = 0.0

    if anchor_item:
        anc = _item_name(anchor_item)
        anchor_price = _item_price(anchor_item)
        if any(k in anc for k in ["spicy", "peri", "fiery", "chilli", "jalapeno", "masala"]):
            has_spicy = True
        if any(k in anc for k in ["cheese", "whopper", "royale", "paneer", "makhani"]):
            has_rich = True
        if any(k in anc for k in ["crispy", "crunchy", "fried"]):
            has_crispy = True
        if "burger" in _item_category(anchor_item):
            has_burger = True

    score = 1.0

    if has_spicy:
        # Capsaicin cooling: dairy / sweet coats receptors
        if any(w in cand_name for w in ["shake", "sundae", "coffee", "float", "softie", "mousse", "cup", "cone", "cake", "lava"]):
            score += 0.45
        elif "drink" in cand_cat:
            score += 0.35
        elif "side" in cand_cat:
            score += 0.30 if not any(k in cand_name for k in ["spicy", "peri", "fiery"]) else -0.15
    elif has_rich:
        # Cut the grease: effervescent carbonation and indulgent finish
        if any(w in cand_name for w in ["fizz", "cola", "coke", "sprite", "mirinda", "float", "thums up"]):
            score += 0.40
        elif any(w in cand_name for w in ["lava", "mousse", "sundae", "cup", "cake", "softie", "shake", "thick shake"]):
            score += 0.40
        elif "side" in cand_cat:
            score += 0.30
    elif has_crispy:
        if "side" in cand_cat and any(w in cand_name for w in ["fries", "hashbrown", "strips", "rings", "nugget", "nuggets"]):
            score += 0.35
        elif "drink" in cand_cat:
            score += 0.35
        elif "dessert" in cand_cat:
            score += 0.25
    elif has_burger:
        if "drink" in cand_cat:
            score += 0.35
        elif "side" in cand_cat:
            score += 0.30
        elif "dessert" in cand_cat:
            score += 0.25

    # Chicken Burger + Chicken Nuggets pairing synergy (Module 2 Universal Override complement)
    if anchor_item and "chicken" in _item_name(anchor_item) and any(w in cand_name for w in ["nugget", "nuggets"]):
        score += 0.40

    # Spend / wallet anchoring: premium anchors reward gourmet complements
    if anchor_price >= 150.0:
        if cand_price >= 120.0:
            score += 0.50
        elif cand_price >= 80.0:
            score += 0.20
        elif cand_price < 50.0:
            score -= 0.20

    return max(0.01, score)


def get_item_temperature(item: Any) -> int:
    """
    Evaluates temperature on 1-5 scalar scale:
    5 = Hot (Hot coffee, freshly grilled burgers, warm molten cakes)
    4 = Warm / Hot
    3 = Ambient
    2 = Chilled
    1 = Frozen / Cold (Sodas, shakes, sundaes, softies)
    """
    if not item:
        return 3
    for attr in ("temp", "temperature", "Temp", "Temperature"):
        v = getattr(item, attr, None) if not isinstance(item, dict) else item.get(attr)
        if v is not None:
            try:
                return int(v)
            except (ValueError, TypeError):
                pass
    st = getattr(item, "serving_type", None) or (item.get("serving_type") if isinstance(item, dict) else None)
    if st:
        st_str = str(st.value if hasattr(st, "value") else st).lower()
        if "hot" in st_str:
            return 5
        elif "cold" in st_str or "chilled" in st_str or "frozen" in st_str:
            return 1
        elif "ambient" in st_str:
            return 3
    name = _item_name(item)
    if any(w in name for w in ["hot", "warm", "burger", "whopper", "lava", "cappuccino", "latte", "espresso", "americano", "tea", "baked"]):
        return 5
    if any(w in name for w in ["cold", "chilled", "shake", "sundae", "softie", "float", "ice", "fizz", "soda", "coke", "sprite", "pepsi"]):
        return 1
    return 3


def module10_thermal_contrast_multiplier(
    candidate: MenuItem,
    anchor_item: MenuItem | None,
    circadian_phase: str,
) -> float:
    """
    Phase 3: Thermal Contrast (The Hot/Hot Ban).
    If anchor.temp >= 4 (Hot) and candidate.temp >= 4 (Hot), apply a 0.50x damping penalty,
    UNLESS the Circadian Craving Analyzer detects it is morning (before 11 AM).
    """
    if not anchor_item:
        return 1.0

    is_morning = circadian_phase == "morning"
    if not is_morning:
        from datetime import datetime
        is_morning = datetime.now().hour < 11

    if is_morning:
        return 1.0  # Morning allows hot burger/hashbrown with hot coffee

    # Thermal contrast applies to beverages & desserts (e.g. Hot Coffee with Hot Burger)
    cand_cat = _item_category(candidate)
    cand_name = _item_name(candidate)
    is_drink_or_dessert = (
        any(k in cand_cat for k in ["drink", "beverage", "dessert"])
        or any(w in cand_name for w in ["coffee", "latte", "cappuccino", "tea", "espresso", "americano"])
    )
    if not is_drink_or_dessert:
        return 1.0

    anchor_temp = get_item_temperature(anchor_item)
    cand_temp = get_item_temperature(candidate)

    if anchor_temp >= 4 and cand_temp >= 4:
        return 0.50

    return 1.0


# ─────────────────────────────────────────────────────────────────────────────
# MODULE 11 — SESSION FATIGUE (IMPRESSION DAMPING)
# ─────────────────────────────────────────────────────────────────────────────

def module11_session_fatigue(session_id: str, item_id: int, candidate: Any = None) -> float:
    """
    Phase 4 / Module 11: Session Fatigue.
    Reads impressions count from in-memory session state (no DB writes).
    Applies progressive damping if item was shown >= 3 times in this session.
    Returns a penalty multiplier (0.70 if impressions >= 3, else higher per schedule).
    Yield Management Override: If item is flagged as overstock/perishable, bypass damping (return 1.0).
    """
    # Yield override: perishable items must stay visible
    if candidate is not None and is_yield_override_active(candidate)[0]:
        return 1.0
    return float(get_impression_penalty(session_id, item_id))


# ─────────────────────────────────────────────────────────────────────────────
# MODULE 12 — CIRCADIAN CRAVING ANALYZER
# ─────────────────────────────────────────────────────────────────────────────

def module12_circadian_score(candidate: MenuItem, circadian_phase: str) -> float:
    """
    Phase 4 / Module 12: Circadian Craving Analyzer.
    On Discovery shelves (empty cart), reads server time and applies biological craving multipliers:
      Morning (7–11 AM): caffeine, hashbrowns
      Afternoon (12–4 PM): savory meals, carbonated
      Evening (5–9 PM): crispy sharing sides
      Late Night (9 PM+): high-sugar, comfort items (shakes, lava cups)
    """
    mult, _ = CircadianCravingAnalyzer.evaluate_circadian_multiplier(candidate)
    return float(mult)


# ─────────────────────────────────────────────────────────────────────────────
# OPERATIONAL SCALARS: VELOCITY & YIELD MANAGEMENT
# ─────────────────────────────────────────────────────────────────────────────

DEFAULT_ITEM_VELOCITIES: dict[str, float] = {
    "fries": 0.45,
    "french fries": 0.45,
    "king fries": 0.38,
    "peri peri fries": 0.38,
    "coca-cola": 0.42,
    "coke": 0.42,
    "pepsi": 0.40,
    "sprite": 0.35,
    "fanta": 0.35,
    "thums up": 0.38,
    "chicken nuggets": 0.35,
    "nuggets": 0.35,
    "crispy veg": 0.40,
    "crispy chicken": 0.35,
    "whopper": 0.32,
    "chocolate sundae": 0.28,
    "mango sundae": 0.25,
    "thick shake": 0.30,
    "shake": 0.30,
    "chocolate lava cup": 0.26,
    "softie": 0.25,
    "veggie strips": 0.20,
    "cheese dip": 0.22,
    "dip": 0.22,
    "masala hashbrown": 0.18,
    "hashbrown": 0.18,
    "bk veg pizza puff": 0.12,
    "pizza puff": 0.12,
    "puff": 0.12,
}


def get_item_velocity(candidate: Any) -> float:
    """Fetches the historical conversion rate for a candidate item."""
    if candidate is None:
        return 0.20
    v = getattr(candidate, "velocity_score", None) or getattr(candidate, "conversion_rate", None)
    if v is not None and float(v) > 0.0:
        return round(float(v), 4)
    if isinstance(candidate, dict):
        d_val = candidate.get("velocity_score") or candidate.get("conversion_rate")
        if d_val is not None and float(d_val) > 0.0:
            return round(float(d_val), 4)
    name = _item_name(candidate)
    for key, rate in DEFAULT_ITEM_VELOCITIES.items():
        if key in name:
            return rate
    cat = str(getattr(candidate, "category", "")).lower()
    if "side" in cat:
        return 0.25
    if "drink" in cat:
        return 0.30
    if "dessert" in cat:
        return 0.22
    return 0.20


def calculate_velocity_multiplier(candidate: Any) -> float:
    """
    Velocity Multiplier (Top-Seller Bias).
    velocity_mult = 1.0 + conversion_rate.
    Fries (45% conv) → 1.45x; Pizza Puff (12% conv) → 1.12x.
    """
    rate = get_item_velocity(candidate)
    return round(1.0 + float(rate), 4)


def is_yield_override_active(candidate: Any) -> tuple[bool, str]:
    """
    Yield Management Override check.
    Returns (is_active, reason) if item is flagged overstock or high_perishability.
    """
    if candidate is None:
        return False, "none"
    if getattr(candidate, "overstock_flag", False) or getattr(candidate, "is_overstock", False):
        return True, "overstock_flag"
    if isinstance(candidate, dict) and (candidate.get("overstock_flag") or candidate.get("is_overstock")):
        return True, "overstock_payload"
    inv = getattr(candidate, "inventory", None)
    if inv is not None:
        if getattr(inv, "overstock_flag", False) or getattr(inv, "is_overstock", False):
            return True, "overstock_snapshot"
        if getattr(inv, "perishability_index", 1) >= 4:
            return True, "high_perishability_inventory"
        exp_days = getattr(candidate, "days_to_expiry", None)
        if exp_days is not None and exp_days <= 2:
            return True, "imminent_expiry"
    p_idx = getattr(candidate, "perishability_index", None)
    if isinstance(candidate, dict) and p_idx is None:
        p_idx = candidate.get("perishability_index")
    if p_idx is not None and int(p_idx) >= 4:
        return True, f"high_perishability_index_{p_idx}"
    name = _item_name(candidate)
    desc = f"{getattr(candidate, 'short_description', '') or ''} {getattr(candidate, 'long_description', '') or ''}".lower()
    if any(k in f"{name} {desc}" for k in ["mango puree", "fresh dairy", "fresh milk", "soft serve"]):
        return True, "perishable_ingredient_match"
    return False, "standard"


def calculate_yield_boost(candidate: Any) -> float:
    """Returns 1.5x Yield Boost if item is flagged overstock/perishable, else 1.0."""
    active, _ = is_yield_override_active(candidate)
    return 1.50 if active else 1.0


# ─────────────────────────────────────────────────────────────────────────────
# REAL-TIME HEURISTICS (Session Context, Zero DB writes)
# ─────────────────────────────────────────────────────────────────────────────

def evaluate_realtime_heuristics(
    candidate: Any,
    active_affinities: list[str] | None = None,
    rejected_categories: list[str] | None = None,
    active_affinity: dict[str, Any] | None = None,
    rejected_sub_roles: list[str] | None = None,
    velocity_state: Optional[str] = None,
) -> tuple[float, dict[str, Any]]:
    """
    Real-Time In-Memory Heuristics (Catalog Mapped, Zero-Training):
    1. Sub-Role Rejection: 0.0x kill-score if candidate sub-role is in rejected_sub_roles.
    2. Attribute Affinity: 1.3x impulse if Spice >= threshold from active_affinity.
    3. Tag-based Affinity: 1.3x impulse if candidate tags match active_affinities.
    4. Cart Velocity Rush: 1.4x for sharing_buckets, 0.4x for individual items.
    5. Category Rejection: 0.1x kill if category matches rejected_categories.
    """
    multiplier = 1.0
    meta: dict[str, Any] = {}
    if not candidate:
        return multiplier, meta

    cand_sub = get_item_sub_role(candidate)

    # 1. Sub-Role Rejection (absolute 0.0x kill)
    if rejected_sub_roles:
        rej_set = {str(r).strip().lower() for r in rejected_sub_roles if r}
        if cand_sub in rej_set:
            meta["sub_role_kill_score"] = 0.0
            meta["rejected_sub_role"] = cand_sub
            return 0.0, meta

    # 2. Scalar Attribute Affinity (Spice threshold)
    if active_affinity and isinstance(active_affinity, dict):
        cand_spice = get_item_spice_level(candidate)
        for key, val in active_affinity.items():
            if str(key).strip().lower() == "spice":
                try:
                    thresh = int(val)
                except (ValueError, TypeError):
                    thresh = 4
                if cand_spice >= thresh:
                    multiplier *= 1.30
                    meta["impulse_affinity_boost"] = 1.30
                    meta["matched_scalar_affinity"] = {"Spice": cand_spice, "threshold": thresh}
                    break

    # 3. Tag-based active affinities (backward compat: ['spicy', 'chicken'])
    if active_affinities and "impulse_affinity_boost" not in meta:
        cand_tags = extract_candidate_tags(candidate)
        matched = [a for a in active_affinities if a and (a in cand_tags or any(a in t for t in cand_tags))]
        if matched:
            multiplier *= 1.30
            meta["impulse_affinity_boost"] = 1.30
            meta["matched_affinities"] = matched

    # 4. Cart Velocity Rush
    if velocity_state and str(velocity_state).strip().lower() == "rushed":
        if cand_sub == "sharing_bucket":
            multiplier *= 1.40
            meta["bulk_rush_multiplier"] = 1.40
            meta["sharing_bucket_boost"] = True
        else:
            multiplier *= 0.40
            meta["individual_item_penalty"] = 0.40

    # 5. Category Rejection (0.1x soft kill)
    if rejected_categories:
        cat_raw = _item_category(candidate)
        cat_norm = cat_raw.rstrip("s")
        for rej in rejected_categories:
            rej_clean = str(rej).strip().lower()
            rej_norm = rej_clean.rstrip("s")
            if (
                rej_clean == cat_raw or rej_norm == cat_norm
                or rej_norm in cat_raw or cat_norm in rej_norm
                or (rej_norm in ("drink", "drinks", "beverage") and any(w in cat_raw for w in ("drink", "beverage", "shake", "coffee", "cola", "fizz")))
                or (rej_norm in ("dessert", "desserts", "sweet") and any(w in cat_raw for w in ("dessert", "sundae", "softie", "lava")))
                or (rej_norm in ("side", "sides", "snack") and any(w in cat_raw for w in ("side", "fries", "puff", "strips", "dip")))
            ):
                multiplier *= 0.10
                meta["rejected_category_penalty"] = 0.10
                meta["rejected_category"] = rej_clean
                break

    return multiplier, meta


# ─────────────────────────────────────────────────────────────────────────────
# PRICE PROXIMITY (Soft score for non-product-page contexts)
# ─────────────────────────────────────────────────────────────────────────────

def price_proximity_score(p_cand: float, p_anchor: float, k: float = 4.0) -> float:
    """
    Continuous logistic price proximity (used outside of product-page hard-ceiling context):
    price_fit = 1 / (1 + exp(k * (cand/anchor - 1.5)))
    """
    if p_anchor <= 0:
        return 1.0
    ratio = p_cand / p_anchor
    exponent = min(50.0, max(-50.0, k * (ratio - 1.5)))
    base_fit = 1.0 / (1.0 + math.exp(exponent))
    if p_anchor < 100.0 and ratio <= 1.0:
        base_fit += 0.30 * (1.0 - ratio)
    return max(0.01, float(base_fit))


# ─────────────────────────────────────────────────────────────────────────────
# KITCHEN LOAD SCORE
# ─────────────────────────────────────────────────────────────────────────────

def kitchen_load_score(candidate: MenuItem, branch_id: int) -> float:
    """Tier 2 soft pacing signal: kitchen prep station queue multiplier."""
    mult, _ = KitchenLoadTracker.evaluate_kitchen_multiplier(candidate, branch_id)
    return float(mult)


# ─────────────────────────────────────────────────────────────────────────────
# COMPOSITE SCORE COMBINER
# ─────────────────────────────────────────────────────────────────────────────

DEFAULT_SCORING_WEIGHTS: dict[str, float] = {
    "price_fit":        0.25,
    "sensory_contrast": 0.30,
    "circadian":        0.15,
    "kitchen_load":     0.10,
    "bandit":           0.10,
    "novelty":          0.10,
}


def combine_scores(features: dict[str, float], weights: dict[str, float] | None = None) -> float:
    """
    Weighted geometric mean of core scoring signals.
    No single signal can dominate by construction.
    """
    w = weights or DEFAULT_SCORING_WEIGHTS
    s_price    = features.get("price_fit", 1.0)
    s_sensory  = features.get("sensory_contrast", 1.0)
    s_circadian = features.get("circadian", 1.0)
    s_kitchen  = features.get("kitchen_load", 1.0)
    s_bandit   = features.get("bandit_theta", 0.33)
    s_novelty  = features.get("novelty", 1.0)

    combined = (
        (s_price ** w.get("price_fit", 0.25))
        * (s_sensory ** w.get("sensory_contrast", 0.30))
        * (s_circadian ** w.get("circadian", 0.15))
        * (s_kitchen ** w.get("kitchen_load", 0.10))
        * ((0.75 + s_bandit) ** w.get("bandit", 0.10))
        * (s_novelty ** w.get("novelty", 0.10))
    )
    return float(combined)


# ─────────────────────────────────────────────────────────────────────────────
# LEGACY ALIASES (backward compat for existing callers)
# ─────────────────────────────────────────────────────────────────────────────

def sensory_contrast_score(candidate: MenuItem, anchor_item: MenuItem | None, cart_lines: list[Any]) -> float:
    """
    Alias combining Module 10 (Sensory Contrast) + Module 3B (Cuisine Synergy)
    for backward compatibility with direct callers and tests.
    """
    score = module10_sensory_contrast(candidate, anchor_item, cart_lines)
    # Apply cuisine synergy (Module 3B) directly in this combined path
    synergy = module3_cuisine_synergy(candidate, anchor_item, cart_lines)
    if synergy != 1.0:
        score *= synergy
    return score


def circadian_score(candidate: MenuItem, circadian_phase: str) -> float:
    """Alias to module12_circadian_score."""
    return module12_circadian_score(candidate, circadian_phase)


def novelty_score(session_id: str, item_id: int, candidate: Any = None) -> float:
    """Alias to module11_session_fatigue."""
    return module11_session_fatigue(session_id, item_id, candidate)


def calculate_margin_multiplier(item: MenuItem, anchor_price: float = 100.0) -> float:
    """Alias to module9_margin_multiplier for backward compatibility."""
    return module9_margin_multiplier(item, anchor_price)


# ─────────────────────────────────────────────────────────────────────────────
# MAIN 13-MODULE PIPELINE ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

def evaluate_7tier_pipeline(
    candidates: list[MenuItem],
    context: RecommendationContext,
    anchor_price: float,
) -> tuple[list[dict[str, Any]], str]:
    """
    THE 13-MODULE DETERMINISTIC PIPELINE — Executes in strict 4-Phase order.

    PHASE 1 — HARD EXCLUSIONS & SATURATION GATES
      Modules 1, 7, 4, 8: Dietary Lock → Cart Exclusion → Dual-Role → Kill-Switch

    PHASE 2 — BUDGET & MARGIN PROTECTION
      Modules 5, 9, 13: Hard Price Ceiling → Margin Multiplier → Anti-Gamification

    PHASE 3 — SENSORY & CULINARY LOGIC
      Modules 2, 3, 6, 10: Anti-Redundancy → Flavor/Synergy → Condiment → Sensory

    PHASE 4 — REAL-TIME HEURISTICS
      Modules 11, 12: Session Fatigue → Circadian

    Items failing Phase 1 or Phase 2 hard gates are dropped BEFORE Phase 3 scoring.
    """
    # ── Pre-computation: build cart ID / name sets ──────────────────────────
    cart_ids: set[int] = set()
    cart_name_set: set[str] = set()
    for l in context.cart_lines:
        cid = getattr(l, "item_id", None) or (l.get("item_id") or l.get("id") if isinstance(l, dict) else None)
        if cid is not None:
            cart_ids.add(int(cid))
        cname = getattr(l, "item_name", None) or (l.get("item_name") or l.get("name") if isinstance(l, dict) else None)
        if cname:
            cart_name_set.add(str(cname).strip().lower())
    cart_ids |= context.dismissed_item_ids
    anchor_id = context.anchor_item.id if context.anchor_item else None
    if context.anchor_item and context.anchor_item.name:
        cart_name_set.add(context.anchor_item.name.strip().lower())

    # ── PHASE 1 — PRE-SCORING GATE ───────────────────────────────────────────
    # Module 4: Evaluate meal pillars from current cart
    pillars = module4_evaluate_meal_pillars(context.cart_lines)

    # Module 8: Kill-switch — if all 4 pillars satisfied, halt immediately
    if module8_gatekeeper_kill_switch(pillars):
        return [], "module8_gatekeeper_kill_switch_fired"

    # Determine product page context for Module 5 hard ceiling
    is_product_page = (
        context.intent_mode in ("meal_complete", "MEAL_COMPLETION", "product_tray")
        and anchor_price > 0
    )

    # Determine spice affinity for Module 6 condiment gate bypass
    has_spice_affinity = False
    if context.active_affinity and any(str(k).lower() == "spice" for k in context.active_affinity):
        thresh = int(context.active_affinity.get("Spice", context.active_affinity.get("spice", 4)))
        has_spice_affinity = True  # will be checked per-item
    if context.active_affinities and any(a in ("spicy", "fiery", "peri peri", "peri-peri") for a in context.active_affinities):
        has_spice_affinity = True

    evaluated_candidates = []

    for it in candidates:
        # ── Tier 1: Data Validity ────────────────────────────────────────────
        if not it or not it.id or not it.price or float(it.price.amount if hasattr(it.price, "amount") else it.price) <= 0:
            continue

        # ── Tier 2: Physical Availability ───────────────────────────────────
        if not it.is_in_stock:
            continue
        station = KitchenLoadTracker.map_item_to_station(it)
        if KitchenLoadTracker.get_station_queue(context.branch_id, station) > 15:
            continue

        # ── PHASE 1 / MODULE 1: Dietary Lock ────────────────────────────────
        passed, reason = module1_dietary_lock(it, context.dietary_lock)
        if not passed:
            continue

        # ── PHASE 1 / MODULE 7: Cart Exclusion ──────────────────────────────
        passed, reason = module7_cart_exclusion(it, cart_ids, cart_name_set, anchor_id)
        if not passed:
            continue

        # ── PHASE 1 / MODULE 4 (per-candidate): Pillar suppression ──────────
        # Suppress drink candidates if drink pillar fulfilled
        # Suppress dessert candidates if dessert pillar fulfilled
        cand_cat = _item_category(it)
        if pillars["drink"] and ("drink" in cand_cat or "beverage" in cand_cat):
            continue
        if pillars["dessert"] and ("dessert" in cand_cat or any(w in _item_name(it) for w in ["sundae", "softie", "lava", "mousse", "shake"])):
            continue

        # ── PHASE 1 / MODULE 6 (hard gate part): Condiment gating ───────────
        # Determine per-item spice affinity for condiment gate
        per_item_spice_affinity = has_spice_affinity
        if context.active_affinity and any(str(k).lower() == "spice" for k in context.active_affinity):
            thresh_val = int(context.active_affinity.get("Spice", context.active_affinity.get("spice", 4)))
            per_item_spice_affinity = get_item_spice_level(it) >= thresh_val
        elif context.active_affinities and any(a in ("spicy", "fiery", "peri peri") for a in context.active_affinities):
            per_item_spice_affinity = get_item_spice_level(it) >= 4

        cond_mult, cond_reason = module6_condiment_host_gate(it, context.cart_lines, context.anchor_item, per_item_spice_affinity)
        if cond_mult == 0.0:
            continue  # No host → hard drop (Module 6 kill)

        # ── PHASE 2 / MODULE 5: Hard Price Ceiling ───────────────────────────
        # Effective anchor for sharing-bucket candidates uses total cart spend
        effective_anchor = anchor_price
        cand_sub_role = get_item_sub_role(it)
        if cand_sub_role == "sharing_bucket" or context.velocity_state == "rushed":
            total_cart_spend = sum(
                _item_price(l) * int(getattr(l, "quantity", 1) if not isinstance(l, dict) else (l.get("quantity") or 1))
                for l in context.cart_lines
            )
            if total_cart_spend > anchor_price:
                effective_anchor = total_cart_spend

        passed, reason = module5_hard_price_ceiling(it, anchor_price, is_product_page)
        if not passed:
            continue

        # ── PHASE 2 / MODULE 13: Anti-Gamification ───────────────────────────
        passed, reason = module13_anti_gamification_check(it)
        if not passed:
            continue

        # ── PHASE 3 SCORING begins (candidates have cleared all hard gates) ──

        p_cand = _item_price(it)

        # Price fit score (soft sigmoid for non-product-page; flat 1.0 for product page)
        if is_product_page and cand_sub_role != "sharing_bucket" and context.velocity_state != "rushed":
            s_price = 1.0
        else:
            s_price = price_proximity_score(p_cand, effective_anchor)

        # Requirement 2: Premium Anchor Elasticity (Fixing the Fanta Float Loop)
        # If anchor_price >= 169, completely bypass price proximity penalty for Drink or Dessert
        cand_cat_raw = _item_category(it)
        if anchor_price >= 169.0 and any(k in cand_cat_raw for k in ["drink", "beverage", "dessert"]):
            s_price = 1.0

        # ── PHASE 3 / MODULE 10: Sensory Contrast ────────────────────────────
        s_sensory = module10_sensory_contrast(it, context.anchor_item, context.cart_lines)

        # ── PHASE 4 / MODULE 12: Circadian ───────────────────────────────────
        s_circadian = module12_circadian_score(it, context.circadian_phase)

        # Kitchen load soft pacing signal
        s_kitchen = kitchen_load_score(it, context.branch_id)

        # ── PHASE 4 / MODULE 11: Session Fatigue ─────────────────────────────
        yield_active, yield_reason = is_yield_override_active(it)
        s_novelty = 1.0 if yield_active else module11_session_fatigue(context.session_id, it.id, it)

        # Deterministic bandit expectation (zero random jitter)
        from app.intelligence.recommendation.bandit import ThompsonSamplingBandit
        anchor_cat = str(context.anchor_item.category.value if hasattr(context.anchor_item.category, "value") else context.anchor_item.category) if context.anchor_item else "general"
        s_bandit = ThompsonSamplingBandit.sample_theta(
            time_bucket=context.circadian_phase,
            anchor_category=anchor_cat,
            item_id=it.id,
            deterministic=True,
        )

        features = {
            "price_fit":        round(s_price, 4),
            "sensory_contrast": round(s_sensory, 4),
            "circadian":        round(s_circadian, 4),
            "kitchen_load":     round(s_kitchen, 4),
            "bandit_theta":     round(s_bandit, 4),
            "novelty":          round(s_novelty, 4),
        }

        composite_score = combine_scores(features)

        # ── PHASE 3 / MODULE 2: Anti-Redundancy penalty ──────────────────────
        redundancy_mult = module2_anti_redundancy_score(it, context.anchor_item)
        if redundancy_mult != 1.0:
            composite_score *= redundancy_mult
            features["anti_redundancy_penalty"] = redundancy_mult

        # ── PHASE 3 / MODULE 3A: Flavor Anti-Clash ───────────────────────────
        flavor_penalty = module3_flavor_anti_clash_penalty(it, context.cart_lines)
        if flavor_penalty < 1.0:
            composite_score *= flavor_penalty
            features["flavor_anti_clash_penalty"] = flavor_penalty

        # ── PHASE 3 / MODULE 3B: Cuisine Synergy ─────────────────────────────
        synergy_mult = module3_cuisine_synergy(it, context.anchor_item, context.cart_lines)
        if synergy_mult != 1.0:
            composite_score *= synergy_mult
            features["cuisine_synergy"] = synergy_mult

        # ── Requirement 3: Universal Side Commercial Boost (Fixing the Nugget Drop) ──
        # If candidate name fuzzy-matches "Nugget" or "Fries", apply explicit 1.25x commercial multiplier
        cand_name_lower = _item_name(it)
        if any(w in cand_name_lower for w in ["nugget", "nuggets", "fries", "french fries"]):
            composite_score *= 1.25
            features["universal_side_boost"] = 1.25

        # ── Requirement 5: Thermal Contrast (The Hot/Hot Ban) ──
        # If anchor.temp >= 4 (Hot) and candidate.temp >= 4 (Hot), apply 0.50x damping penalty outside morning
        thermal_mult = module10_thermal_contrast_multiplier(it, context.anchor_item, context.circadian_phase)
        if thermal_mult != 1.0:
            composite_score *= thermal_mult
            features["thermal_contrast_penalty"] = thermal_mult

        # ── PHASE 3 / MODULE 6: Condiment Host Boost (already gated above) ───
        if cond_mult != 1.0:
            composite_score *= cond_mult
            features["condiment_host_boost"] = cond_mult

        # ── PHASE 2 / MODULE 9: Margin Multiplier ────────────────────────────
        margin_mult = module9_margin_multiplier(it, anchor_price)
        if margin_mult != 1.0:
            composite_score *= margin_mult
            features["margin_weight"] = margin_mult

        # ── Velocity Multiplier (Top-Seller Bias) ────────────────────────────
        velocity_mult = calculate_velocity_multiplier(it)
        if velocity_mult != 1.0:
            composite_score *= velocity_mult
            features["velocity_multiplier"] = velocity_mult
            features["conversion_rate"] = get_item_velocity(it)

        # ── Yield Management Override (1.5x boost + fatigue bypass) ──────────
        if yield_active:
            composite_score *= 1.50
            features["yield_boost"] = 1.50
            features["yield_reason"] = yield_reason
            features["session_fatigue_overridden"] = True

        # ── Real-Time Session Heuristics (Module 11/12 phase 4) ──────────────
        if (
            context.active_affinities
            or context.rejected_categories
            or context.active_affinity
            or context.rejected_sub_roles
            or context.velocity_state
        ):
            heuristics_mult, heuristics_meta = evaluate_realtime_heuristics(
                candidate=it,
                active_affinities=context.active_affinities,
                rejected_categories=context.rejected_categories,
                active_affinity=context.active_affinity,
                rejected_sub_roles=context.rejected_sub_roles,
                velocity_state=context.velocity_state,
            )
            if heuristics_mult == 0.0:
                continue  # Sub-role rejection kill
            if heuristics_mult != 1.0:
                composite_score *= heuristics_mult
                features.update(heuristics_meta)

        it_is_veg = bool(
            it.food_type
            and "veg" in str(it.food_type).lower()
            and "non" not in str(it.food_type).lower()
        )

        evaluated_candidates.append({
            "item":            it,
            "item_id":         it.id,
            "name":            it.name,
            "price":           p_cand,
            "category":        str(it.category.value if hasattr(it.category, "value") else it.category),
            "food_type":       "veg" if it_is_veg else "non_veg",
            "proximity_score": round(s_price, 4),
            "kitchen_mult":    round(s_kitchen, 4),
            "score_breakdown": features,
            "composite_score": round(composite_score, 4),
            "tier_fired":      "13_module_deterministic_pipeline",
        })

    evaluated_candidates.sort(key=lambda x: x["composite_score"], reverse=True)
    return evaluated_candidates, "13_module_pipeline_evaluated"
