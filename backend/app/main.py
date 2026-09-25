"""
app/main.py
Application Entry Point and FastAPI Factory for TheAtom Commercial Intelligence Engine.
"""
from __future__ import annotations
import io
from contextlib import asynccontextmanager
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import Response, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from app.api.middleware.error_handler import register_exception_handlers
from app.api.middleware.request_id import RequestContextMiddleware
from app.api.v1.router import api_v1_router
from app.config.settings import get_settings
from app.infrastructure.cache.redis_client import close_redis_client, get_redis_client
from app.infrastructure.db.connection import close_db_engine
from app.observability.logging import configure_logging, get_logger


logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(level=settings.log_level, json_format=settings.effective_log_json)
    logger.info("theatom_starting_up", version=settings.app_version, env=settings.environment)

    # Initialize warm connections
    await get_redis_client()

    # Prewarm catalog cache in RAM to eliminate WAN database latency
    try:
        from app.infrastructure.repositories.catalog_repository import SQLAlchemyCatalogRepository
        repo = SQLAlchemyCatalogRepository()
        for cat in ["burger", "drink", "side", "dessert"]:
            await repo.get_by_category(cat, branch_id=1)
        logger.info("catalog_cache_prewarmed_successfully")
    except Exception as e:
        logger.warning("catalog_warmup_failed", error=str(e))

    yield

    logger.info("theatom_shutting_down")
    await close_redis_client()
    await close_db_engine()


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="TheAtom — Universal Commercial Intelligence & Decision Engine",
        lifespan=lifespan,
    )

    # 1. Error handlers
    register_exception_handlers(app)

    # 2. Middlewares (outermost executed first)
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:[0-9]+)?$",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 3. Mount versioned API routes
    app.include_router(api_v1_router, prefix=settings.api_prefix)
    from app.api.v1.recommendations import router as recommendations_router
    app.include_router(recommendations_router)

    # 4. Backward-compatible / legacy endpoints for kiosk frontend compatibility
    # Kiosk frontend hits /menu/burgers, /cart, etc. directly
    from app.infrastructure.repositories.catalog_repository import SQLAlchemyCatalogRepository
    from app.infrastructure.repositories.order_repository import SQLAlchemyOrderRepository
    from app.application.cart_service import CartService

    _cat = SQLAlchemyCatalogRepository()
    _ord = SQLAlchemyOrderRepository()
    _cs = CartService(_cat)
    from app.infrastructure.repositories.session_repository import RedisSessionRepository
    from app.application.session_service import SessionService
    from app.intelligence.recommendation.engine import HybridRecommendationEngine

    _session_repo = RedisSessionRepository()
    _session_svc = SessionService(_session_repo)
    _rec_engine = HybridRecommendationEngine(_cat)

    from app.infrastructure.repositories.memory_repository import PostgresMemoryStore
    from app.intelligence.memory.memory_service import MemoryService
    from app.intelligence.proactive.engine import ProactiveIntelligenceEngine

    _mem_store = PostgresMemoryStore()
    _mem_svc = MemoryService(_mem_store)
    _proactive_engine = ProactiveIntelligenceEngine(_cat, _mem_svc)
    from app.intelligence.recommendation.session_learner import SessionLearner
    from app.intelligence.recommendation.heuristics.circadian_clock import CircadianCravingAnalyzer
    from app.intelligence.recommendation.llm_merchandising_engine import LLMMerchandisingEngine

    _merchandising_engine = LLMMerchandisingEngine()

    def _filter_sections_by_pref(sections: list[dict], preference: str | None = None) -> list[dict]:
        if not preference or preference.strip().lower() == "both":
            return sections
        pref = preference.strip().lower()
        filtered = []
        for sec in sections:
            prods = sec.get("products", [])
            if pref == "veg":
                matched = [
                    p for p in prods
                    if p.get("type") == "veg"
                    or p.get("foodType") == "veg"
                    or ("veg" in str(p.get("food_type", "")).lower() and "non" not in str(p.get("food_type", "")).lower())
                ]
            elif pref in ("non veg", "non_veg"):
                matched = [
                    p for p in prods
                    if "non" in str(p.get("type", "")).lower()
                    or "non" in str(p.get("foodType", "")).lower()
                    or "non" in str(p.get("food_type", "")).lower()
                ]
            else:
                matched = prods
            if matched:
                sec_copy = dict(sec)
                sec_copy["products"] = matched
                filtered.append(sec_copy)
        return filtered

    @app.get("/menu/burgers")
    async def legacy_burgers(preference: str | None = None):
        sections = await _cat.get_sections("burger", 1)
        return _filter_sections_by_pref(sections, preference)

    @app.get("/menu/drinks")
    async def legacy_drinks(preference: str | None = None):
        sections = await _cat.get_sections("drink", 1)
        return _filter_sections_by_pref(sections, preference)

    @app.get("/menu/sides")
    async def legacy_sides(preference: str | None = None):
        sections = await _cat.get_sections("side", 1)
        return _filter_sections_by_pref(sections, preference)

    @app.get("/menu/desserts")
    async def legacy_desserts(preference: str | None = None):
        sections = await _cat.get_sections("dessert", 1)
        return _filter_sections_by_pref(sections, preference)

    @app.get("/cart")
    async def legacy_get_cart(session_id: str = "default-kiosk-session"):
        c = await _cs.get_cart(session_id)
        return {
            "success": True,
            "cart": [
                {
                    "line_id": l.line_id,
                    "item_id": l.item_id,
                    "name": l.item_name,
                    "quantity": l.quantity,
                    "unitPrice": float(l.unit_price.amount),
                    "price": float(l.unit_price.amount),
                    "subtotal": float(l.subtotal.amount),
                    "image": l.image,
                    "type": l.line_type,
                    "side": {"name": l.metadata.get("side_name") or "Side Item"} if l.line_type == "meal" else None,
                    "drink": {"name": l.metadata.get("drink_name") or "Beverage"} if l.line_type == "meal" else None,
                }
                for l in c.lines
            ],
            "itemCount": c.item_count,
            "subtotal": float(c.subtotal.amount),
            "total": float(c.subtotal.amount),
        }

    async def _compute_dynamic_category_merchandising(category: str, session_id: str = "default-kiosk-session", branch_id: int = 1, preference: str | None = None):
        cat_norm = category.lower().rstrip("s")
        if cat_norm in ("burger", "burgers"):
            cat_norm = "burger"
        elif cat_norm in ("drink", "drinks", "beverage", "beverages"):
            cat_norm = "drink"
        elif cat_norm in ("side", "sides", "snack", "snacks"):
            cat_norm = "side"
        elif cat_norm in ("dessert", "desserts", "sweet", "sweets"):
            cat_norm = "dessert"

        target_session = session_id or "default-kiosk-session"
        items = await _cat.get_by_category(cat_norm, branch_id)
        if not items:
            items = await _cat.get_all_available(branch_id)

        cart = await _cs.get_cart(target_session)
        cart_item_ids = {line.item_id for line in cart.lines}
        cart_categories = [line.category.lower() for line in cart.lines]
        cart_item_names = [line.item_name.lower() for line in cart.lines]

        from app.infrastructure.repositories.catalog_repository import get_category_default_image
        from app.intelligence.recommendation.session_learner import SessionLearner
        from app.intelligence.recommendation.heuristics.circadian_clock import CircadianCravingAnalyzer
        from app.intelligence.recommendation.llm_merchandising_engine import (
            record_impressions,
            get_impression_penalty,
        )

        circadian_phase = CircadianCravingAnalyzer.get_current_circadian_phase()
        phase_labels = {
            "morning": "🌅 Morning Warm-Up",
            "lunch": "☀️ Lunch Rush",
            "afternoon_snack": "🍟 Afternoon Snack",
            "dinner": "🍔 Dinner Rush",
            "late_night": "🌙 Late-Night Comfort",
        }
        circadian_badge = phase_labels.get(circadian_phase, "⭐ Chef's Picks")

        profile = SessionLearner.update_from_cart(target_session, cart.lines)
        intent_mode = profile.basket_intent_mode

        # Update dietary lock if explicit preference provided
        if preference:
            pref_l = preference.lower().strip()
            if pref_l in ("veg", "non veg", "non_veg"):
                profile.dietary_lock = "veg" if pref_l == "veg" else "non_veg"
            elif pref_l == "both":
                profile.dietary_lock = None

        effective_dietary = (preference or profile.dietary_lock or "").lower()

        has_spicy_cart = any("peri" in n or "spicy" in n or "fiery" in n for n in cart_item_names)
        has_burger_cart = any("burger" in c for c in cart_categories)
        has_drink_cart = any("drink" in c or "beverage" in c or "coke" in n or "pepsi" in n for c, n in zip(cart_categories, cart_item_names))

        context_headline = "Curated For You"
        context_subline = "Hand-picked favorites to complete your meal"

        if intent_mode == "premium_beverage":
            context_headline = "✨ Essential Bites to Pair with Your Drink"
            context_subline = "Flame-grilled burgers & golden sides to complete your beverage"
        elif intent_mode == "budget_hunter":
            context_headline = "⭐ Smart Value Deals & Micro-Upgrades"
            context_subline = "Unbeatable taste that respects your wallet"
        elif circadian_phase == "morning":
            context_headline = "🌅 Morning Warm-Up & Breakfast Picks"
            context_subline = "Fresh energizing brew & light morning favorites"
        elif circadian_phase == "late_night":
            context_headline = "🌙 Late-Night Indulgence & Comfort Food"
            context_subline = "Satisfy your midnight cravings with rich, warm comfort"

        dismissed_ids = getattr(profile, "dismissed_item_ids", set()) or set()
        excluded_ids = cart_item_ids | dismissed_ids
        valid_candidates = [it for it in items if it.id not in excluded_ids]

        # Strictly enforce dietary lock for vegetarian selections
        if "veg" in effective_dietary and "non" not in effective_dietary:
            valid_candidates = [it for it in valid_candidates if it.food_type and "veg" in str(it.food_type).lower() and "non" not in str(it.food_type).lower()]
        elif "non" in effective_dietary:
            valid_candidates = [it for it in valid_candidates if it.food_type and "non" in str(it.food_type).lower()]

        if not valid_candidates:
            from app.intelligence.recommendation.gatekeeper import Gatekeeper
            valid_candidates = Gatekeeper.handle_zero_candidates_fallback(items, limit=6)
            if "veg" in effective_dietary and "non" not in effective_dietary:
                valid_candidates = [it for it in valid_candidates if it.food_type and "veg" in str(it.food_type).lower() and "non" not in str(it.food_type).lower()]

        cart_dicts = [
            {"id": l.item_id, "name": l.item_name, "unit_price": float(l.unit_price.amount), "category": str(l.category)}
            for l in cart.lines
        ]
        llm_merch = await _merchandising_engine.improvise_merchandising(
            session_id=target_session,
            category=cat_norm,
            cart_items=cart_dicts,
            candidates=valid_candidates,
            circadian_phase=circadian_phase,
            session_behavior={"removed_item": profile.last_removed_item, "mode": intent_mode},
            dietary_preference=profile.dietary_lock,
        )

        llm_headline = llm_merch.get("headline") or context_headline
        llm_subline = llm_merch.get("subline") or context_subline
        manifestation_nudge = llm_merch.get("manifestation_nudge") or "🔥 Hand-crafted fresh for you"
        llm_items = llm_merch.get("items", {})

        scored = []
        for it in valid_candidates:
            p_val = float(it.price.amount)
            name_lower = it.name.lower()
            score = 1.0
            badge = "🔥 Top Pick"
            reason = "Customer favorite at Burger King"

            circ_mult, _ = CircadianCravingAnalyzer.evaluate_circadian_multiplier(it)
            score *= circ_mult

            # Novelty rotation penalty
            score *= get_impression_penalty(target_session, it.id)

            if intent_mode == "premium_beverage":
                if cat_norm in ("burger", "side"):
                    score += 1.30
                    badge = "🍔 Essential Meal Bite"
                    reason = "Essential flame-grilled pairing to complete your drink"
                elif cat_norm == "drink":
                    score *= 0.40
            elif intent_mode == "budget_hunter":
                if p_val <= 69.0:
                    score += 1.50
                    badge = "⭐ Unbeatable Value"
                    reason = "Pocket-friendly treat packed with taste"
                elif p_val <= 100.0:
                    score += 0.80
                    badge = "⭐ Great Value"
                    reason = "Hearty flavor that stays easy on your wallet"
                elif p_val > 140.0:
                    score *= 0.15
            elif has_spicy_cart and any(k in name_lower for k in ["shake", "sundae", "coffee", "float", "ice"]):
                score += 0.95
                badge = "❄️ Calms The Spice"
                reason = "Cooling soothing pair to soothe your spicy dish"
            elif has_burger_cart and not has_drink_cart and cat_norm in ("drink", "beverage"):
                score += 0.85
                badge = "🥤 Perfect Burger Wash"
                reason = "Refreshing sip to balance your burger"
            elif any(k in name_lower for k in ["whopper", "royale", "cold coffee", "peri peri fries"]):
                score += 0.50
                badge = "🔥 Signature Bestseller"
                reason = "King of the menu, flame-grilled perfection"
            elif any(k in name_lower for k in ["sundae", "shake", "lava"]):
                score += 0.40
                badge = "✨ Sweet Indulgence"
                reason = "Rich velvety dessert to complete your meal"

            it_merch = llm_items.get(it.id, {})
            if it_merch:
                score *= it_merch.get("synergy_score", 1.0)
                if it_merch.get("badge"):
                    badge = it_merch["badge"]
                if it_merch.get("sensory_rationale"):
                    reason = it_merch["sensory_rationale"]

            scored.append((score, badge, reason, it, it_merch))

        scored.sort(key=lambda x: x[0], reverse=True)

        result = []
        for s, badge, reason, it, it_merch in scored:
            fallback = get_category_default_image(it.category, it.name)
            img = it.image or fallback
            if img and not img.startswith("http") and not img.startswith("/"):
                img = "/" + img
            meal_img = it.meal_image or img
            if meal_img and not meal_img.startswith("http") and not meal_img.startswith("/"):
                meal_img = "/" + meal_img
            is_veg = bool(it.food_type and "veg" in str(it.food_type).lower() and "non" not in str(it.food_type).lower())

            has_micro_deal = it_merch.get("has_micro_deal", False)
            orig_price = it_merch.get("original_price", float(it.price.amount))
            offer_price = it_merch.get("offer_price", float(it.price.amount))
            discount_pct = it_merch.get("discount_pct", 0)
            deal_tag = it_merch.get("deal_tag")

            result.append({
                "id": it.id,
                "name": it.name,
                "price": offer_price if has_micro_deal else orig_price,
                "original_price": orig_price,
                "offer_price": offer_price,
                "has_micro_deal": has_micro_deal,
                "discount_pct": discount_pct,
                "deal_tag": deal_tag,
                "image": img,
                "meal_image": meal_img,
                "category": str(it.category.value if hasattr(it.category, "value") else it.category),
                "type": "veg" if is_veg else "non veg",
                "foodType": "veg" if is_veg else "non veg",
                "shortDescription": it.short_description or it.name,
                "badge": badge,
                "synergy_reason": reason,
                "is_meal_available": it.is_meal_available,
            })

        record_impressions(target_session, [x["id"] for x in result[:8]])

        return {
            "all_serialized": result,
            "headline": llm_headline,
            "subline": llm_subline,
            "manifestation_nudge": manifestation_nudge,
            "circadian_badge": circadian_badge,
            "intent_mode": intent_mode,
        }

    @app.post("/session/preference")
    async def set_session_preference(payload: dict):
        sid = payload.get("session_id", "default-kiosk-session")
        pref = (payload.get("preference") or "both").strip().lower()
        from app.intelligence.recommendation.session_learner import SessionLearner
        SessionLearner.set_explicit_dietary_override(sid, pref)
        profile = SessionLearner.get_or_create_profile(sid)
        return {
            "success": True,
            "session_id": sid,
            "preference": pref,
            "dietary_lock": profile.dietary_lock,
            "is_explicit_override": profile.is_explicit_override,
        }

    @app.post("/session/reset")
    async def reset_session_endpoint(payload: dict):
        sid = payload.get("session_id", "default-kiosk-session")
        from app.intelligence.recommendation.session_learner import SessionLearner
        SessionLearner.clear_profile(sid)
        try:
            await _cs.clear_cart(sid)
        except Exception:
            pass
        return {"success": True, "session_id": sid, "message": "Session reset successfully"}

    @app.get("/menu/spotlight/{category}")
    async def get_menu_spotlight(category: str, session_id: str = "default-kiosk-session", branch_id: int = 1, preference: str | None = None):
        if preference:
            from app.intelligence.recommendation.session_learner import SessionLearner
            p = SessionLearner.get_or_create_profile(session_id)
            if preference.lower() in ("veg", "non veg", "non_veg"):
                p.dietary_lock = "veg" if preference.lower() == "veg" else "non_veg"
        data = await _compute_dynamic_category_merchandising(category, session_id, branch_id, preference=preference)
        return {
            "success": True,
            "category": category,
            "headline": data["headline"],
            "subline": data["subline"],
            "manifestation_nudge": data["manifestation_nudge"],
            "circadian_badge": data["circadian_badge"],
            "intent_mode": data["intent_mode"],
            "spotlight": data["all_serialized"][:4],
        }

    @app.get("/recommendations/category/{category}")
    async def get_category_recommendations(
        category: str,
        session_id: str = "default-kiosk-session",
        branch_id: int = 1,
        preference: str | None = None,
    ):
        data = await _compute_dynamic_category_merchandising(category, session_id, branch_id, preference=preference)
        all_items = data["all_serialized"]
        cat_norm = category.lower().rstrip("s")
        intent_mode = data.get("intent_mode", "explorer")

        veg_items = [i for i in all_items if i.get("foodType") == "veg" or i.get("type") == "veg"]
        non_veg_items = [i for i in all_items if i.get("foodType") != "veg" and i.get("type") != "veg"]

        def build_set(lst):
            pool = lst if lst else all_items
            prio = pool[:2] if len(pool) >= 2 else (pool * 2)[:2]
            remaining = [i for i in pool if i["id"] not in {p["id"] for p in prio}]
            if not remaining:
                remaining = pool
            if intent_mode == "budget_hunter":
                prem_cands = [i for i in remaining if i.get("original_price", 999) <= 140]
                prem = prem_cands[:2] if len(prem_cands) >= 2 else (prem_cands + remaining)[:2]
            else:
                prem = remaining[:2] if len(remaining) >= 2 else (remaining + pool)[:2]
            used_ids = {p["id"] for p in prio} | {p["id"] for p in prem}
            add = [i for i in pool if i["id"] not in used_ids][:4]
            if len(add) < 4:
                extra = [i for i in pool if i["id"] not in {a["id"] for a in add}]
                add = (add + extra + pool)[:4]
            return {
                "priority": prio,
                "premium": prem,
                "additional": add,
            }

        both_prio = []
        if veg_items:
            both_prio.append(veg_items[0])
        if non_veg_items:
            both_prio.append(non_veg_items[0])
        if len(both_prio) < 2:
            both_prio = all_items[:2]

        remaining_both = [i for i in all_items if i not in both_prio]
        if intent_mode == "budget_hunter":
            both_prem_cands = [i for i in remaining_both if i["original_price"] <= 140]
            both_prem = both_prem_cands[:2] if len(both_prem_cands) >= 2 else (both_prem_cands + remaining_both)[:2]
        else:
            both_prem = remaining_both[:2] if len(remaining_both) >= 2 else (remaining_both + all_items)[:2]

        both_add = [i for i in all_items if i not in both_prio and i not in both_prem][:4]

        from app.intelligence.recommendation.session_learner import SessionLearner
        prof = SessionLearner.get_or_create_profile(session_id)
        eff_pref = (preference or prof.dietary_lock or "").lower().strip()

        if eff_pref == "veg" and veg_items:
            top_set = build_set(veg_items)
            prio, prem, add = top_set["priority"], top_set["premium"], top_set["additional"]
        elif "non" in eff_pref and non_veg_items:
            top_set = build_set(non_veg_items)
            prio, prem, add = top_set["priority"], top_set["premium"], top_set["additional"]
        else:
            prio = both_prio if both_prio else all_items[:2]
            prem = both_prem if both_prem else (all_items[2:4] if len(all_items) >= 4 else all_items[:2])
            add = both_add if both_add else (all_items[4:8] if len(all_items) >= 8 else all_items[:4])

        return {
            "success": True,
            "category": category,
            "headline": data["headline"],
            "subline": data["subline"],
            "manifestation_nudge": data["manifestation_nudge"],
            "circadian_badge": data["circadian_badge"],
            "intent_mode": intent_mode,
            "priority": prio,
            "premium": prem,
            "additional": add,
            "both": {
                "priority": both_prio,
                "premium": both_prem,
                "additional": both_add,
            },
            "veg": build_set(veg_items) if veg_items else build_set(all_items),
            "non_veg": build_set(non_veg_items) if non_veg_items else build_set(all_items),
        }

    @app.post("/meal/options")
    async def legacy_meal_options(payload: dict):
        item_id = payload.get("item_id")
        if not item_id:
            return {"success": False, "is_meal_available": False}
        burger = await _cat.get_by_id(item_id, 1)
        if not burger or not burger.is_meal_available:
            return {"success": True, "product_id": item_id, "is_meal_available": False}

        from app.infrastructure.repositories.catalog_repository import get_category_default_image
        from app.intelligence.recommendation.heuristics.sensory_contrast import SensoryContrastAnalyzer

        sides = await _cat.get_by_category("side", 1)
        drinks = await _cat.get_by_category("drink", 1)

        sid = payload.get("session_id", "default-kiosk-session")
        from app.intelligence.recommendation.session_learner import SessionLearner
        profile = SessionLearner.get_or_create_profile(sid)
        req_pref = (payload.get("preference") or "").lower().strip()
        if req_pref in ("veg", "non_veg", "non veg"):
            norm_p = "veg" if req_pref == "veg" else "non_veg"
            SessionLearner.set_explicit_dietary_override(sid, norm_p)

        effective_pref = profile.dietary_lock or ("veg" if req_pref == "veg" else None)
        is_burger_veg = bool(burger.food_type and "veg" in str(burger.food_type).lower() and "non" not in str(burger.food_type).lower())
        if is_burger_veg or effective_pref == "veg":
            sides = [s for s in sides if s.food_type and "veg" in str(s.food_type).lower() and "non" not in str(s.food_type).lower()]

        # Classify burger sensory characteristics
        burger_profiles = SensoryContrastAnalyzer.classify_flavor_profile(burger.name, "burger", burger.short_description or "")

        # Dynamic scoring and ranking for SIDES
        scored_sides = []
        for s in sides:
            s_profiles = SensoryContrastAnalyzer.classify_flavor_profile(s.name, "side", s.short_description or "")
            score = 1.0
            badge = None
            reason = "Crispy golden side"

            if "spicy" in burger_profiles:
                if "cooling_dairy" in s_profiles or "sweet" in s_profiles:
                    score += 0.60
                    badge = "❄️ Cools the Spice"
                    reason = "Cooling contrast soothes the spicy flame-grilled heat"
                elif "spicy" in s_profiles:
                    score -= 0.20
                    badge = "🌶️ Double Spice"
                    reason = "For extreme heat lovers"
            elif "heavy_savory" in burger_profiles:
                if "fries" in s.name.lower():
                    score += 0.45
                    badge = "⭐ Included Classic"
                    reason = "Golden crisp fries perfectly pair with the flame-grilled patty"

            if "medium" in s.name.lower():
                badge = badge or "⭐ Included Value"
            elif "king" in s.name.lower():
                badge = "👑 King Size Upgrade"

            scored_sides.append((score, badge, reason, s))

        scored_sides.sort(key=lambda x: x[0], reverse=True)
        ranked_sides = [x[3] for x in scored_sides]
        side_meta = {x[3].id: (x[1], x[2], i < 2) for i, x in enumerate(scored_sides)}

        # Dynamic scoring and ranking for DRINKS
        scored_drinks = []
        for d in drinks:
            d_profiles = SensoryContrastAnalyzer.classify_flavor_profile(d.name, "drink", d.short_description or "")
            score = 1.0
            badge = None
            reason = "Refreshing beverage pairing"

            if "spicy" in burger_profiles:
                if "cooling_dairy" in d_profiles or "shake" in d.name.lower() or "float" in d.name.lower():
                    score += 0.65
                    badge = "🍦 Calms Peri Peri Heat"
                    reason = "Velvety ice cream / shake instantly calms the spicy burn"
                elif "carbonated_refreshing" in d_profiles:
                    score += 0.40
                    badge = "❄️ Chilled Fizz"
                    reason = "Icy fizz cleanses the palate after every bite"
            elif "heavy_savory" in burger_profiles:
                if "carbonated_refreshing" in d_profiles or "coke" in d.name.lower():
                    score += 0.50
                    badge = "🥤 Cuts the Richness"
                    reason = "Bubbly carbonation cuts right through rich savory patties"

            if "coca cola" in d.name.lower() or "coke" in d.name.lower():
                badge = badge or "⭐ Included Classic"
            elif "coffee" in d.name.lower():
                badge = "☕ Cold Brew Energizer"
            elif "shake" in d.name.lower():
                badge = "🍫 Creamy Shake Upgrade"

            scored_drinks.append((score, badge, reason, d))

        scored_drinks.sort(key=lambda x: x[0], reverse=True)
        ranked_drinks = [x[3] for x in scored_drinks]
        drink_meta = {x[3].id: (x[1], x[2], i < 2) for i, x in enumerate(scored_drinks)}

        # Determine dynamic exact sensory contrast matches
        best_dynamic_side = ranked_sides[0] if ranked_sides else None
        best_dynamic_drink = ranked_drinks[0] if ranked_drinks else None

        default_side_med = best_dynamic_side or (ranked_sides[0] if ranked_sides else None)
        default_side_lrg = next((s for s in ranked_sides if "large" in s.name.lower() or "king" in s.name.lower()), default_side_med)
        default_drink = best_dynamic_drink or (ranked_drinks[0] if ranked_drinks else None)

        def serialize_opt(item, is_default=False, baseline_price=0.0, meta_dict=None):
            img = item.image or ""
            if not img or not img.strip():
                img = get_category_default_image(item.category, item.name)
            elif not img.startswith("http") and not img.startswith("/"):
                img = "/" + img

            p = float(item.price.amount)
            extra = 0.0 if is_default else max(0.0, round(p - baseline_price, 2))
            badge, reason, is_rec = (meta_dict.get(item.id) if meta_dict else (None, "", False))
            is_item_veg = bool(item.food_type and "veg" in str(item.food_type).lower() and "non" not in str(item.food_type).lower())
            return {
                "id": item.id,
                "name": item.name,
                "image": img,
                "price": p,
                "extra_price": extra,
                "is_default": is_default,
                "section": item.section or "Featured",
                "foodType": "veg" if is_item_veg else "non veg",
                "food_type": "veg" if is_item_veg else "non_veg",
                "type": "veg" if is_item_veg else "non veg",
                "recommendation_badge": badge,
                "synergy_reason": reason,
                "is_recommended": is_rec or is_default,
            }

        b_img = burger.meal_image or burger.image or ""
        if not b_img or not b_img.strip():
            b_img = get_category_default_image(burger.category, burger.name)
        elif not b_img.startswith("http") and not b_img.startswith("/"):
            b_img = "/" + b_img

        burger_data = {
            "id": burger.id,
            "name": burger.name,
            "price": float(burger.price.amount),
            "image": b_img,
            "foodType": "veg" if burger.food_type and "veg" in str(burger.food_type).lower() else "non veg",
        }

        def build_meal(size: str, upgrade_price: float, def_side, def_drink):
            base_side_price = float(def_side.price.amount) if def_side else 0.0
            base_drink_price = float(def_drink.price.amount) if def_drink else 0.0

            s_options = [
                serialize_opt(s, is_default=(def_side is not None and s.id == def_side.id), baseline_price=base_side_price, meta_dict=side_meta)
                for s in ranked_sides
            ]
            d_options = [
                serialize_opt(d, is_default=(def_drink is not None and d.id == def_drink.id), baseline_price=base_drink_price, meta_dict=drink_meta)
                for d in ranked_drinks
            ]

            top_side_reason = side_meta.get(def_side.id, (None, "Golden crispy fries balance the burger"))[1] if def_side else ""
            top_drink_reason = drink_meta.get(def_drink.id, (None, "Ice-cold fizz refreshes the palate"))[1] if def_drink else ""

            top_side_name = def_side.name if def_side else "Golden Fries"
            top_drink_name = def_drink.name if def_drink else "Chilled Drink"
            dynamic_headline = f"🔥 Complete Your {burger.name} Feast"
            dynamic_subtitle = f"Pair with {top_side_name} and {top_drink_name} — Save over ₹45 compared to singles!"
            manifestation_tag = "⚡ 84% of diners make it a meal for complete satisfaction"

            return {
                "size": size,
                "burger": burger_data,
                "side": serialize_opt(def_side, True, base_side_price, meta_dict=side_meta) if def_side else {},
                "drink": serialize_opt(def_drink, True, base_drink_price, meta_dict=drink_meta) if def_drink else {},
                "burger_price": float(burger.price.amount),
                "upgrade_price": upgrade_price,
                "meal_price": float(burger.price.amount) + upgrade_price,
                "side_options": s_options,
                "drink_options": d_options,
                "pairing_headline": f"✨ Chef's Pairing: {burger.name} Deluxe Meal",
                "pairing_rationale": f"{top_drink_reason}. {top_side_reason}.",
                "meal_headline": dynamic_headline,
                "meal_subtitle": dynamic_subtitle,
                "manifestation_tag": manifestation_tag,
            }

        return {
            "success": True,
            "product_id": burger.id,
            "product_name": burger.name,
            "is_meal_available": True,
            "meal_headline": f"🔥 Make It a Meal & Save ₹45!",
            "meal_subtitle": f"Upgrade {burger.name} with golden crispy fries & a refreshing drink.",
            "manifestation_tag": "⚡ 84% of diners choose a meal upgrade today",
            "meals": {
                "medium": build_meal("medium", 140.0, default_side_med, default_drink),
                "large": build_meal("large", 145.0, default_side_lrg, default_drink),
            },
        }

    @app.post("/meal/decline")
    async def legacy_meal_decline(payload: dict = None):
        if payload:
            sid = payload.get("session_id", "default-kiosk-session")
            item_id = payload.get("item_id")
            if sid and item_id:
                try:
                    SessionLearner.record_dismissal(sid, int(item_id), "meal")
                except Exception:
                    pass
        return {"success": True, "message": "Meal offer declined"}

    @app.post("/cart/add")
    async def legacy_cart_add_item(payload: dict):
        item_id = payload.get("item_id")
        item_name = payload.get("item_name")
        quantity = int(payload.get("quantity", 1))
        session_id = payload.get("session_id", "default-kiosk-session")
        branch_id = int(payload.get("branch_id", 1))

        if not item_id and item_name:
            items = await _cat.search_by_name(item_name, branch_id)
            if items:
                item_id = items[0].id

        if not item_id:
            return JSONResponse(status_code=400, content={"success": False, "message": "Item ID required"})

        # Re-query inventory directly for live stock_qty at relevant branch_id
        live_stock = await _cat.get_live_stock(int(item_id), branch_id)
        if live_stock < quantity:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "error_code": "OUT_OF_STOCK",
                    "message": f"Item is no longer available (in stock: {live_stock})",
                },
            )

        item = await _cat.get_by_id(int(item_id), branch_id)
        if not item or not item.is_available:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "error_code": "ITEM_UNAVAILABLE",
                    "message": "Item is currently unavailable",
                },
            )

        custom_val = payload.get("offer_price") or payload.get("price")
        custom_p = None
        if custom_val is not None:
            try:
                from decimal import Decimal
                cand_val = Decimal(str(custom_val))
                # Only accept custom price if it is non-zero and not equal to default item price
                if cand_val > 0 and cand_val != item.price.amount:
                    custom_p = cand_val
            except Exception:
                custom_p = None

        deal_meta = {}
        if payload.get("deal_tag"):
            deal_meta["deal_tag"] = payload.get("deal_tag")
        if payload.get("has_micro_deal"):
            deal_meta["has_micro_deal"] = True

        try:
            await _cs.add_item(
                session_id=session_id,
                item_id=item.id,
                quantity=quantity,
                branch_id=branch_id,
                custom_price=custom_p,
                metadata=deal_meta or None,
            )
        except ValueError as exc:
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": str(exc)},
            )

        c = await _cs.get_cart(session_id)
        SessionLearner.update_from_cart(session_id, c.lines)
        try:
            from app.intelligence.recommendation.bandit import ThompsonSamplingBandit
            from app.intelligence.recommendation.heuristics.kitchen_load import KitchenLoadTracker
            ThompsonSamplingBandit.record_interaction("product_rec", item.id, converted=True)
            ThompsonSamplingBandit.record_interaction("checkout_rec", item.id, converted=True)
            station = KitchenLoadTracker.map_item_to_station(item)
            KitchenLoadTracker.increment_queue(branch_id, station, delta=quantity)
        except Exception:
            pass
        return await legacy_get_cart(session_id=session_id)

    @app.post("/cart/add-meal")
    async def legacy_cart_add_meal(payload: dict):
        meal = payload.get("meal", {})
        qty = int(payload.get("quantity", 1))
        session_id = payload.get("session_id", "default-kiosk-session")
        branch_id = int(payload.get("branch_id", 1))
        burger_info = meal.get("burger", {})
        side_info = meal.get("side", {})
        drink_info = meal.get("drink", {})

        # Live stock validation across all meal components
        for comp_lbl, c_id in [("Burger", burger_info.get("id")), ("Side", side_info.get("id")), ("Drink", drink_info.get("id"))]:
            if c_id:
                stk = await _cat.get_live_stock(int(c_id), branch_id)
                if stk < qty:
                    return JSONResponse(
                        status_code=400,
                        content={
                            "success": False,
                            "error_code": "OUT_OF_STOCK",
                            "message": f"{comp_lbl} component is out of stock (available: {stk})",
                        },
                    )
        size = meal.get("size", "medium").capitalize()
        custom_patty = meal.get("custom_patty")
        if custom_patty and custom_patty.get("name"):
            meal_name = f"{burger_info.get('name', 'Burger')} Meal ({size}) w/ {custom_patty.get('name')}"
        else:
            meal_name = f"{burger_info.get('name', 'Burger')} Meal ({size})"
        
        base_meal_price = float(meal.get("meal_price", 199.0) or 199.0)
        side_extra = float(side_info.get("extra_price", 0.0) or 0.0)
        drink_extra = float(drink_info.get("extra_price", 0.0) or 0.0)
        patty_extra = float(meal.get("patty_extra", 0.0) or 0.0)
        price_val = round(base_meal_price + side_extra + drink_extra + patty_extra, 2)

        c = await _cs.get_cart(session_id)
        from app.domain.cart.entities import MealComposition
        from app.domain.catalog.value_objects import Price
        from decimal import Decimal

        meal_comp = MealComposition(
            size=size,
            main_item_id=int(burger_info.get("id", 1)),
            main_item_name=burger_info.get("name", "Burger"),
            side_id=int(side_info.get("id", 65) or 65),
            side_name=side_info.get("name", "Fries"),
            drink_id=int(drink_info.get("id", 40) or 40),
            drink_name=drink_info.get("name", "Coke"),
            burger_price=Price(Decimal(str(base_meal_price))),
            upgrade_price=Price(Decimal(str(patty_extra))),
            side_extra=Price(Decimal(str(side_extra))),
            drink_extra=Price(Decimal(str(drink_extra))),
        )
        added_line = c.add_meal(meal_comp, quantity=qty)
        # Preserve custom metadata and rich meal name
        if custom_patty and custom_patty.get("name"):
            added_line.item_name = meal_name
        added_line.food_type = burger_info.get("foodType")
        added_line.image = burger_info.get("image")
        if added_line.metadata:
            added_line.metadata.update({
                "side_extra": side_extra,
                "drink_extra": drink_extra,
                "custom_patty": custom_patty,
                "custom_toppings": meal.get("custom_toppings"),
            })

        await _cs._save_cart(c)
        SessionLearner.update_from_cart(session_id, c.lines)
        return await legacy_get_cart(session_id=session_id)

    @app.post("/cart/clear")
    async def legacy_cart_clear(payload: dict | None = None):
        session_id = (payload or {}).get("session_id", "default-kiosk-session")
        c = await _cs.get_cart(session_id)
        c.lines.clear()
        await _cs._save_cart(c)
        SessionLearner.update_from_cart(session_id, [])
        return {"success": True, "cart": [], "itemCount": 0, "subtotal": 0.0, "total": 0.0}

    @app.patch("/cart/item")
    async def legacy_cart_update_item(payload: dict):
        from app.intelligence.recommendation.session_learner import SessionLearner
        item_index = payload.get("item_index", 0)
        action = payload.get("action", "increase")
        session_id = payload.get("session_id", "default-kiosk-session")
        c = await _cs.get_cart(session_id)
        if 0 <= item_index < len(c.lines):
            line = c.lines[item_index]
            if action == "increase":
                line.quantity += 1
            elif action == "decrease":
                line.quantity -= 1
                if line.quantity <= 0:
                    removed = c.lines.pop(item_index)
                    SessionLearner.record_removal(session_id, {
                        "id": removed.item_id,
                        "name": removed.item_name,
                        "price": float(removed.unit_price.amount),
                        "category": removed.category,
                        "food_type": removed.food_type,
                    })
            elif action == "delete":
                removed = c.lines.pop(item_index)
                SessionLearner.record_removal(session_id, {
                    "id": removed.item_id,
                    "name": removed.item_name,
                    "price": float(removed.unit_price.amount),
                    "category": removed.category,
                    "food_type": removed.food_type,
                })
            await _cs._save_cart(c)
            SessionLearner.update_from_cart(session_id, c.lines)
        return await legacy_get_cart(session_id=session_id)

    @app.get("/recommendations/winback")
    async def get_winback_recommendation(session_id: str = "default-kiosk-session", branch_id: int = 1):
        # Eradicated: winback is disabled to prevent cart abandonment gamification exploits
        return {"success": False, "has_winback": False, "message": "Winback feature eradicated"}

    @app.delete("/cart")
    async def legacy_clear_cart(session_id: str = "default-kiosk-session"):
        await _cs.clear_cart(session_id)
        return {"success": True, "cart": [], "itemCount": 0, "subtotal": 0.0, "total": 0.0}

    from app.api.v1.conversation import handle_message, MessageRequest

    @app.post("/message")
    async def legacy_message(payload: dict):
        req = MessageRequest(**payload)
        return await handle_message(req)

    @app.get("/recommendations/checkout")
    async def legacy_get_checkout_recommendations(session_id: str = "default-kiosk-session", branch_id: int = 1):
        from app.api.v1.recommendations import get_checkout_recommendations as v1_get_checkout
        return await v1_get_checkout(session_id=session_id, branch_id=branch_id)

    @app.post("/recommendations")
    @app.post("/recommendations/checkout")
    async def legacy_post_checkout_recommendations(req: dict):
        from app.api.v1.recommendations import post_checkout_recommendations as v1_post_checkout, CheckoutRecommendationRequest
        typed_req = CheckoutRecommendationRequest(**req)
        return await v1_post_checkout(typed_req)

    from app.intelligence.intent.stt_intent_firewall import STTIntentFirewall
    _stt_firewall = STTIntentFirewall()

    @app.post("/recommendations/contextual")
    async def get_contextual_recommendations(payload: dict, session_id: str = "default-kiosk-session", branch_id: int = 1):
        session = await _session_svc.get_session(session_id)
        if not session:
            session = await _session_svc.start_session()
        
        recs = await _rec_engine.get_contextual_recommendations(session, payload, branch_id=branch_id, limit=4)
        
        from app.infrastructure.repositories.catalog_repository import get_category_default_image

        def serialize_rec(item):
            fallback = get_category_default_image(item.category, item.name)
            img = item.image or fallback
            if img and not img.startswith("http") and not img.startswith("/"):
                img = "/" + img
            return {
                "id": item.id,
                "name": item.name,
                "price": float(item.price.amount),
                "image": img,
                "category": str(item.category.value if hasattr(item.category, "value") else item.category),
                "foodType": "veg" if item.food_type and "veg" in str(item.food_type).lower() else "non veg",
                "shortDescription": item.short_description or item.name,
            }

        return {
            "success": True,
            "recommendations": [serialize_rec(r) for r in recs],
        }

    @app.post("/intent/stt-firewall")
    async def parse_stt_intent(payload: dict):
        transcript = payload.get("transcript", "")
        intent_result = await _stt_firewall.parse_stt_transcript(transcript)
        return {"success": True, "intent": intent_result}

    @app.get("/recommendations/product/{item_id}")
    async def get_product_recommendations(item_id: int, session_id: str = "default-kiosk-session", branch_id: int = 1):
        import time
        from app.intelligence.recommendation.session_learner import SessionLearner
        from app.intelligence.recommendation.heuristics.circadian_clock import CircadianCravingAnalyzer
        from app.intelligence.recommendation.scoring import RecommendationContext, evaluate_7tier_pipeline
        from app.intelligence.recommendation.gatekeeper import Gatekeeper
        from app.observability.recommendation_telemetry import RecommendationTelemetryLogger
        from app.infrastructure.repositories.catalog_repository import get_category_default_image
        from app.intelligence.recommendation.llm_merchandising_engine import (
            get_impression_penalty,
            record_impressions,
        )

        t0 = time.time()
        target_session = session_id or "default-kiosk-session"
        prod = await _cat.get_by_id(item_id, branch_id)
        if not prod:
            return {"success": False, "recommendations": []}

        anchor_price = float(prod.price.amount)
        anchor_is_veg = bool(prod.food_type and "veg" in str(prod.food_type).lower() and "non" not in str(prod.food_type).lower())

        cat_raw = str(prod.category.value if hasattr(prod.category, "value") else prod.category).lower()
        cat_norm = "burger" if "burger" in cat_raw else ("drink" if "drink" in cat_raw else ("side" if "side" in cat_raw else ("dessert" if "dessert" in cat_raw else "burger")))

        if cat_norm == "burger":
            target_sequence = ["side", "drink", "dessert"]
        elif cat_norm == "drink":
            target_sequence = ["side", "burger", "dessert"]
        elif cat_norm == "side":
            target_sequence = ["drink", "burger", "dessert"]
        else:
            target_sequence = ["drink", "side", "burger"]

        cart = await _cs.get_cart(target_session)
        profile = SessionLearner.get_or_create_profile(target_session)
        dismissed_ids = getattr(profile, "dismissed_item_ids", set()) or set()
        strict_veg = anchor_is_veg or (profile.dietary_lock == "veg")
        circadian_phase = CircadianCravingAnalyzer.get_current_circadian_phase()

        # Build v4 Unified Context Object
        context = RecommendationContext(
            session_id=target_session,
            user_id=None,
            user_profile=None,
            cart_lines=cart.lines,
            dismissed_item_ids=dismissed_ids,
            dietary_lock="veg" if strict_veg else None,
            intent_mode=profile.basket_intent_mode,
            branch_id=branch_id,
            circadian_phase=circadian_phase,
            anchor_item=prod,
        )

        # Collect catalog candidates across complementary sequence and evaluate per role independently
        all_candidate_items = []
        candidates_telemetry = []
        selected_winner_entries = []
        confidence_floor = 0.15

        for comp_cat in target_sequence:
            cat_items = await _cat.get_by_category(comp_cat, branch_id)
            all_candidate_items.extend(cat_items)

            # Evaluate 7-Tier Precedence Order for this role independently
            evaluated_role_candidates, _ = evaluate_7tier_pipeline(
                candidates=cat_items,
                context=context,
                anchor_price=anchor_price,
            )
            candidates_telemetry.extend(evaluated_role_candidates)

            # Per-role top-1 winner with per-slot silence
            valid_role_candidates = [c for c in evaluated_role_candidates if c["composite_score"] >= confidence_floor]
            if valid_role_candidates:
                selected_winner_entries.append(valid_role_candidates[0])

        # Presentation Ordering: Re-sort winning items by composite_score descending
        # so that the highest scoring recommendation displays first
        selected_winner_entries.sort(key=lambda x: x["composite_score"], reverse=True)
        selected_candidates = [entry["item"] for entry in selected_winner_entries]
        winner_signals = {
            entry["item"].id: entry.get("signals", {})
            for entry in selected_winner_entries
        }

        # Calibrated Gatekeeper: Silence beats bad UX, with zero-candidate fallback
        top_evaluated_score = max([c["composite_score"] for c in candidates_telemetry], default=0.0)
        should_silence, gate_reason = Gatekeeper.should_silence(
            candidate_count=len(selected_candidates),
            top_score=top_evaluated_score,
            session_dismissals=len(dismissed_ids),
            confidence_floor=0.15,
        )

        if should_silence and len(selected_candidates) == 0:
            fallback_items = Gatekeeper.handle_zero_candidates_fallback(all_candidate_items, limit=3)
            if fallback_items:
                selected_candidates = fallback_items
                should_silence = False
                gate_reason = "zero_candidate_fallback_engaged"

        if should_silence:
            RecommendationTelemetryLogger.log_decision(
                session_id=target_session,
                endpoint="/recommendations/product",
                anchor_info={"id": prod.id, "name": prod.name, "price": anchor_price},
                candidates_evaluated=candidates_telemetry,
                served_items=[],
                gatekeeper_decision={"status": "SILENCED", "reason": gate_reason},
                latency_ms=(time.time() - t0) * 1000.0,
            )
            return {
                "success": True,
                "headline": f"✨ Pairs Best with {prod.name}",
                "recommendations": [],
            }

        # Check A/B Testing Holdout Route (Bypassed for kiosk traffic so users receive dynamic intelligent pairings)
        if False and RecommendationTelemetryLogger.should_route_to_baseline_ab(target_session):
            baseline_items = []
            for comp_cat in target_sequence:
                cat_candidates = [
                    it for it in all_candidate_items
                    if str(it.category.value if hasattr(it.category, "value") else it.category).lower() == comp_cat
                    and it.is_in_stock
                ]
                if strict_veg:
                    cat_candidates = [
                        it for it in cat_candidates
                        if bool(it.food_type and "veg" in str(it.food_type).lower() and "non" not in str(it.food_type).lower())
                    ]
                cat_candidates.sort(key=lambda x: getattr(x, "display_order", 0) or 0)
                if cat_candidates:
                    baseline_items.append(cat_candidates[0])
            result = []
            for it in baseline_items:
                fallback = get_category_default_image(it.category, it.name)
                img = it.image or fallback
                if img and not img.startswith("http") and not img.startswith("/"):
                    img = "/" + img
                result.append({
                    "id": it.id,
                    "name": it.name,
                    "price": float(it.price.amount),
                    "original_price": float(it.price.amount),
                    "offer_price": float(it.price.amount),
                    "has_micro_deal": False,
                    "discount_pct": 0,
                    "deal_tag": None,
                    "image": img,
                    "category": str(it.category.value if hasattr(it.category, "value") else it.category),
                    "foodType": "veg" if it.food_type and "veg" in str(it.food_type).lower() and "non" not in str(it.food_type).lower() else "non veg",
                    "shortDescription": it.short_description or it.name,
                    "badge": "⭐ Diner Favorite",
                    "synergy_reason": "Popular guest favorite",
                })
            record_impressions(target_session, [x["id"] for x in result])
            RecommendationTelemetryLogger.log_decision(
                session_id=target_session,
                endpoint="/recommendations/product",
                anchor_info={"id": prod.id, "name": prod.name, "price": anchor_price},
                candidates_evaluated=candidates_telemetry,
                served_items=result,
                gatekeeper_decision={"status": "APPROVED", "reason": "ab_baseline_arm"},
                latency_ms=(time.time() - t0) * 1000.0,
                experiment_arm="baseline",
            )
            return {
                "success": True,
                "headline": f"✨ Popular Favorites with {prod.name}",
                "recommendations": result,
            }
        cart_dicts = [
            {"id": l.item_id, "name": l.item_name, "unit_price": float(l.unit_price.amount), "category": str(l.category)}
            for l in cart.lines
        ]

        llm_merch = await _merchandising_engine.improvise_merchandising(
            session_id=target_session,
            category=cat_norm,
            cart_items=cart_dicts,
            candidates=selected_candidates,
            circadian_phase=circadian_phase,
            session_behavior={"viewing_product": prod.name, "mode": profile.basket_intent_mode},
            dietary_preference=profile.dietary_lock or ("veg" if strict_veg else None),
            candidate_signals=winner_signals,
        )

        llm_items = llm_merch.get("items", {})

        result = []
        for it in selected_candidates:
            fallback = get_category_default_image(it.category, it.name)
            img = it.image or fallback
            if img and not img.startswith("http") and not img.startswith("/"):
                img = "/" + img

            it_merch = llm_items.get(it.id, {})
            has_micro_deal = it_merch.get("has_micro_deal", False)
            orig_p = float(it.price.amount)
            offer_p = it_merch.get("offer_price", orig_p)
            badge = it_merch.get("badge") or "⭐ Chef's Pick"
            reason = it_merch.get("sensory_rationale") or f"Pairs wonderfully with {prod.name}"

            result.append({
                "id": it.id,
                "name": it.name,
                "price": offer_p if has_micro_deal else orig_p,
                "original_price": orig_p,
                "offer_price": offer_p,
                "has_micro_deal": has_micro_deal,
                "discount_pct": it_merch.get("discount_pct", 0),
                "deal_tag": it_merch.get("deal_tag"),
                "image": img,
                "category": str(it.category.value if hasattr(it.category, "value") else it.category),
                "foodType": "veg" if it.food_type and "veg" in str(it.food_type).lower() and "non" not in str(it.food_type).lower() else "non veg",
                "shortDescription": it.short_description or it.name,
                "badge": badge,
                "synergy_reason": reason,
            })

        record_impressions(target_session, [x["id"] for x in result])

        # Log complete decision event with counterfactual candidates for offline evaluation
        RecommendationTelemetryLogger.log_decision(
            session_id=target_session,
            endpoint="/recommendations/product",
            anchor_info={"id": prod.id, "name": prod.name, "price": anchor_price},
            candidates_evaluated=candidates_telemetry,
            served_items=result,
            gatekeeper_decision={"status": "APPROVED", "reason": "passed_confidence_floor"},
            latency_ms=(time.time() - t0) * 1000.0,
            experiment_arm="treatment",
        )

        return {
            "success": True,
            "headline": f"✨ Pairs Best with {prod.name}",
            "recommendations": result,
        }

    @app.get("/proactive/opportunity")
    async def get_proactive_opportunity(
        session_id: str = "default-kiosk-session",
        current_screen: str = "home",
        branch_id: int = 1,
    ):
        try:
            cart = await _cs.get_cart(session_id)
            session = await _session_svc.get_session(session_id)
            if not session:
                session = await _session_svc.start_session()

            opp = await _proactive_engine.evaluate_opportunity(
                session=session,
                cart_lines=cart.lines,
                current_screen=current_screen,
                branch_id=branch_id,
            )
            if not opp:
                return {"success": True, "opportunity": None}

            from app.infrastructure.repositories.catalog_repository import get_category_default_image
            fallback = get_category_default_image(opp.item.category, opp.item.name)
            img = opp.item.image or fallback
            if img and not img.startswith("http") and not img.startswith("/"):
                img = "/" + img

            return {
                "success": True,
                "opportunity": {
                    "type": opp.opportunity_type,
                    "title": opp.title,
                    "description": opp.description,
                    "confidence": opp.confidence_score,
                    "spoken_hint": opp.spoken_hint,
                    "rationale": opp.rationale,
                    "item": {
                        "id": opp.item.id,
                        "name": opp.item.name,
                        "price": float(opp.item.price.amount),
                        "image": img,
                        "category": str(opp.item.category.value if hasattr(opp.item.category, "value") else opp.item.category),
                        "foodType": "veg" if opp.item.food_type and "veg" in str(opp.item.food_type).lower() else "non veg",
                    },
                },
            }
        except Exception as exc:
            logger.warning(f"Error evaluating proactive opportunity: {exc}")
            return {"success": True, "opportunity": None}

    @app.post("/proactive/feedback")
    async def record_proactive_feedback(payload: dict):
        try:
            session_id = payload.get("session_id") or "default-kiosk-session"
            action = payload.get("action", "dismissed")
            item_id = payload.get("item_id")
            opp_type = payload.get("opportunity_type", "proactive")

            from app.domain.session.memory import ContextualObservation, ObservationScope, ObservationSource
            from datetime import datetime, timedelta

            obs = ContextualObservation(
                id=str(uuid.uuid4()),
                session_id=session_id,
                subject="proactive_offer",
                predicate=action,
                value=str(item_id) if item_id else opp_type,
                scope=ObservationScope.SESSION,
                context={"opportunity_type": opp_type},
                confidence=1.0,
                source=ObservationSource.EXPLICIT,
                created_at=datetime.utcnow(),
                expires_at=datetime.utcnow() + timedelta(hours=1),
            )
            await _mem_store.add_observation(obs)
            return {"success": True, "action": action}
        except Exception as exc:
            logger.warning(f"Error recording proactive feedback: {exc}")
            return {"success": True, "action": action}

    @app.post("/order/complete")
    async def legacy_order_complete(payload: dict = None):
        await _cs.clear_cart("default-kiosk-session")
        import random
        return {
            "success": True,
            "order_number": random.randint(1000, 9999),
            "message": "Order completed successfully",
        }


    @app.post("/session/start")
    async def legacy_start_session():
        return {
            "success": True,
            "session_id": "default-kiosk-session",
            "screen": "home",
            "message": "Welcome to Burger King India! How can I help you today?",
            "voice_enabled": True,
        }

    @app.post("/screen")
    async def legacy_screen(payload: dict):
        screen_name = payload.get("screen", "home")
        controls = payload.get("available_controls", [])
        if not controls:
            if any(k in screen_name for k in ["burger", "recommended", "menu"]):
                controls = ["filter_veg", "filter_non_veg", "filter_both", "back_button", "view_more"]
        await _session_svc.sync_screen("default-kiosk-session", screen_name, controls)
        return {"success": True, "screen": screen_name, "available_controls": controls}

    @app.post("/stt")
    async def legacy_stt(file: UploadFile = File(...)):
        try:
            from groq import Groq
            s = get_settings()
            key = s.groq_api_key if isinstance(s.groq_api_key, str) else s.groq_api_key.get_secret_value()
            client = Groq(api_key=key)
            content = await file.read()
            filename = file.filename or "voice.webm"
            whisper_prompt = (
                "Burger King India order kiosk: Whopper, Whopper Jr, Crispy Veg, Paneer Royale, "
                "Fiery Chicken, Classic Fries, Peri Peri Fries, Cold Coffee, Iced Latte, Mocha Frappe, "
                "Chocolate Sundae, BK Fusion, Coke, combo meal, veg, non-veg, spicy, thanda, bill, checkout."
            )
            transcription = client.audio.transcriptions.create(
                file=(filename, content),
                model="whisper-large-v3-turbo",
                prompt=whisper_prompt,
                temperature=0.0,
            )
            raw_text = transcription.text.strip()
            # Clean hallucinated silence / subtitle markers
            clean_text = raw_text
            for noise_tag in ["[BLANK_AUDIO]", "(music)", "(bell)", "[music]", "[applause]", "Thank you.", "Subtitle by"]:
                clean_text = clean_text.replace(noise_tag, "")
            text = clean_text.strip()
            logger.info("stt_success", text=text, raw=raw_text)
            return {"success": True, "text": text}
        except Exception as exc:
            logger.error("stt_failure", error=str(exc))
            return {"success": False, "text": "", "error": str(exc)}

    @app.post("/tts")
    async def legacy_tts(payload: dict):
        try:
            from gtts import gTTS
            text = payload.get("text", "")
            if not text:
                return Response(status_code=400)
            tts = gTTS(text=text, lang="en", tld="co.in")
            fp = io.BytesIO()
            tts.write_to_fp(fp)
            fp.seek(0)
            return Response(content=fp.read(), media_type="audio/mpeg")
        except Exception as exc:
            logger.error("tts_failure", error=str(exc))
            return Response(status_code=500)

    @app.get("/health")
    async def health():
        return {"status": "healthy", "service": settings.app_name, "version": settings.app_version}


    return app


app = create_app()
