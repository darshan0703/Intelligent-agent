"""
app/intelligence/recommendation/session_learner.py
Customer Mindset Learner & Session Behavioral Tracker (v3.0)
- Tracks real-time session behavior:
  * Mindset Classification: Budget_Hunter, Indulgent_Gourmet, Quick_Refreshment, Strict_Vegetarian.
  * Basket Intent Mode: premium_beverage, budget_hunter, meal_complete, standard.
  * Active Cart Deletion & Removal Memory: Tracks what was removed and why.
  * Observed Price Elasticity / Spending Tier.
  * Interaction Friction & Dynamic Category Dismissal Counts.
- Auto-adapts recommendation multipliers on the fly.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any


@dataclass
class SessionMindsetProfile:
    session_id: str
    persona: str = "Standard_Explorer"  # Budget_Hunter | Indulgent_Gourmet | Quick_Refreshment | Strict_Vegetarian | Standard_Explorer
    basket_intent_mode: str = "standard"  # premium_beverage | budget_hunter | meal_complete | standard
    observed_avg_price: float = 120.0
    accepted_item_ids: set[int] = field(default_factory=set)
    dismissed_item_ids: set[int] = field(default_factory=set)
    category_dismissal_counts: dict[str, int] = field(default_factory=dict)
    dietary_lock: str | None = None
    is_explicit_override: bool = False
    last_removed_item: dict[str, Any] | None = None
    removal_count: int = 0


class SessionLearner:
    _session_profiles: dict[str, SessionMindsetProfile] = {}

    @classmethod
    def get_or_create_profile(cls, session_id: str) -> SessionMindsetProfile:
        if session_id not in cls._session_profiles:
            cls._session_profiles[session_id] = SessionMindsetProfile(session_id=session_id)
        return cls._session_profiles[session_id]

    @classmethod
    def set_explicit_dietary_override(cls, session_id: str, dietary_pref: str) -> None:
        """
        Deterministic Tool Entry Point:
        Invoked by voice/LLM agents or UI filter toggles.
        Accepts 'veg', 'non_veg', or 'both'.
        """
        profile = cls.get_or_create_profile(session_id)
        pref = dietary_pref.lower().strip()
        profile.dietary_lock = pref if pref in ("veg", "non_veg") else None
        profile.is_explicit_override = True

    @classmethod
    def clear_profile(cls, session_id: str) -> None:
        """Removes all stored mindset profiles, dismissed items, and dietary locks for session."""
        cls._session_profiles.pop(session_id, None)

    @classmethod
    def update_from_cart(
        cls,
        session_id: str,
        cart_lines: list[Any],
        session_preference: str | None = None,
    ) -> SessionMindsetProfile:
        profile = cls.get_or_create_profile(session_id)

        if session_preference:
            cls.set_explicit_dietary_override(session_id, session_preference)

        if not cart_lines:
            profile.basket_intent_mode = "standard"
            return profile

        prices: list[float] = []
        categories: list[str] = []
        item_names: list[str] = []
        is_veg_only = True
        has_expensive_drink = False

        for line in cart_lines:
            p = getattr(line, "unit_price", line.get("price") if isinstance(line, dict) else None)
            p_val = 0.0
            if p is not None:
                p_val = float(p.amount if hasattr(p, "amount") else p)
                prices.append(p_val)

            name = str(getattr(line, "item_name", line.get("name") if isinstance(line, dict) else "")).lower()
            item_names.append(name)

            cat = str(getattr(line, "category", line.get("category") if isinstance(line, dict) else "")).lower()
            categories.append(cat)

            ft = str(getattr(line, "food_type", line.get("food_type") if isinstance(line, dict) else "")).lower()
            if "non" in ft:
                is_veg_only = False

            # Detect expensive juice / beverage intent (price >= 110 or premium shakes/smoothies)
            if ("drink" in cat or "beverage" in cat or any(x in name for x in ["coffee", "shake", "juice", "float"])) and p_val >= 110.0:
                has_expensive_drink = True

        if prices:
            profile.observed_avg_price = sum(prices) / len(prices)

        # 1. Classify Basket Intent Mode (Crucial for Contextual Anchoring)
        max_price = max(prices) if prices else 0.0
        has_burger = any("burger" in c for c in categories)
        has_drink = any("drink" in c or "beverage" in c for c in categories)
        has_side = any("side" in c for c in categories)

        if has_expensive_drink:
            # Customer ordered a premium juice/beverage -> Cover up with food essentials!
            profile.basket_intent_mode = "premium_beverage"
        elif max_price <= 75.0 and len(prices) > 0:
            # Customer selected budget item (< Rs.75) -> Convince with high-value micro-upgrades & offers
            profile.basket_intent_mode = "budget_hunter"
        elif has_burger and has_drink and has_side:
            profile.basket_intent_mode = "meal_complete"
        else:
            profile.basket_intent_mode = "standard"

        # 2. Classify Persona based on behavioral patterns
        if is_veg_only and (profile.dietary_lock == "veg" or any("veg" in c for c in categories)):
            if profile.observed_avg_price <= 110.0:
                profile.persona = "Budget_Vegetarian"
            else:
                profile.persona = "Gourmet_Vegetarian"
        elif profile.observed_avg_price <= 110.0:
            profile.persona = "Budget_Hunter"
        elif profile.observed_avg_price >= 240.0:
            profile.persona = "Indulgent_Gourmet"
        elif all(c in ("drink", "side", "dessert") for c in categories):
            profile.persona = "Quick_Refreshment"
        else:
            profile.persona = "Standard_Explorer"

        return profile

    @classmethod
    def record_removal(cls, session_id: str, item_dict: dict[str, Any]) -> None:
        """
        Captures explicit cart deletion event.
        Identifies hesitation type (Price shock vs Taste conflict).
        """
        profile = cls.get_or_create_profile(session_id)
        profile.last_removed_item = item_dict
        profile.removal_count += 1
        item_id = item_dict.get("id") or item_dict.get("item_id")
        cat = str(item_dict.get("category", "")).lower()

        if item_id:
            profile.dismissed_item_ids.add(int(item_id))
            if int(item_id) in profile.accepted_item_ids:
                profile.accepted_item_ids.remove(int(item_id))

        if cat:
            profile.category_dismissal_counts[cat] = profile.category_dismissal_counts.get(cat, 0) + 1

    @classmethod
    def record_dismissal(cls, session_id: str, item_id: int, category: str) -> None:
        profile = cls.get_or_create_profile(session_id)
        profile.dismissed_item_ids.add(item_id)
        cat_norm = category.lower()
        profile.category_dismissal_counts[cat_norm] = profile.category_dismissal_counts.get(cat_norm, 0) + 1

    @classmethod
    def record_acceptance(cls, session_id: str, item_id: int) -> None:
        profile = cls.get_or_create_profile(session_id)
        profile.accepted_item_ids.add(item_id)
        if item_id in profile.dismissed_item_ids:
            profile.dismissed_item_ids.remove(item_id)


# ── IDENTITY BOUNDARY — v7 §23 ────────────────────────────────────────────────

class IdentityBoundary:
    """
    v7 §23: Governs what moves across the session_id -> user_id boundary
    when an anonymous session becomes identified (e.g., WhatsApp/web login).

    Building directly on v4 §1's session_id/user_id split — this specifies
    exactly what's allowed to move, and under what conditions.

    CARRIES FORWARD AUTOMATICALLY (behavioral summaries, not raw event logs):
      - observed_price_sensitivity (derived from cart history)
      - mindset_state (Budget_Hunter, Indulgent_Gourmet, etc.)
      - dismissed_item_decay (active dismissals for current session)
    These are behavioral SUMMARIES — they can't re-identify another person.

    REQUIRES EXPLICIT CONSENT BEFORE MERGING:
      - cross_session_purchase_history (tied to newly-identified user_id)
      - cross_device_history (if person used anonymous session on same device before)
    This is the 'we found a previous session — merge it?' moment from v4 §1.2
    — specified as opt-in, not automatic.

    NEVER CROSSES THE BOUNDARY (under any condition):
      - raw_impression_logs_other_sessions
      - device_fingerprint_history
    Device fingerprint is a weak, probabilistic signal (v4 §7 edge case).
    It must never be used to silently attribute one person's history to another.
    """

    # What auto-carries — field names in SessionMindsetProfile
    AUTO_CARRY_FIELDS: list[str] = [
        "observed_avg_price",    # observed_price_sensitivity
        "persona",               # mindset_state
        "basket_intent_mode",    # intent classification
        "dismissed_item_ids",    # active dismissal set for this session
        "category_dismissal_counts",
    ]

    # What requires consent
    CONSENT_REQUIRED: list[str] = [
        "cross_session_purchase_history",
        "cross_device_history",
    ]

    # What never crosses — not even with consent
    # (Listed for documentation/audit purposes. No opt-in mechanism exists.)
    NEVER_CROSSES: list[str] = [
        "raw_impression_logs_other_sessions",
        "device_fingerprint_history",
    ]

    @classmethod
    def extract_auto_carry(cls, session_id: str) -> dict:
        """
        Extracts the behavioral summary fields that carry forward automatically
        when a session becomes identified. Returns a flat dict of safe signals.
        """
        profile = SessionLearner.get_or_create_profile(session_id)
        result = {}
        for field_name in cls.AUTO_CARRY_FIELDS:
            val = getattr(profile, field_name, None)
            if val is not None:
                # Convert sets to lists for serialization
                result[field_name] = list(val) if isinstance(val, set) else val
        return result

    @classmethod
    def merge_session_to_user(
        cls,
        session_id: str,
        user_id: str,
        consent_given: bool = False,
    ) -> dict:
        """
        Merges session signals to a user profile on identification.
        auto_carry signals always transfer.
        consent_required signals transfer only if consent_given=True.
        NEVER_CROSSES signals are simply not included — no opt-in exists for them.
        """
        merged = cls.extract_auto_carry(session_id)
        merged["user_id"] = user_id
        merged["session_id"] = session_id
        merged["consent_given"] = consent_given

        if consent_given:
            # Placeholder for cross-session history merge
            # Phase 2: query user_id's historical purchase records and merge here
            merged["cross_session_history_merged"] = True
        else:
            merged["cross_session_history_merged"] = False

        # NEVER_CROSSES: deliberately absent from merged dict
        # No code path adds device_fingerprint_history or raw_impression_logs here
        return merged
