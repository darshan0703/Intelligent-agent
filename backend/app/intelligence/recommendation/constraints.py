"""
app/intelligence/recommendation/constraints.py
Override Hierarchy — v7 §15 and §21

v7 Rule: The hierarchy is enforced in code as a strict short-circuit, in exact order.
No scoring step is permitted to reach a higher tier. A recommendation score, however
high, CANNOT promote an item past tiers 1-4. Those tiers are pass/fail gates the
candidate must already have cleared before it is eligible for tier 5 scoring.

Tier 1: Safety / Legal (age-restricted items, allergen locks) — hardcoded, no config override
Tier 2: Transaction Correctness (price > 0, item exists, inventory) — deterministic zone
Tier 3: Hard Business Policy (dietary lock, regional restriction)
Tier 4: Customer Constraints (explicit preferences/exclusions the customer set)
Tier 5: Intelligence (entire v6 ranking/candidate pipeline) — runs ONLY on survivors of 1-4
Tier 6: Exploration (bandit-driven discovery)

The deterministic/AI boundary (§15): The LLM/ranker can decide what to say or which
items look best; it can NEVER decide what's true (stock, price, policy).
"""
from __future__ import annotations
from decimal import Decimal
from typing import Any
from app.domain.catalog.entities import MenuItem
from app.domain.session.entities import SessionState
from app.intelligence.recommendation.data_quality_gate import CulinaryTagger


UNIVERSAL_SIDES: list[str] = ["Chicken Nuggets", "Fries", "Medium Fries", "Large Fries"]


class AntiRedundancyConstraint:
    """
    v7 Anti-Redundancy Constraint:
    In MEAL_COMPLETION mode, penalizes / suppresses sides that share identical base ingredients
    with the anchor item (e.g., do not pair potato patty burgers with potato hashbrowns;
    prioritize pizza puffs or veggie strips instead).

    Commercial Fast-Food Reality Override:
    UNIVERSAL_SIDES (e.g. Chicken Nuggets, French Fries) completely bypass the base ingredient
    redundancy penalty so that high-margin pairings (like Chicken Nuggets with a Chicken Burger)
    are permitted.
    """

    UNIVERSAL_SIDES: list[str] = UNIVERSAL_SIDES

    @classmethod
    def is_universal_side(cls, candidate: MenuItem | str | dict | None) -> bool:
        """
        Returns True if candidate matches the UNIVERSAL_SIDES list.
        Uses substring matching (e.g. if 'nuggets' or 'fries' in item.name: bypass_redundancy()).
        Allows Chicken Nuggets alongside Chicken Burgers, and Fries alongside potato burgers.
        """
        if not candidate:
            return False
        if hasattr(candidate, "name"):
            name = str(candidate.name).strip().lower()
        elif isinstance(candidate, dict):
            name = str(candidate.get("name") or candidate.get("item_name") or "").strip().lower()
        else:
            name = str(candidate).strip().lower()

        # Direct substring match check for universal fast-food craving items
        if any(w in name for w in ["nugget", "nuggets", "fries", "french fries", "wing", "wings", "bucket"]):
            return True
        from app.intelligence.recommendation.catalog_meta import get_item_sub_role
        if get_item_sub_role(candidate) == "sharing_bucket":
            return True
        for u in cls.UNIVERSAL_SIDES:
            if u.lower() in name or name in u.lower():
                return True
        return False

    @staticmethod
    def extract_base_ingredient(item: MenuItem | str | None) -> str | None:
        if not item:
            return None
        if isinstance(item, str):
            name_text = item.lower()
            text = name_text
        else:
            name_text = item.name.lower()
            desc = f"{getattr(item, 'short_description', '') or ''} {getattr(item, 'long_description', '') or ''}".lower()
            text = f"{name_text} {desc}"

        # Distinct savory sides: Veggie strips and puffs are mixed vegetable, not potato
        if any(w in name_text for w in ["veggie strip", "vegetable strip", "pizza puff"]):
            return "mixed_veg"
        if any(w in name_text for w in ["dip", "sauce"]):
            return "condiment"

        # Chicken base
        if any(w in name_text for w in ["chicken", "wings", "nuggets", "chicken whopper", "bk chicken"]):
            return "chicken"
        # Paneer base
        if any(w in name_text for w in ["paneer"]):
            return "paneer"
        # Cheese base
        if any(w in name_text for w in ["cheese", "cheesy"]):
            return "cheese"

        # Potato base: potato patty burgers (Crispy Veg, Veg Makhani), hashbrowns, and fries
        if any(w in name_text for w in ["hashbrown", "crispy veg", "veg makhani", "fries", "aloo", "potato"]):
            return "potato"
        if any(w in text for w in ["hashbrown", "aloo", "potato patty"]):
            return "potato"
        return None

    @classmethod
    def is_redundant_side(cls, candidate: Any, anchor_item: MenuItem | str | None) -> bool:
        if not anchor_item:
            return False

        # TASK 1: UNIVERSAL CRAVING OVERRIDE - Checked first via substring match!
        # If candidate item matches UNIVERSAL_SIDES (e.g. Nuggets, Fries), completely bypass redundancy.
        if cls.is_universal_side(candidate):
            return False

        cand_cat = str(
            getattr(candidate.category, "value", None)
            if hasattr(candidate, "category") and hasattr(candidate.category, "value")
            else getattr(candidate, "category", "")
        ).lower()
        if "side" not in cand_cat:
            return False

        cand_base = cls.extract_base_ingredient(candidate)
        anchor_base = cls.extract_base_ingredient(anchor_item)
        return bool(cand_base and anchor_base and cand_base == anchor_base)

    @classmethod
    def extract_dominant_flavor(cls, item: MenuItem | str | dict | None) -> str | None:
        """Extracts dominant_flavor using CulinaryTagger."""
        return CulinaryTagger.get_dominant_flavor(item)

    @classmethod
    def has_flavor_clash(cls, candidate: MenuItem, cart_items: list[Any] | None) -> tuple[bool, str | None]:
        """
        Checks whether candidate shares the exact dominant flavor with any item already in the cart.
        (e.g., Mango Shake in cart + Mango Sundae recommended -> True, 'mango').
        """
        cand_flavor = cls.extract_dominant_flavor(candidate)
        if not cand_flavor or not cart_items:
            return False, None

        for it in cart_items:
            cart_flavor = cls.extract_dominant_flavor(it)
            if cart_flavor and cart_flavor == cand_flavor:
                return True, cand_flavor
        return False, None

    @classmethod
    def evaluate_flavor_redundancy_penalty(
        cls, candidate: Any, cart_items: list[Any] | None, mode: str = "MEAL_COMPLETION"
    ) -> float:
        """
        In MEAL_COMPLETION mode, if candidate shares exact dominant_flavor
        with any item already in the cart, apply a severe penalty multiplier.
        If 'Mango' is in any cart item name, apply a 0.1x penalty multiplier to any candidate containing 'Mango'.
        """
        if not cart_items:
            return 1.0

        cand_name = str(getattr(candidate, "name", "") or (candidate.get("name") if isinstance(candidate, dict) else "")).lower()

        # Explicit Mango Anti-Clash check
        has_mango_cart = any(
            "mango" in str(getattr(it, "name", "") or (it.get("name") or it.get("item_name") if isinstance(it, dict) else "")).lower()
            for it in cart_items
        )
        if has_mango_cart and "mango" in cand_name:
            return 0.25

        if mode in ("MEAL_COMPLETION", "meal_complete", "CLOSURE"):
            has_clash, clash_flavor = cls.has_flavor_clash(candidate, cart_items)
            if has_clash:
                return 0.25
        return 1.0

    @classmethod
    def evaluate_redundancy_penalty(
        cls,
        candidate: MenuItem,
        anchor_item: MenuItem | str | None,
        mode: str = "MEAL_COMPLETION",
        cart_items: list[Any] | None = None,
    ) -> float:
        penalty = 1.0
        if mode in ("MEAL_COMPLETION", "meal_complete", "CLOSURE") and cls.is_redundant_side(candidate, anchor_item):
            penalty *= 0.35  # Heavy 65% base anti-redundancy penalty
        if mode in ("MEAL_COMPLETION", "meal_complete", "CLOSURE") and cart_items:
            penalty *= cls.evaluate_flavor_redundancy_penalty(candidate, cart_items, mode=mode)
        return penalty


class OverrideHierarchy:
    """
    v7 §21: Strict short-circuit filter applied before any candidate reaches scoring.
    Each tier returns (passed: bool, reason: str) — the reason is recorded in DecisionTrace.
    """

    @staticmethod
    def _tier1_safety_legal(item: MenuItem) -> tuple[bool, str]:
        """
        Tier 1: Safety / Legal.
        Hardcoded — no configuration can override this tier.
        Phase 1: no age-restricted items in BK catalog, so this tier is always pass.
        Phase 2: add allergen codes, regulatory restrictions by region.
        """
        # Price must be a positive number — a zero-price item is a data error, not a deal
        if not item.price:
            return False, "tier1_null_price"
        price_val = float(item.price.amount) if hasattr(item.price, "amount") else float(item.price)
        if price_val < 0:
            return False, "tier1_negative_price"
        return True, "tier1_passed"

    @staticmethod
    def _tier2_transaction_correctness(item: MenuItem) -> tuple[bool, str]:
        """
        Tier 2: Transaction Correctness — the deterministic zone.
        Money and stock are never approximated or interpreted by AI.
        """
        # Physical availability
        if not item.is_available:
            return False, "tier2_unavailable"
        # Inventory check (if inventory snapshot present)
        if item.inventory is not None and item.inventory.stock <= 0:
            return False, "tier2_out_of_stock"
        # Price must be positive and parseable
        try:
            p = float(item.price.amount) if hasattr(item.price, "amount") else float(item.price)
            if p <= 0:
                return False, "tier2_zero_price"
        except (TypeError, ValueError):
            return False, "tier2_invalid_price"
        return True, "tier2_passed"

    @staticmethod
    def _tier3_business_policy(
        item: MenuItem,
        suppressed_categories: set[str],
        branch_id: int = 1,
    ) -> tuple[bool, str]:
        """
        Tier 3: Hard Business Policy.
        Regional restrictions, category saturation suppression.
        These are operator-level policies, not customer preferences.
        """
        item_cat = str(
            item.category.value if hasattr(item.category, "value") else item.category
        ).lower()
        if suppressed_categories and item_cat in {c.lower() for c in suppressed_categories}:
            return False, f"tier3_category_suppressed:{item_cat}"
        return True, "tier3_passed"

    @classmethod
    def _tier4_customer_constraints(
        cls,
        item: MenuItem,
        session: SessionState,
        rejected_item_ids: set[int],
        cart_item_ids: set[int],
        anchor_price: Decimal | None,
        max_price_ratio: float,
        anchor_item: MenuItem | None = None,
        mode: str = "",
        cart_item_names: set[str] | None = None,
    ) -> tuple[bool, str]:
        """
        Tier 4: Customer Constraints — explicit preferences and exclusions.
        These reflect what the customer has explicitly told us or done.
        """
        # Absolute Cart Exclusion (Code Red: check ID and Name)
        if CartExclusionConstraint.is_in_cart(item, cart_item_ids=cart_item_ids, cart_item_names=cart_item_names):
            return False, "cart_exclusion"

        # Dismissed items
        if rejected_item_ids and item.id in rejected_item_ids:
            return False, "tier4_dismissed_item"

        # Strict dietary preference (Code Red: Forcefully eradicate all Non-Veg SKUs when veg preference locked)
        if session.food_preference:
            pref = session.food_preference.lower()
            food_type = str(
                item.food_type.value if hasattr(item.food_type, "value") else item.food_type
            ).lower() if item.food_type else ""
            item_name = (item.name or "").lower()
            if pref == "veg":
                has_meat = any(w in item_name for w in ["chicken", "wings", "nugget", "nuggets", "mutton", "fish", "beef"]) or any(w in item_name.replace("(", " ").replace(")", " ").replace("-", " ").split() for w in ["egg", "eggs"])
                if "non" in food_type or has_meat:
                    return False, "tier4_dietary_veg_lock"

        # Price proximity hard ceiling (customer budget constraint)
        item_cat = str(
            item.category.value if hasattr(item.category, "value") else item.category
        ).lower()
        if anchor_price is not None and anchor_price > Decimal("0"):
            item_price = item.price.amount if hasattr(item.price, "amount") else Decimal(str(item.price))
            # Sharing buckets (group/party bulk items) bypass single-portion budget ceilings
            from app.intelligence.recommendation.catalog_meta import get_item_sub_role
            is_sharing = get_item_sub_role(item) == "sharing_bucket"
            if not is_sharing and anchor_price <= Decimal("150.00") and item_cat != "burger":
                if item_price > (anchor_price * Decimal(str(max_price_ratio))):
                    return False, f"tier4_price_ceiling_exceeded:{float(item_price):.0f}>{float(anchor_price * Decimal(str(max_price_ratio))):.0f}"

        # Anti-Redundancy Constraint in MEAL_COMPLETION mode
        # Suppress sides sharing identical base ingredient with anchor item
        if mode in ("MEAL_COMPLETION", "meal_complete", "CLOSURE") and anchor_item is not None:
            if AntiRedundancyConstraint.is_redundant_side(item, anchor_item):
                return False, "tier4_anti_redundancy_clash"

        return True, "tier4_passed"

    @classmethod
    def apply(
        cls,
        item: MenuItem,
        session: SessionState,
        suppressed_categories: set[str] | None = None,
        rejected_item_ids: set[int] | None = None,
        cart_item_ids: set[int] | None = None,
        anchor_price: Decimal | None = None,
        max_price_ratio: float = 2.5,
        branch_id: int = 1,
        anchor_item: MenuItem | None = None,
        mode: str = "",
        cart_item_names: set[str] | None = None,
    ) -> tuple[bool, str]:
        """
        Applies all four tiers in strict order. Returns (eligible, reason).
        Short-circuits immediately on first failure — no tier can be skipped.
        """
        passed, reason = cls._tier1_safety_legal(item)
        if not passed:
            return False, reason

        passed, reason = cls._tier2_transaction_correctness(item)
        if not passed:
            return False, reason

        passed, reason = cls._tier3_business_policy(
            item, suppressed_categories or set(), branch_id
        )
        if not passed:
            return False, reason

        passed, reason = cls._tier4_customer_constraints(
            item,
            session,
            rejected_item_ids or set(),
            cart_item_ids or set(),
            anchor_price,
            max_price_ratio,
            anchor_item=anchor_item,
            mode=mode,
            cart_item_names=cart_item_names,
        )
        if not passed:
            return False, reason

        return True, "eligible_for_scoring"


class CartExclusionConstraint:
    """
    Absolute Cart Exclusion (Code Red):
    Parses exact item_id and item_name from the incoming JSON payload and permanently drops them.
    Zero exceptions.
    """

    @classmethod
    def is_in_cart(
        cls,
        item: MenuItem | Any,
        cart_item_ids: set[int] | list[int] | None = None,
        cart_item_names: set[str] | list[str] | None = None,
    ) -> bool:
        if not item:
            return False

        cand_id = getattr(item, "id", None)
        if cand_id is None and isinstance(item, dict):
            cand_id = item.get("id") or item.get("item_id")
        if cand_id is not None and cart_item_ids and int(cand_id) in set(cart_item_ids):
            return True

        cand_name = str(getattr(item, "name", "") or (item.get("name") if isinstance(item, dict) else "")).strip().lower()
        if not cand_name:
            return False

        if cart_item_names:
            import re
            clean_cand = re.sub(r"\s*\(.*?\)", "", cand_name).strip()
            for c_name in cart_item_names:
                clean_cart_raw = str(c_name).strip().lower()
                clean_cart = re.sub(r"\s*\(.*?\)", "", clean_cart_raw).strip()
                if cand_name == clean_cart_raw:
                    return True
                if clean_cand and clean_cart and clean_cand == clean_cart:
                    return True
                if len(clean_cart) >= 4 and (clean_cart in cand_name or cand_name in clean_cart):
                    return True
        return False

    @classmethod
    def filter_cart_candidates(
        cls,
        candidates: list[MenuItem],
        cart_item_ids: set[int] | list[int] | None = None,
        cart_item_names: set[str] | list[str] | None = None,
    ) -> list[MenuItem]:
        return [c for c in candidates if not cls.is_in_cart(c, cart_item_ids, cart_item_names)]


class ConstraintFilter:
    """
    Backward-compatible wrapper around OverrideHierarchy.
    Existing callers in engine.py use this interface.
    Internally delegates to the strict OverrideHierarchy.apply() short-circuit.
    """

    def filter_candidates(
        self,
        candidates: list[MenuItem],
        session: SessionState,
        cart_item_ids: set[int] | None = None,
        rejected_item_ids: set[int] | None = None,
        suppressed_categories: set[str] | None = None,
        anchor_price: Decimal | None = None,
        max_price_ratio: float = 2.5,
        branch_id: int = 1,
        anchor_item: MenuItem | None = None,
        mode: str = "",
        cart_item_names: set[str] | None = None,
    ) -> list[MenuItem]:
        """
        Filters candidates through the four-tier OverrideHierarchy.
        Returns only items that cleared all tiers and are eligible for scoring.
        """
        # Absolute Cart Exclusion (Code Red)
        if mode in ("MEAL_COMPLETION", "meal_complete", "CLOSURE", "meal_upgrade"):
            candidates = CartExclusionConstraint.filter_cart_candidates(candidates, cart_item_ids, cart_item_names)

        valid: list[MenuItem] = []
        for item in candidates:
            eligible, _ = OverrideHierarchy.apply(
                item=item,
                session=session,
                suppressed_categories=suppressed_categories,
                rejected_item_ids=rejected_item_ids,
                cart_item_ids=cart_item_ids,
                anchor_price=anchor_price,
                max_price_ratio=max_price_ratio,
                branch_id=branch_id,
                anchor_item=anchor_item,
                mode=mode,
                cart_item_names=cart_item_names,
            )
            if eligible:
                valid.append(item)
        return valid

    def filter_with_reasons(
        self,
        candidates: list[MenuItem],
        session: SessionState,
        cart_item_ids: set[int] | None = None,
        rejected_item_ids: set[int] | None = None,
        suppressed_categories: set[str] | None = None,
        anchor_price: Decimal | None = None,
        max_price_ratio: float = 2.5,
        branch_id: int = 1,
        anchor_item: MenuItem | None = None,
        mode: str = "",
        cart_item_names: set[str] | None = None,
    ) -> tuple[list[MenuItem], list[str]]:
        """
        Extended version that also returns the filter reason per candidate.
        Used by engine.py when building the full DecisionTrace (§19).
        """
        # Absolute Cart Exclusion (Code Red)
        if mode in ("MEAL_COMPLETION", "meal_complete", "CLOSURE", "meal_upgrade"):
            candidates = CartExclusionConstraint.filter_cart_candidates(candidates, cart_item_ids, cart_item_names)

        valid: list[MenuItem] = []
        filters_applied: list[str] = []
        for item in candidates:
            eligible, reason = OverrideHierarchy.apply(
                item=item,
                session=session,
                suppressed_categories=suppressed_categories,
                rejected_item_ids=rejected_item_ids,
                cart_item_ids=cart_item_ids,
                anchor_price=anchor_price,
                max_price_ratio=max_price_ratio,
                branch_id=branch_id,
                anchor_item=anchor_item,
                mode=mode,
                cart_item_names=cart_item_names,
            )
            if eligible:
                valid.append(item)
            else:
                filters_applied.append(reason)
        return valid, filters_applied
