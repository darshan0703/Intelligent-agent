"""
catalog_meta.py
Lightweight metadata, catalog mappings, and domain classification utilities
extracted from legacy scoring/ranking files.
Zero dependencies on legacy monolithic engines.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Optional

@dataclass
class RecommendationContext:
    """
    Unified context object for recommendation pipeline.
    """
    session_id: str = "default-kiosk-session"
    user_id: Optional[str] = None
    user_profile: Optional[dict[str, Any]] = None
    cart_lines: list[Any] = field(default_factory=list)
    dismissed_item_ids: set[int] = field(default_factory=set)
    dietary_lock: Optional[str] = None
    intent_mode: str = "standard"
    branch_id: int = 1
    circadian_phase: str = "afternoon_dip"
    anchor_item: Optional[Any] = None
    session_context: Optional[dict[str, Any]] = field(default_factory=dict)
    active_affinities: list[str] = field(default_factory=list)
    rejected_categories: list[str] = field(default_factory=list)
    active_affinity: dict[str, Any] = field(default_factory=dict)
    rejected_sub_roles: list[str] = field(default_factory=list)
    velocity_state: Optional[str] = None

    def __post_init__(self):
        if self.cart_lines is None:
            self.cart_lines = []
        if self.dismissed_item_ids is None:
            self.dismissed_item_ids = set()
        if self.session_context is None:
            self.session_context = {}
        if not self.active_affinities and self.session_context:
            self.active_affinities = [str(a).strip().lower() for a in self.session_context.get("active_affinities", []) if a]
        if not self.rejected_categories and self.session_context:
            self.rejected_categories = [str(r).strip().lower() for r in self.session_context.get("rejected_categories", []) if r]
        if not self.active_affinity and self.session_context:
            self.active_affinity = self.session_context.get("active_affinity", {})
        if not self.rejected_sub_roles and self.session_context:
            self.rejected_sub_roles = [str(r).strip().lower() for r in self.session_context.get("rejected_sub_roles", []) if r]
        if self.velocity_state is None and self.session_context:
            self.velocity_state = self.session_context.get("velocity_state")


CATALOG_SPICE_MAP: dict[int, int] = {
    67: 8,   # Peri Peri Fries
    71: 8,   # Saucy Peri Peri Fries
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
    67: "individual_snack", 68: "individual_snack",
    69: "individual_snack", 70: "individual_snack", 71: "individual_snack",
    74: "individual_snack", 75: "individual_snack",
    76: "individual_snack", 77: "individual_snack",
    81: "individual_snack", 82: "individual_snack",
    83: "condiment", 84: "condiment",
    85: "individual_snack",
}


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
    if hasattr(cat, "value"):
        return str(cat.value).lower()
    return str(cat).lower()


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
    return "general"


def classify_beverage_subrole(item: Any) -> str:
    """
    Classifies beverages into:
    - 'sweet_indulgence': heavy milk, thick shake, frappe, float, ice-cream dessert drinks.
    - 'carbonated_hydration': carbonated/acidic hydration (soda, cola, fizz, sprite, juice, water).
    """
    name = _item_name(item)
    desc = f"{getattr(item, 'short_description', '') or ''} {getattr(item, 'long_description', '') or ''}".lower()
    text = f"{name} {desc}"

    if any(w in text for w in ["shake", "frappe", "float", "ice cream", "softie", "cream", "milk", "latte", "cappuccino", "hot chocolate", "mousse"]):
        return "sweet_indulgence"
    return "carbonated_hydration"


def classify_dessert_subrole(item: Any) -> str:
    """
    Classifies desserts into:
    - 'cold_dairy': softie, sundae, shake, ice cream, mousse, float, cold, cone.
    - 'hot_baked': lava cup, waffle, pie, baked, pastry, warm brownie/cake, cookie, muffin, tart.
    """
    name = _item_name(item)
    desc = f"{getattr(item, 'short_description', '') or ''} {getattr(item, 'long_description', '') or ''}".lower()
    text = f"{name} {desc}"

    if any(w in name for w in ["lava", "waffle", "pie", "cake", "brownie", "pastry", "cookie", "muffin", "tart"]):
        return "hot_baked"
    if any(w in text for w in ["softie", "sundae", "shake", "ice cream", "mousse", "float", "cone", "mcflurry"]):
        return "cold_dairy"
    if any(w in text for w in ["lava", "waffle", "pie", "baked", "cake", "brownie", "pastry", "cookie", "muffin", "tart"]):
        return "hot_baked"
    return "cold_dairy"


def is_heavy_dairy_beverage(item: Any) -> bool:
    """
    Dual-Role Saturation check:
    Returns True if beverage fulfills both drink and dessert pillars (heavy shake/frappe/float).
    """
    if not item:
        return False
    cat = _item_category(item)
    if "drink" not in cat and "beverage" not in cat:
        return False
    name = _item_name(item)
    return any(w in name for w in ["shake", "frappe", "float"])


def calculate_effective_anchor(cart_lines: list[Any], default_anchor: float = 100.0) -> float:
    """
    Module 5: Bulk Elastic Budgeting.
    effective_anchor = max(highest_single_entree_price, total_entree_spend / total_entree_qty).
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
        avg_spend = total_entree_spend / total_entrees
        return round(max(highest_main_price, avg_spend), 2)
    return default_anchor


def calculate_velocity_multiplier(candidate: Any) -> float:
    """Velocity Multiplier (Top-Seller Bias). Default 1.0."""
    name = _item_name(candidate)
    if any(k in name for k in ["fries", "coke", "whopper"]):
        return 1.45
    return 1.15


def calculate_yield_boost(candidate: Any) -> float:
    """Yield Boost for perishable/overstock items. Default 1.0."""
    return 1.0

