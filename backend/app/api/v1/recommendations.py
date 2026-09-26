"""
app/api/v1/recommendations.py
Stateless API Routing Layer (Controllers/Routers) for TheAtom Recommendation Engine.

Exposes the governed intelligence pipeline to the React frontend:
1. Product Detail Endpoint (GET /product/{item_id}) -> MEAL_COMPLETION
2. Category Spotlight Endpoint (GET /spotlight/{category}) -> DISCOVERY
3. Pre-Checkout / Cart Drawer Endpoint (POST /checkout) -> MEAL_COMPLETION & UPGRADE
4. Make It A Meal Upgrade Endpoint (GET /meal-upgrade/{anchor_item_id}) -> UPGRADE_BUNDLE
"""
from __future__ import annotations

import time
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.domain.catalog.entities import MenuItem
from app.domain.catalog.value_objects import Price, CategorySlug, FoodType, ServingType
from app.domain.session.entities import SessionState
from app.infrastructure.db.models import MealUpgradeRule, MenuItem as MenuItemORM
from app.infrastructure.db.connection import get_async_session_maker
from app.infrastructure.repositories.catalog_repository import (
    SQLAlchemyCatalogRepository,
    get_category_default_image,
)
from app.infrastructure.repositories.session_repository import RedisSessionRepository
from app.application.session_service import SessionService
from app.intelligence.recommendation.catalog_meta import (
    RecommendationContext,
    calculate_effective_anchor,
    get_item_sub_role,
    get_item_spice_level,
    calculate_velocity_multiplier,
    calculate_yield_boost,
    _item_name,
    classify_beverage_subrole,
    classify_dessert_subrole,
    is_heavy_dairy_beverage,
)
from app.intelligence.recommendation.pipeline_runner import (
    evaluate_7tier_pipeline,
    run_recommendation_pipeline,
)
from app.intelligence.recommendation.constraints import (
    AntiRedundancyConstraint,
    OverrideHierarchy,
    ConstraintFilter,
    CartExclusionConstraint,
)
from app.application.cart_service import CartService
from app.intelligence.recommendation.data_quality_gate import CulinaryTagger
from app.intelligence.recommendation.heuristics.circadian_clock import CircadianCravingAnalyzer
from app.intelligence.recommendation.presentation import BADGE_RULES, PresentationLayer
from app.intelligence.recommendation.session_learner import SessionLearner
from app.observability.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/recommendations", tags=["recommendations"])

_catalog_repo = SQLAlchemyCatalogRepository()
_session_repo = RedisSessionRepository()
_session_service = SessionService(_session_repo)
_cart_service = CartService(_catalog_repo)
_constraint_filter = ConstraintFilter()


# ── REQUEST MODELS ────────────────────────────────────────────────────────────

class SessionContextPayload(BaseModel):
    active_affinities: list[str] = Field(default_factory=list, description="Immediate user craving tags e.g. ['spicy', 'chicken']")
    rejected_categories: list[str] = Field(default_factory=list, description="Explicitly rejected categories e.g. ['drinks']")
    active_affinity: dict[str, Any] = Field(default_factory=dict, description="Active scalar attribute affinity e.g. {'Spice': 4}")
    rejected_sub_roles: list[str] = Field(default_factory=list, description="Explicitly rejected sub-roles e.g. ['thick_shake', 'hot_coffee']")
    velocity_state: Optional[str] = Field(default=None, description="Velocity state e.g. 'rushed'")


class CheckoutRecommendationRequest(BaseModel):
    session_id: str = Field(default="default-kiosk-session", description="Unique session ID")
    cart_lines: list[Any] = Field(default_factory=list, description="Array of item_ids or cart line objects")
    branch_id: int = Field(default=1, description="Store branch ID")
    circadian_hour: Optional[int] = Field(default=None, description="Optional override for biological hour")
    session_context: Optional[SessionContextPayload | dict[str, Any]] = Field(default=None, description="Ephemeral real-time session heuristics")


# ── SERIALIZATION HELPER ──────────────────────────────────────────────────────

def serialize_recommendation_item(
    item: MenuItem,
    badge: str = "⭐ Best Match",
    synergy_reason: str = "Recommended pairing to complete your meal",
) -> dict[str, Any]:
    """Formats domain MenuItem into standard frontend JSON contract."""
    price_val = float(item.price.amount if hasattr(item.price, "amount") else item.price)
    fallback = get_category_default_image(item.category, item.name)
    img = item.image or fallback
    if img and not img.startswith("http") and not img.startswith("/"):
        img = "/" + img

    food_type_str = "veg"
    if item.food_type:
        ft_val = str(item.food_type.value if hasattr(item.food_type, "value") else item.food_type).lower()
        if "non" in ft_val:
            food_type_str = "non veg"

    cat_str = str(item.category.value if hasattr(item.category, "value") else item.category).lower()
    if "burger" in cat_str:
        cat_norm = "burger"
    elif "drink" in cat_str or "beverage" in cat_str:
        cat_norm = "drink"
    elif "side" in cat_str:
        cat_norm = "side"
    elif "dessert" in cat_str:
        cat_norm = "dessert"
    else:
        cat_norm = cat_str

    return {
        "id": item.id,
        "name": item.name,
        "price": price_val,
        "original_price": price_val,
        "offer_price": price_val,
        "has_micro_deal": False,
        "discount_pct": 0,
        "deal_tag": None,
        "image": img,
        "category": cat_norm,
        "foodType": food_type_str,
        "food_type": food_type_str,
        "shortDescription": item.short_description or item.name,
        "short_description": item.short_description or item.name,
        "badge": badge,
        "synergy_reason": synergy_reason,
    }


async def _resolve_session(session_id: str, food_preference: str | None = None) -> SessionState:
    """Retrieves session from repository or creates clean in-memory state."""
    session = await _session_service.get_session(session_id)
    profile = SessionLearner.get_or_create_profile(session_id)

    if food_preference is not None:
        SessionLearner.set_explicit_dietary_override(session_id, food_preference)

    effective_pref = profile.dietary_lock or food_preference
    if not effective_pref:
        if session and session.food_preference:
            effective_pref = session.food_preference

    if not session:
        session = SessionState(
            session_id=session_id,
            tenant_id="tenant-bk",
            channel="kiosk",
            current_screen=None,
            food_preference=effective_pref,
            last_category=None,
            last_item_id=None,
            conversation_history=[],
            created_at=datetime.now(timezone.utc),
            last_active_at=datetime.now(timezone.utc),
            is_active=True,
        )
    else:
        if food_preference is not None:
            session.food_preference = food_preference
        elif effective_pref:
            session.food_preference = effective_pref

    if effective_pref and not profile.dietary_lock:
        profile.dietary_lock = effective_pref

    return session


# ── 1. PRODUCT DETAIL ENDPOINT (ProductPage.jsx) ──────────────────────────────

@router.get("/product/{item_id}")
async def get_product_recommendations(
    item_id: int,
    session_id: str = Query("default-kiosk-session"),
    branch_id: int = Query(1),
    dietary_preference: Optional[str] = Query(None, alias="preference"),
    session_context: Optional[str] = Query(None),
    cart_payload: Optional[str] = Query(None),
    cart_lines: Optional[str] = Query(None),
):
    """
    Product Detail Endpoint (For ProductPage.jsx).
    Job: MEAL_COMPLETION.
    Evaluates the anchor item and returns a strict 3-pillar complementary tray
    [Slot 1: Side], [Slot 2: Drink], [Slot 3: Dessert]
    using sensory contrast, real-time session heuristics, universal cart exclusion,
    and anti-redundancy constraints.
    """
    t0 = time.time()
    anchor = await _catalog_repo.get_by_id(item_id, branch_id)
    if not anchor:
        raise HTTPException(status_code=404, detail="Anchor product not found")

    anchor_is_veg = bool(
        anchor.food_type
        and "veg" in str(anchor.food_type).lower()
        and "non" not in str(anchor.food_type).lower()
    )
    anchor_cat_raw = str(
        anchor.category.value if hasattr(anchor.category, "value") else anchor.category
    ).lower()

    # Requirement 6: Strict 3-Pillar UI Formatting [Slot 1: Side, Slot 2: Drink, Slot 3: Dessert]
    if "drink" in anchor_cat_raw or "beverage" in anchor_cat_raw:
        complementary_roles = ["side", "burger", "dessert"]
    elif "side" in anchor_cat_raw:
        complementary_roles = ["drink", "burger", "dessert"]
    elif "dessert" in anchor_cat_raw:
        complementary_roles = ["burger", "drink", "side"]
    else:
        # Standard entree/burger page: strictly Side, Drink, Dessert
        complementary_roles = ["side", "drink", "dessert"]

    profile = SessionLearner.get_or_create_profile(session_id)
    dismissed_ids = set(profile.dismissed_item_ids)

    session_ctx_dict = {}
    if session_context:
        try:
            import json
            session_ctx_dict = json.loads(session_context) if isinstance(session_context, str) else session_context
        except Exception:
            pass

    # Resolve Explicit UI Filter
    pref_param = (dietary_preference or "").strip().lower()
    pref_from_ctx = str(session_ctx_dict.get("preference") or session_ctx_dict.get("food_preference") or "").strip().lower()
    if pref_param in ("veg", "non_veg", "non veg", "both"):
        SessionLearner.set_explicit_dietary_override(session_id, pref_param)
    elif pref_from_ctx in ("veg", "non_veg", "non veg", "both"):
        SessionLearner.set_explicit_dietary_override(session_id, pref_from_ctx)

    explicit_veg_filter = (
        pref_param == "veg"
        or pref_from_ctx == "veg"
        or (profile.dietary_lock == "veg")
    )
    explicit_non_veg_filter = (
        pref_param in ("non_veg", "non veg")
        or pref_from_ctx in ("non_veg", "non veg")
        or (profile.dietary_lock in ("non_veg", "non veg"))
    )

    # Requirement 1: Eradicate Cart Blindness (Universal Cart Exclusion)
    parsed_cart: list[Any] = []
    cart_raw = cart_payload or cart_lines
    if cart_raw:
        if isinstance(cart_raw, str):
            try:
                import json
                loaded = json.loads(cart_raw)
                if isinstance(loaded, list):
                    parsed_cart = loaded
                elif isinstance(loaded, dict):
                    parsed_cart = [loaded]
            except Exception:
                # Comma separated IDs fallback: "30,10"
                parsed_cart = [{"item_id": int(x.strip())} for x in cart_raw.split(",") if x.strip().isdigit()]
        elif isinstance(cart_raw, list):
            parsed_cart = cart_raw

    # Fallback to session_context if cart was passed inside session_context
    if not parsed_cart and session_ctx_dict:
        if session_ctx_dict.get("cart"):
            parsed_cart = session_ctx_dict.get("cart")
        elif session_ctx_dict.get("cart_lines"):
            parsed_cart = session_ctx_dict.get("cart_lines")

    cart_item_ids: set[int] = set()
    cart_item_names: set[str] = set()
    has_cart_meat = False
    has_cart_veg_entree = False
    total_cart_qty = 0

    for entry in parsed_cart:
        cid = None
        cname = None
        qty = 1
        c_type = ""
        c_cat = ""
        if isinstance(entry, (int, str)) and str(entry).isdigit():
            cid = int(entry)
        elif isinstance(entry, dict):
            cid = entry.get("item_id") or entry.get("id")
            cname = entry.get("item_name") or entry.get("name")
            qty = entry.get("quantity", 1)
            c_type = str(entry.get("food_type") or entry.get("type") or "").lower()
            c_cat = str(entry.get("category") or "").lower()
        elif hasattr(entry, "id"):
            cid = getattr(entry, "id", None)
            cname = getattr(entry, "name", None)
            qty = getattr(entry, "quantity", 1)
            c_type = str(getattr(entry, "food_type", "")).lower()
            c_cat = str(getattr(entry, "category", "")).lower()

        try:
            total_cart_qty += int(qty or 1)
        except (ValueError, TypeError):
            total_cart_qty += 1

        if cid is not None:
            try:
                cart_item_ids.add(int(cid))
            except (ValueError, TypeError):
                pass
        if cname:
            cn_lower = str(cname).strip().lower()
            cart_item_names.add(cn_lower)
            if any(w in cn_lower for w in ["chicken", "mutton", "fish", "beef", "meat", "wings", "nugget", "nuggets"]) or any(w in cn_lower.replace("(", " ").replace(")", " ").replace("-", " ").split() for w in ["egg", "eggs"]):
                has_cart_meat = True
            if any(w in cn_lower for w in ["paneer", "veggie", "crispy veg", "aloo", "potato"]):
                if any(w in c_cat for w in ["burger", "sandwich", "wrap", "main", "entree"]):
                    has_cart_veg_entree = True

        if "non" in c_type:
            has_cart_meat = True
        elif "veg" in c_type:
            if any(w in c_cat for w in ["burger", "sandwich", "wrap", "main", "entree"]):
                has_cart_veg_entree = True

    # Smart Cart Inference: ONLY lock if zero meat AND (committed veg main entree OR bulk >= 10 items)
    cart_committed_veg = (bool(parsed_cart) and not has_cart_meat and (has_cart_veg_entree or total_cart_qty >= 10))

    # Anchor commitment: only a vegetarian main entree locks dietary without explicit filter
    is_anchor_main = any(w in anchor_cat_raw for w in ["burger", "sandwich", "wrap", "entree", "main"])
    anchor_committed_veg = anchor_is_veg and is_anchor_main

    if explicit_veg_filter or anchor_committed_veg or cart_committed_veg:
        effective_dietary_lock = "veg"
    elif explicit_non_veg_filter:
        effective_dietary_lock = "non_veg"
    elif profile.is_explicit_override and profile.dietary_lock:
        effective_dietary_lock = profile.dietary_lock
    else:
        effective_dietary_lock = None

    session = await _resolve_session(session_id, food_preference=effective_dietary_lock)
    session.food_preference = effective_dietary_lock
    if effective_dietary_lock:
        profile.dietary_lock = effective_dietary_lock

    context = RecommendationContext(
        session_id=session_id,
        user_id=None,
        user_profile=None,
        cart_lines=parsed_cart,
        dismissed_item_ids=dismissed_ids,
        dietary_lock=effective_dietary_lock,
        intent_mode="meal_complete",
        branch_id=branch_id,
        circadian_phase=CircadianCravingAnalyzer.get_current_circadian_phase(),
        anchor_item=anchor,
        session_context=session_ctx_dict,
    )

    tray_winners: list[dict[str, Any]] = []
    # Seed chosen_ids with anchor and all cart items (Module 7: Universal Cart Exclusion)
    chosen_ids: set[int] = {anchor.id} | cart_item_ids
    chosen_drink_subroles: set[str] = set()
    assigned_base_ingredients: set[str] = set()
    assigned_dominant_flavors: set[str] = set()

    from app.intelligence.recommendation.data_quality_gate import CulinaryTagger
    anchor_base = AntiRedundancyConstraint.extract_base_ingredient(anchor)
    if anchor_base:
        assigned_base_ingredients.add(anchor_base)
    anchor_flavor = CulinaryTagger.get_dominant_flavor(anchor)
    if anchor_flavor:
        assigned_dominant_flavors.add(anchor_flavor)

    slot_badges = [
        ("⭐ Best Match", "Top recommended pairing to complete your meal"),
        ("🔥 Great Pairing", "Crisp, balanced flavor contrast to complement your order"),
        ("🍽️ Complete Your Meal", "Essential companion to complete your tray"),
    ]

    # Requirement 6: Strict 3-Pillar UI Formatting [Slot 1: Side, Slot 2: Drink, Slot 3: Dessert]
    for idx, target_role in enumerate(complementary_roles):
        candidates = await _catalog_repo.get_by_category(target_role, branch_id)
        if not candidates:
            continue

        # Effective max ratio: for premium anchors (>= 169) on drink/dessert, allow full elasticity
        eff_max_ratio = 2.0 if (float(anchor.price.amount) >= 169.0 and target_role in ("drink", "dessert")) else 1.5

        # 1. Strict Override Hierarchy Filter with Anti-Redundancy Constraint in MEAL_COMPLETION
        valid_candidates = _constraint_filter.filter_candidates(
            candidates=candidates,
            session=session,
            cart_item_ids=chosen_ids,
            rejected_item_ids=dismissed_ids,
            anchor_price=anchor.price.amount,
            max_price_ratio=eff_max_ratio,
            branch_id=branch_id,
            anchor_item=anchor,
            mode="MEAL_COMPLETION",
        )

        if not valid_candidates:
            # Fallback to general category items if all were filtered
            valid_candidates = [
                c for c in candidates 
                if c.id not in chosen_ids and c.is_available and float(c.price.amount) <= float(anchor.price.amount) * eff_max_ratio
            ]

        # 2. 7-Tier Precedence Scoring
        evaluated, _ = evaluate_7tier_pipeline(
            candidates=valid_candidates,
            context=context,
            anchor_price=float(anchor.price.amount),
        )

        # 3. Apply Cart Gap Beverage Diversity, Intra-Tray Diversity & Strict Categorical Pillar Matching
        selected_cand = None
        for entry in evaluated:
            cand_item: MenuItem = entry["item"]
            if cand_item.id in chosen_ids or _item_name(cand_item).strip().lower() in cart_item_names:
                continue

            if context.rejected_sub_roles and get_item_sub_role(cand_item) in context.rejected_sub_roles:
                continue

            cand_cat = str(cand_item.category.value if hasattr(cand_item.category, "value") else cand_item.category).lower()
            if context.rejected_categories and cand_cat in context.rejected_categories:
                continue

            # Strict pillar categorical enforcement: candidate MUST match target_role
            if target_role == "side" and not ("side" in cand_cat or "snack" in cand_cat):
                continue
            if target_role == "drink" and not ("drink" in cand_cat or "beverage" in cand_cat):
                continue
            if target_role == "dessert" and not ("dessert" in cand_cat or any(w in cand_item.name.lower() for w in ["sundae", "softie", "lava", "mousse", "shake"])):
                continue

            if "drink" in cand_cat:
                subrole = classify_beverage_subrole(cand_item)
                if subrole == "sweet_indulgence" and "sweet_indulgence" in chosen_drink_subroles:
                    continue

            # TASK 2: INTRA-TRAY DIVERSITY
            cand_base = AntiRedundancyConstraint.extract_base_ingredient(cand_item)
            if cand_base and cand_base in assigned_base_ingredients:
                continue
            cand_flavor = CulinaryTagger.get_dominant_flavor(cand_item)
            if cand_flavor and cand_flavor in assigned_dominant_flavors:
                continue

            selected_cand = cand_item
            break

        # Fallback if intra-tray diversity filtered all candidates in this role
        if not selected_cand:
            for entry in evaluated:
                cand_item = entry["item"]
                if cand_item.id in chosen_ids or _item_name(cand_item).strip().lower() in cart_item_names:
                    continue
                if context.rejected_sub_roles and get_item_sub_role(cand_item) in context.rejected_sub_roles:
                    continue
                c_cat = str(cand_item.category.value if hasattr(cand_item.category, "value") else cand_item.category).lower()
                if context.rejected_categories and c_cat in context.rejected_categories:
                    continue
                # Still respect strict category role
                if target_role == "side" and not ("side" in c_cat or "snack" in c_cat):
                    continue
                if target_role == "drink" and not ("drink" in c_cat or "beverage" in c_cat):
                    continue
                if target_role == "dessert" and not ("dessert" in c_cat):
                    continue
                selected_cand = cand_item
                break

        if selected_cand:
            badge_text, synergy_desc = slot_badges[min(idx, len(slot_badges) - 1)]
            tray_winners.append(
                serialize_recommendation_item(
                    selected_cand,
                    badge=badge_text,
                    synergy_reason=synergy_desc,
                )
            )
            chosen_ids.add(selected_cand.id)
            if "drink" in str(selected_cand.category).lower():
                chosen_drink_subroles.add(classify_beverage_subrole(selected_cand))
            sel_base = AntiRedundancyConstraint.extract_base_ingredient(selected_cand)
            if sel_base:
                assigned_base_ingredients.add(sel_base)
            sel_flavor = CulinaryTagger.get_dominant_flavor(selected_cand)
            if sel_flavor:
                assigned_dominant_flavors.add(sel_flavor)

    if effective_dietary_lock == "veg":
        tray_winners = [
            w for w in tray_winners
            if not (
                "non" in str(w.get("foodType") or w.get("food_type") or "").lower()
                or any(m in str(w.get("name", "")).lower() for m in ["chicken", "mutton", "fish", "beef", "meat", "wings", "nugget", "nuggets"])
                or any(m in str(w.get("name", "")).lower().replace("(", " ").replace(")", " ").replace("-", " ").split() for m in ["egg", "eggs"])
            )
        ]

    return {
        "success": True,
        "job_code": "MEAL_COMPLETION",
        "headline": f"✨ Pairs Best with {anchor.name}",
        "recommendations": tray_winners,
        "latency_ms": round((time.time() - t0) * 1000.0, 2),
    }


# ── 2. CATEGORY SPOTLIGHT ENDPOINT (SpotlightShelf.jsx) ───────────────────────

@router.get("/spotlight/{category}")
async def get_category_spotlight(
    category: str,
    session_id: str = Query("default-kiosk-session"),
    dietary_preference: Optional[str] = Query(None, alias="preference"),
    time_of_day: Optional[str] = Query(None),
    circadian_hour: Optional[int] = Query(None),
    branch_id: int = Query(1),
):
    """
    Category Spotlight Endpoint (For SpotlightShelf.jsx).
    Job: DISCOVERY.
    Applies Circadian Contexting logic to return time-appropriate items:
    - Morning (7-11): Caffeine & breakfast focus (Coffee, Hashbrowns)
    - Afternoon (12-16): Lunch energy & effervescent fizz (Whoppers, Soda)
    - Evening (17-21): Dinner & savory sharing bites (Loaded burgers, Hot Fries)
    - Night (22-5): High-sugar, indulgent comfort (Shakes, Lava Cake, Sundaes)
    """
    t0 = time.time()

    # 1. Resolve Circadian Hour
    hour = datetime.now().hour
    if time_of_day:
        tod_lower = time_of_day.lower()
        if any(w in tod_lower for w in ["morning", "breakfast"]):
            hour = 9
        elif any(w in tod_lower for w in ["afternoon", "lunch"]):
            hour = 14
        elif any(w in tod_lower for w in ["evening", "dinner"]):
            hour = 19
        elif any(w in tod_lower for w in ["night", "late"]):
            hour = 23
    elif circadian_hour is not None:
        hour = circadian_hour

    # 2. Determine Circadian Phase Metadata
    if 6 <= hour <= 10:
        circadian_phase = "morning"
        circadian_badge = "🌅 Morning Kick"
        headline = "Fresh Morning Starters"
        subline = "Kickstart your day with warm breakfast favorites & energizing brews."
    elif 11 <= hour <= 15:
        circadian_phase = "afternoon"
        circadian_badge = "☀️ Lunchtime Fuel"
        headline = "Lunchtime Favorites"
        subline = "Hearty flame-grilled classics and refreshing coolers to power your afternoon."
    elif 16 <= hour <= 21:
        circadian_phase = "evening"
        circadian_badge = "🔥 Evening Feast"
        headline = "Evening Crowd Favorites"
        subline = "Crisp savory sides, loaded whoppers, and perfect sharing bites."
    else:
        circadian_phase = "night"
        circadian_badge = "🌙 Late Night Comfort"
        headline = "Midnight Cravings"
        subline = "Sweet decadent treats and creamy shakes to satisfy late night sweet teeth."

    # 3. Retrieve Candidates
    cat_norm = category.lower().rstrip("s")
    if cat_norm in ("all", "spotlight"):
        candidates = []
        for c in ["burger", "drink", "side", "dessert"]:
            candidates.extend(await _catalog_repo.get_by_category(c, branch_id))
    else:
        candidates = await _catalog_repo.get_by_category(cat_norm, branch_id)

    session = await _resolve_session(session_id, food_preference=dietary_preference)
    profile = SessionLearner.get_or_create_profile(session_id)
    dismissed_ids = set(profile.dismissed_item_ids)

    # 4. Filter and Score Candidates
    valid_candidates = _constraint_filter.filter_candidates(
        candidates=candidates,
        session=session,
        cart_item_ids=set(),
        rejected_item_ids=dismissed_ids,
        branch_id=branch_id,
        mode="DISCOVERY",
    )

    scored_items: list[tuple[float, MenuItem, str]] = []
    for it in valid_candidates:
        mult, reason = CircadianCravingAnalyzer.evaluate_circadian_multiplier(it, hour=hour)
        price_val = float(it.price.amount)
        base_score = 1.0

        # Preference matching
        if session.food_preference:
            pref = session.food_preference.lower()
            it_type = str(it.food_type).lower() if it.food_type else ""
            if pref == "veg" and "veg" in it_type and "non" not in it_type:
                base_score += 0.35
            elif "non" in pref and "non" in it_type:
                base_score += 0.35

        velocity_mult = calculate_velocity_multiplier(it)
        yield_mult = calculate_yield_boost(it)
        score = base_score * mult * velocity_mult * yield_mult
        scored_items.append((score, it, reason))

    scored_items.sort(key=lambda x: x[0], reverse=True)
    top_items = scored_items[:4]

    spotlight_serialized = [
        serialize_recommendation_item(
            it,
            badge=circadian_badge if mult_reason != "Neutral circadian baseline" else "⭐ Curated Pick",
            synergy_reason=mult_reason,
        )
        for _, it, mult_reason in top_items
    ]

    return {
        "success": True,
        "job_code": "DISCOVERY",
        "category": category,
        "circadian_phase": circadian_phase,
        "circadian_badge": circadian_badge,
        "headline": headline,
        "subline": subline,
        "manifestation_nudge": f"Hand-picked for your {circadian_phase} appetite",
        "spotlight": spotlight_serialized,
        "latency_ms": round((time.time() - t0) * 1000.0, 2),
    }


# ── 3. PRE-CHECKOUT / CART DRAWER ENDPOINT (CartPage.jsx & CartContainer.jsx) ─

@router.get("/checkout")
async def get_checkout_recommendations(
    session_id: str = Query("default-kiosk-session"),
    branch_id: int = Query(1),
    circadian_hour: Optional[int] = Query(None),
):
    """
    GET overload for Pre-Checkout / Cart Drawer Endpoint (Used by CartPage.jsx & fetch clients).
    """
    req = CheckoutRecommendationRequest(
        session_id=session_id,
        cart_lines=[],
        branch_id=branch_id,
        circadian_hour=circadian_hour,
    )
    return await post_checkout_recommendations(req)


@router.post("")
@router.post("/")
@router.post("/checkout")
async def post_checkout_recommendations(req: CheckoutRecommendationRequest):
    """
    Pre-Checkout / Cart Drawer Endpoint (For CartPage.jsx & CartContainer.jsx).
    Job: MEAL_COMPLETION & UPGRADE.
    Evaluates missing pillars (burger, side, drink, dessert), enforces Cart Gap Diversity
    (never shows two heavy milk/ice-cream drinks together), and prioritizes accessible impulse items under ₹60.
    """
    t0 = time.time()
    session = await _resolve_session(req.session_id)
    profile = SessionLearner.get_or_create_profile(req.session_id)

    # 0. Cart Recovery if cart_lines is empty (e.g. GET request or unloaded frontend state)
    if not req.cart_lines:
        try:
            saved_cart = await _cart_service.get_cart(req.session_id)
            if saved_cart and saved_cart.lines:
                req.cart_lines = [
                    {
                        "item_id": l.item_id,
                        "item_name": l.item_name,
                        "name": l.item_name,
                        "category": str(l.category.value if hasattr(l.category, "value") else l.category) if hasattr(l, "category") else "",
                        "unit_price": float(l.unit_price.amount) if hasattr(l.unit_price, "amount") else float(l.unit_price),
                        "price": float(l.unit_price.amount) if hasattr(l.unit_price, "amount") else float(l.unit_price),
                        "quantity": l.quantity,
                        "food_type": getattr(l, "food_type", None) or (l.metadata.get("food_type") if getattr(l, "metadata", None) else None),
                        "is_veg": getattr(l, "is_veg", None) or (l.metadata.get("is_veg") if getattr(l, "metadata", None) else None),
                        "type": l.line_type,
                    }
                    for l in saved_cart.lines
                ]
        except Exception as e:
            logger.warning("failed_to_pull_saved_cart", error=str(e))

    # 1. Normalize Cart Lines and extract item_ids & item_names for Absolute Cart Exclusion
    normalized_lines = []
    cart_item_ids: set[int] = set()
    cart_item_names: set[str] = set()
    cart_total = Decimal("0.00")

    for line in req.cart_lines:
        if isinstance(line, int):
            item = await _catalog_repo.get_by_id(line, req.branch_id)
            if item:
                cart_item_ids.add(item.id)
                cart_item_names.add(item.name.strip().lower())
                p_amt = item.price.amount
                cart_total += p_amt
                is_v = bool(item.food_type and "veg" in str(item.food_type).lower() and "non" not in str(item.food_type).lower())
                normalized_lines.append({
                    "item_id": item.id,
                    "item_name": item.name,
                    "name": item.name,
                    "category": str(item.category.value if hasattr(item.category, "value") else item.category),
                    "unit_price": float(item.price.amount) if hasattr(item.price, "amount") else float(item.price),
                    "price": float(item.price.amount) if hasattr(item.price, "amount") else float(item.price),
                    "quantity": 1,
                    "food_type": "veg" if is_v else "non_veg",
                    "is_veg": is_v,
                    "type": "Veg" if is_v else "Non Veg",
                })
        elif isinstance(line, dict):
            item_id = line.get("item_id") or line.get("id")
            if item_id is not None:
                try:
                    cart_item_ids.add(int(item_id))
                except (ValueError, TypeError):
                    pass
            item_name = line.get("item_name") or line.get("name")
            if item_name:
                cart_item_names.add(str(item_name).strip().lower())
            price_val = line.get("price") or line.get("unit_price") or 0.0
            qty = line.get("quantity", 1)
            cart_total += Decimal(str(price_val)) * Decimal(str(qty))
            normalized_lines.append(line)

    # 1.5. Dietary Lock Resolution (Explicit Filter vs Smart Cart Threshold)
    session_ctx = req.session_context or {}
    if hasattr(session_ctx, "model_dump"):
        session_ctx = session_ctx.model_dump()

    ctx_pref = str(session_ctx.get("preference") or session_ctx.get("food_preference") or "").strip().lower() if isinstance(session_ctx, dict) else ""
    req_pref = (req.preference or "").strip().lower() if hasattr(req, "preference") and req.preference else ""

    if req_pref in ("veg", "non_veg", "non veg", "both"):
        SessionLearner.set_explicit_dietary_override(session_id, req_pref)
    elif ctx_pref in ("veg", "non_veg", "non veg", "both"):
        SessionLearner.set_explicit_dietary_override(session_id, ctx_pref)

    explicit_veg_filter = (
        req_pref == "veg"
        or ctx_pref == "veg"
        or (profile.dietary_lock == "veg")
        or (session.food_preference == "veg")
    )
    explicit_non_veg_filter = (
        req_pref in ("non_veg", "non veg")
        or ctx_pref in ("non_veg", "non veg")
        or (profile.dietary_lock in ("non_veg", "non veg"))
        or (session.food_preference in ("non_veg", "non veg"))
    )

    def _is_cart_line_veg(l: dict) -> bool:
        if l.get("is_veg") is not None:
            return bool(l.get("is_veg"))
        t = str(l.get("type") or l.get("food_type") or "").strip().lower()
        if t in ("veg", "vegetarian"):
            return True
        if "non" in t:
            return False
        nm = str(l.get("item_name") or l.get("name") or "").lower()
        if any(w in nm for w in ["paneer", "veg", "veggie", "aloo", "cheese", "potato", "crispy veg", "makhani"]):
            return True
        if any(w in nm for w in ["chicken", "mutton", "fish", "beef", "meat", "wings", "nugget", "nuggets"]) or any(w in nm.replace("(", " ").replace(")", " ").replace("-", " ").split() for w in ["egg", "eggs"]):
            return False
        return True

    has_cart_meat = any(not _is_cart_line_veg(l) for l in normalized_lines)
    has_veg_entree = any(
        _is_cart_line_veg(l) and any(w in str(l.get("category", "")).lower() for w in ["burger", "sandwich", "wrap", "main", "entree"])
        for l in normalized_lines
    )
    total_cart_qty = sum(l.get("quantity", 1) for l in normalized_lines)

    # Smart Cart Inference: ONLY lock if zero meat AND (veg main entree OR bulk >= 10 items)
    cart_committed_veg = (bool(normalized_lines) and not has_cart_meat and (has_veg_entree or total_cart_qty >= 10))

    if explicit_veg_filter or cart_committed_veg:
        effective_dietary_lock = "veg"
        session.food_preference = "veg"
        profile.dietary_lock = "veg"
    elif explicit_non_veg_filter:
        effective_dietary_lock = "non_veg"
        session.food_preference = "non_veg"
        profile.dietary_lock = "non_veg"
    elif profile.is_explicit_override and profile.dietary_lock:
        effective_dietary_lock = profile.dietary_lock
        session.food_preference = profile.dietary_lock
    else:
        effective_dietary_lock = None
        session.food_preference = None
        profile.dietary_lock = None

    # 2. Dining Pillar Gap Analysis + Dual-Role Saturation
    categories_present = set()
    has_heavy_dairy = False
    has_shake = False
    has_fries_or_nuggets = False

    for l in normalized_lines:
        cat_str = str(l.get("category", "")).lower()
        nm = str(l.get("item_name") or l.get("name") or "").lower()
        if "shake" in nm:
            has_shake = True
        if any(w in nm for w in ["fries", "french fries", "nugget", "nuggets"]):
            has_fries_or_nuggets = True
        if "burger" in cat_str:
            categories_present.add("burger")
        if "drink" in cat_str or "beverage" in cat_str:
            categories_present.add("drink")
            if is_heavy_dairy_beverage(l):
                has_heavy_dairy = True
        if "side" in cat_str:
            categories_present.add("side")
        if "dessert" in cat_str:
            categories_present.add("dessert")

    # Dual-Role Saturation (Code Red):
    # If cart contains 'Shake' or a heavy, high-dairy beverage, forcefully set Dessert = FULFILLED,
    # forcing shelf to pivot to savory sides/dips.
    if has_heavy_dairy or has_shake:
        categories_present.add("drink")
        categories_present.add("dessert")

    all_pillars = ["side", "drink", "dessert", "burger"]
    missing_pillars = [p for p in all_pillars if p not in categories_present]

    # TASK 4: THE GATEKEEPER KILL-SWITCH
    # If Main, Side, Drink, and Dessert are ALL evaluated as FULFILLED, trigger the Saturation Kill-Switch
    # and instantly return {"recommendations": []}.
    if not missing_pillars:
        return {
            "success": True,
            "job_code": "CLOSURE",
            "headline": "🍽️ Meal Complete",
            "missing_pillars": [],
            "recommendations": [],
            "cart_total": float(cart_total),
            "kill_switch_triggered": True,
            "latency_ms": round((time.time() - t0) * 1000.0, 2),
        }

    target_categories = list(missing_pillars) if missing_pillars else (["side"] if (has_heavy_dairy or has_shake) else ["dessert", "side"])

    # Real-Time Session Heuristics (Zero-Training):
    # Exclude explicitly rejected categories from the target category drawer
    session_ctx = req.session_context or {}
    if hasattr(session_ctx, "model_dump"):
        session_ctx = session_ctx.model_dump()
    raw_rej = session_ctx.get("rejected_categories", []) if isinstance(session_ctx, dict) else []
    rejected_cats = {str(r).strip().lower().rstrip("s") for r in raw_rej if r}

    raw_rsr = session_ctx.get("rejected_sub_roles", []) if isinstance(session_ctx, dict) else []
    rejected_sub_roles = {str(r).strip().lower() for r in raw_rsr if r}

    velocity_state = str(session_ctx.get("velocity_state") or "").strip().lower() if isinstance(session_ctx, dict) else ""

    if rejected_cats:
        unrejected = [p for p in target_categories if p.lower().rstrip("s") not in rejected_cats and not any(r in p.lower() for r in rejected_cats)]
        if unrejected:
            target_categories = unrejected

    # Bulk Rush Mode: ensure sides are evaluated so sharing buckets can surface
    if velocity_state == "rushed" and "side" not in target_categories and "side" not in rejected_cats:
        target_categories.append("side")

    # Condiment Host Boost: If Fries or Nuggets are in cart payload, also evaluate sides (dips, sauces)
    # so they can receive the 1.5x boost and surface above standard desserts
    if has_fries_or_nuggets and "side" not in target_categories and "side" not in rejected_cats:
        target_categories.append("side")

    # 3. Retrieve Contextual Candidates for target missing categories
    raw_candidates = []
    for cat in target_categories:
        cat_items = await _catalog_repo.get_by_category(cat, req.branch_id)
        raw_candidates.extend(cat_items)

    if not raw_candidates:
        fallback_cats = ["side"] if (has_heavy_dairy or has_shake) else ["side", "drink", "dessert"]
        for cat in fallback_cats:
            raw_candidates.extend(await _catalog_repo.get_by_category(cat, req.branch_id))

    anchor_item_candidate = None
    if normalized_lines:
        def _line_price(line_dict: dict) -> float:
            p = line_dict.get("unit_price") or line_dict.get("price") or 0.0
            if hasattr(p, "amount"):
                return float(p.amount)
            try:
                return float(p)
            except (ValueError, TypeError):
                return 0.0

        # Prioritize the dominant/highest-priced entree (e.g. Premium Whopper over a budget burger)
        entrees = [
            l for l in normalized_lines
            if any(w in str(l.get("category", "")).lower() for w in ["burger", "sandwich", "wrap", "taco", "main", "entree"])
        ]
        if entrees:
            dominant_line = max(entrees, key=_line_price)
        else:
            dominant_line = max(normalized_lines, key=_line_price)
        anchor_id = dominant_line.get("item_id")
        if anchor_id:
            anchor_item_candidate = await _catalog_repo.get_by_id(anchor_id, req.branch_id)

    eff_anchor = calculate_effective_anchor(normalized_lines, default_anchor=float(cart_total) if cart_total > Decimal("0") else 100.0)

    # 4. Strict Override Hierarchy Filter with Absolute Cart Exclusion (ID & Name)
    valid_candidates = _constraint_filter.filter_candidates(
        candidates=raw_candidates,
        session=session,
        cart_item_ids=cart_item_ids,
        cart_item_names=cart_item_names,
        rejected_item_ids=set(profile.dismissed_item_ids),
        anchor_price=Decimal(str(round(eff_anchor, 2))),
        max_price_ratio=2.5,
        branch_id=req.branch_id,
        anchor_item=anchor_item_candidate,
        mode="CLOSURE",
    )

    session_ctx = req.session_context or {}
    if hasattr(session_ctx, "model_dump"):
        session_ctx = session_ctx.model_dump()

    context = RecommendationContext(
        session_id=req.session_id,
        user_id=None,
        user_profile=None,
        cart_lines=normalized_lines,
        dismissed_item_ids=set(profile.dismissed_item_ids),
        dietary_lock=effective_dietary_lock,
        intent_mode="closure",
        branch_id=req.branch_id,
        circadian_phase=CircadianCravingAnalyzer.get_current_circadian_phase(),
        anchor_item=anchor_item_candidate,
        session_context=session_ctx,
    )

    evaluated, _ = evaluate_7tier_pipeline(
        candidates=valid_candidates,
        context=context,
        anchor_price=eff_anchor,
    )
    candidates = [e["item"] for e in evaluated]

    # 5. Enforce Cart Gap Diversity across target categories (preserving 7-tier score)
    # Group candidates by category preserving their pipeline order
    cat_buckets: dict[str, list[MenuItem]] = {}
    for e in evaluated:
        it = e["item"]
        c_raw = str(it.category.value if hasattr(it.category, "value") else it.category).lower()
        c_norm = "burger" if "burger" in c_raw else ("drink" if "drink" in c_raw or "beverage" in c_raw else ("side" if "side" in c_raw else ("dessert" if "dessert" in c_raw else "side")))
        cat_buckets.setdefault(c_norm, []).append(it)

    score_map = {e["item_id"]: e["composite_score"] for e in evaluated}
    # For budget carts (eff_anchor <= 80), sort within each bucket to prioritize impulse items (<= 60), while preserving composite score ranking
    if eff_anchor <= 80.0 and velocity_state != "rushed":
        for c in cat_buckets:
            cat_buckets[c].sort(key=lambda it: (0 if float(it.price.amount) <= 60.0 else 1, -score_map.get(it.id, 0.0)))

    # Condiment Host Boost: if fries or nuggets are in cart, ensure condiment items top the side bucket
    if has_fries_or_nuggets and "side" in cat_buckets:
        def _condiment_sort_key(it: MenuItem):
            nm = (it.name or "").lower()
            sub_role = getattr(it, "sub_role", None) or getattr(it, "sub_category", None) or ""
            is_cond = str(sub_role).lower() == "condiment" or any(w in nm for w in ["dip", "sauce", "mayo"])
            return (0 if is_cond else 1, -score_map.get(it.id, 0.0))
        cat_buckets["side"].sort(key=_condiment_sort_key)

    chosen_drink_subroles: set[str] = set()
    chosen_dessert_subroles: list[str] = []
    assigned_base_ingredients: set[str] = set()
    assigned_dominant_flavors: set[str] = set()
    final_recs = []
    chosen_ids = set(cart_item_ids)

    def _is_cand_eligible(it: MenuItem) -> bool:
        # Code Red: Absolute Cart Exclusion by ID and Name
        if it.id in chosen_ids or CartExclusionConstraint.is_in_cart(it, cart_item_ids=chosen_ids, cart_item_names=cart_item_names):
            return False

        # Real-time Session Heuristics (Zero-Training): Category rejection check
        cand_cat = str(it.category.value if hasattr(it.category, "value") else it.category).lower()
        if rejected_cats and (cand_cat.rstrip("s") in rejected_cats or any(r in cand_cat for r in rejected_cats)):
            return False

        # Real-time Session Heuristics: Sub-Role Rejection (The "Back Button" Signal)
        if rejected_sub_roles:
            cand_sub = get_item_sub_role(it)
            if cand_sub in rejected_sub_roles:
                return False

        # Code Red: Strict Dietary Veg Lock Enforcement
        if effective_dietary_lock == "veg":
            ft = str(it.food_type.value if hasattr(it.food_type, "value") else it.food_type).lower() if it.food_type else ""
            cand_n = (it.name or "").lower()
            has_meat = any(w in cand_n for w in ["chicken", "mutton", "fish", "beef", "meat", "wings", "nugget", "nuggets"]) or any(w in cand_n.replace("(", " ").replace(")", " ").replace("-", " ").split() for w in ["egg", "eggs"])
            if "non" in ft or has_meat:
                return False

        # TASK 2: INTRA-TRAY DIVERSITY - FIXING "VANILLA + VANILLA"
        cand_base = AntiRedundancyConstraint.extract_base_ingredient(it)
        if cand_base and cand_base in assigned_base_ingredients:
            return False
        cand_flavor = CulinaryTagger.get_dominant_flavor(it)
        if cand_flavor and cand_flavor in assigned_dominant_flavors:
            return False

        cat_str = str(it.category.value if hasattr(it.category, "value") else it.category).lower()
        # Enforce beverage balance: never show two sweet indulgence drinks together
        if "drink" in cat_str or "beverage" in cat_str:
            subrole = classify_beverage_subrole(it)
            if subrole == "sweet_indulgence" and "sweet_indulgence" in chosen_drink_subroles:
                return False

        # Enforce dessert diversity: never show all cold_dairy desserts if hot_baked available
        if "dessert" in cat_str:
            dessert_subrole = classify_dessert_subrole(it)
            if dessert_subrole == "cold_dairy":
                cold_count = sum(1 for r in chosen_dessert_subroles if r == "cold_dairy")
                if cold_count >= 2:
                    has_hot = any(
                        c.id not in chosen_ids
                        and "dessert" in str(c.category.value if hasattr(c.category, "value") else c.category).lower()
                        and classify_dessert_subrole(c) == "hot_baked"
                        for c in candidates
                    )
                    if has_hot:
                        return False
        return True

    def _add_rec(it: MenuItem):
        chosen_ids.add(it.id)
        cand_base = AntiRedundancyConstraint.extract_base_ingredient(it)
        if cand_base:
            assigned_base_ingredients.add(cand_base)
        cand_flavor = CulinaryTagger.get_dominant_flavor(it)
        if cand_flavor:
            assigned_dominant_flavors.add(cand_flavor)

        cat_str = str(it.category.value if hasattr(it.category, "value") else it.category).lower()
        if "drink" in cat_str or "beverage" in cat_str:
            chosen_drink_subroles.add(classify_beverage_subrole(it))
        if "dessert" in cat_str:
            chosen_dessert_subroles.append(classify_dessert_subrole(it))

        cand_name_l = (it.name or "").lower()
        sub_role = getattr(it, "sub_role", None) or getattr(it, "sub_category", None) or ""
        is_cond = str(sub_role).lower() == "condiment" or any(w in cand_name_l for w in ["dip", "sauce", "mayo"])
        cand_sub = get_item_sub_role(it)
        price_amt = float(it.price.amount)

        if cand_sub == "sharing_bucket":
            badge = "🔥 Crowd Pleaser (Bulk Sharing)"
            synergy = "Perfect sharing add-on for your group order"
        elif has_fries_or_nuggets and is_cond:
            badge = "🔥 Best Dipping Pair"
            synergy = "Perfect companion dip for your savory sides"
        elif price_amt <= 60.0:
            badge = "💚 Impulse Treat (Under ₹60)"
            synergy = "Pocket-friendly treat to complete your tray"
        else:
            badge = "🍽️ Complete Your Tray"
            synergy = "Recommended companion for your order"
        final_recs.append(serialize_recommendation_item(it, badge=badge, synergy_reason=synergy))

    if velocity_state == "rushed":
        # Bulk Rush mode: prioritize sharing_bucket items and highest composite scores directly
        for it in candidates:
            if len(final_recs) >= 3:
                break
            if _is_cand_eligible(it):
                _add_rec(it)
    else:
        # PASS 1: Select top candidate from each target missing category
        for cat in target_categories:
            if len(final_recs) >= 3:
                break
            for it in cat_buckets.get(cat, []):
                if _is_cand_eligible(it):
                    _add_rec(it)
                    break

        # PASS 2: If still under 3, select secondary choices from target categories
        if len(final_recs) < 3:
            for cat in target_categories:
                if len(final_recs) >= 3:
                    break
                for it in cat_buckets.get(cat, []):
                    if _is_cand_eligible(it):
                        _add_rec(it)
                        break

        # PASS 3: Fallback from remaining evaluated candidates
        if len(final_recs) < 3:
            for it in candidates:
                if len(final_recs) >= 3:
                    break
                if _is_cand_eligible(it):
                    _add_rec(it)

    # FINAL HARDFILTER 1 (Code Red): Forcefully eradicate all Non-Veg SKUs if dietary lock is veg
    if effective_dietary_lock == "veg":
        final_recs = [
            r for r in final_recs
            if not (
                "non" in str(r.get("food_type", "")).lower()
                or any(w in str(r.get("name", "")).lower() for w in ["chicken", "mutton", "fish", "beef", "meat", "wings", "nugget", "nuggets"])
                or any(w in str(r.get("name", "")).lower().replace("(", " ").replace(")", " ").replace("-", " ").split() for w in ["egg", "eggs"])
            )
        ]

    # FINAL HARDFILTER 2 (Code Red): Absolute Cart Exclusion by ID and Name
    final_recs = [
        r for r in final_recs
        if not CartExclusionConstraint.is_in_cart(r, cart_item_ids=cart_item_ids, cart_item_names=cart_item_names)
    ]

    return {
        "success": True,
        "job_code": "CLOSURE",
        "headline": "🍽️ Complete Your Tray Before Checkout",
        "missing_pillars": missing_pillars,
        "recommendations": final_recs,
        "cart_total": float(cart_total),
        "latency_ms": round((time.time() - t0) * 1000.0, 2),
    }


# ── 4. "MAKE IT A MEAL" UPGRADE ENDPOINT (ProductPage.jsx / Drawer) ───────────

@router.get("/meal-upgrade/{anchor_item_id}")
async def get_meal_upgrade_options(
    anchor_item_id: int,
    session_id: str = Query("default-kiosk-session"),
    branch_id: int = Query(1),
):
    """
    "Make it a Meal" Bundle-Pricing Upgrade Endpoint (For ProductPage.jsx / Drawer).
    Job: UPGRADE_BUNDLE.

    Logic:
    1. Verify if the anchor_item_id is eligible for a meal upgrade (must exist and have is_meal_available=True).
    2. Retrieve eligible sides and drinks strictly governed by the meal_upgrade_rules database table.
    3. CRITICAL PRICING OVERRIDE: Do not return standard standalone prices (e.g. ₹130).
       Calculate and return upgrade_delta_price (e.g. +₹50, +₹40, +₹70) based on bundle math in meal_upgrade_rules.
    4. Group response payload into standard_sides, premium_sides, drinks, premium_drinks, standard_add_ons, and premium_add_ons.
    """
    t0 = time.time()
    anchor = await _catalog_repo.get_by_id(anchor_item_id, branch_id)
    if not anchor:
        raise HTTPException(status_code=404, detail="Anchor product not found")

    anchor_price_val = float(anchor.price.amount if hasattr(anchor.price, "amount") else anchor.price)

    if not anchor.is_meal_available:
        return {
            "status": "ineligible",
            "anchor_item_id": anchor_item_id,
            "anchor_name": anchor.name,
            "job": "UPGRADE_BUNDLE",
            "message": "Item is not eligible for meal upgrade",
            "upgrade_options": {
                "standard_sides": [],
                "premium_sides": [],
                "drinks": [],
                "premium_drinks": [],
                "standard_add_ons": [],
                "premium_add_ons": [],
            },
            "latency_ms": round((time.time() - t0) * 1000.0, 2),
        }

    # Retrieve bundle rules from meal_upgrade_rules joined with menu_items
    session_maker = get_async_session_maker()
    async with session_maker() as session:
        stmt = (
            select(MealUpgradeRule, MenuItemORM)
            .join(MenuItemORM, MealUpgradeRule.upgrade_item_id == MenuItemORM.id)
            .where(MealUpgradeRule.base_item_id == anchor_item_id)
        )
        res = await session.execute(stmt)
        rules = res.all()

    standard_sides = []
    premium_sides = []
    drinks = []
    premium_drinks = []
    standard_add_ons = []
    premium_add_ons = []

    for rule, item_orm in rules:
        if not item_orm.is_available:
            continue

        cat = (item_orm.category or "").lower()
        name_lower = item_orm.name.lower()
        standalone_price = float(item_orm.price)
        upgrade_price = float(rule.upgrade_price_delta)
        delta_int = int(round(upgrade_price))
        display_text = f"+ ₹{delta_int}"

        img = item_orm.image or get_category_default_image(cat, item_orm.name)
        if img and not img.startswith("http") and not img.startswith("/"):
            img = "/" + img

        # Differentiate standard vs premium
        # Premium sides: "peri peri", "king", "nugget", or upgrade delta >= 65
        # Premium drinks: "shake", "frappe", "coffee", or upgrade delta >= 70
        is_side = "side" in cat or "snack" in cat
        is_drink = "drink" in cat or "beverage" in cat

        is_premium = False
        if is_side:
            if "peri peri" in name_lower or "king" in name_lower or "nugget" in name_lower or upgrade_price >= 65.0:
                is_premium = True
        elif is_drink:
            if "shake" in name_lower or "frappe" in name_lower or "coffee" in name_lower or upgrade_price >= 70.0:
                is_premium = True

        addon_payload = {
            "id": item_orm.id,
            "name": item_orm.name,
            "category": cat,
            "standalone_price": standalone_price,
            "upgrade_price": upgrade_price,
            "display_text": display_text,
            "savings": round(max(0.0, standalone_price - upgrade_price), 2),
            "image": img,
            "is_premium": is_premium,
        }

        if is_side:
            if is_premium:
                premium_sides.append(addon_payload)
                premium_add_ons.append(addon_payload)
            else:
                standard_sides.append(addon_payload)
                standard_add_ons.append(addon_payload)
        elif is_drink:
            if is_premium:
                premium_drinks.append(addon_payload)
                premium_add_ons.append(addon_payload)
            else:
                drinks.append(addon_payload)
                standard_add_ons.append(addon_payload)

    # Sort trays by upgrade_price ascending
    standard_sides.sort(key=lambda x: x["upgrade_price"])
    premium_sides.sort(key=lambda x: x["upgrade_price"])
    drinks.sort(key=lambda x: x["upgrade_price"])
    premium_drinks.sort(key=lambda x: x["upgrade_price"])
    standard_add_ons.sort(key=lambda x: x["upgrade_price"])
    premium_add_ons.sort(key=lambda x: x["upgrade_price"])

    return {
        "status": "success",
        "anchor_item_id": anchor_item_id,
        "anchor_name": anchor.name,
        "anchor_price": anchor_price_val,
        "job": "UPGRADE_BUNDLE",
        "upgrade_options": {
            "standard_sides": standard_sides,
            "premium_sides": premium_sides,
            "drinks": drinks,
            "premium_drinks": premium_drinks,
            "standard_add_ons": standard_add_ons,
            "premium_add_ons": premium_add_ons,
        },
        "latency_ms": round((time.time() - t0) * 1000.0, 2),
    }


@router.post("/preference")
async def set_dietary_preference_endpoint(payload: dict):
    """
    Deterministic Tool Entry Point for LLM / Voice Agent / UI filter toggles.
    Directly updates SessionLearner with explicit override.
    Accepts: { session_id: str, preference: 'veg' | 'non_veg' | 'both' }
    """
    session_id = payload.get("session_id", "default-kiosk-session")
    preference = payload.get("preference", "both")
    SessionLearner.set_explicit_dietary_override(session_id, preference)
    profile = SessionLearner.get_or_create_profile(session_id)
    return {
        "success": True,
        "session_id": session_id,
        "preference": preference,
        "dietary_lock": profile.dietary_lock,
        "is_explicit_override": profile.is_explicit_override,
    }

