"""
app/main.py
Application Entry Point and FastAPI Factory for TheAtom Commercial Intelligence Engine.
"""
from __future__ import annotations
import io
from contextlib import asynccontextmanager
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import Response
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
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 3. Mount versioned API routes
    app.include_router(api_v1_router, prefix=settings.api_prefix)

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

    @app.get("/menu/burgers")
    async def legacy_burgers():
        return await _cat.get_sections("burger", 1)

    @app.get("/menu/drinks")
    async def legacy_drinks():
        return await _cat.get_sections("drink", 1)

    @app.get("/menu/sides")
    async def legacy_sides():
        return await _cat.get_sections("side", 1)

    @app.get("/menu/desserts")
    async def legacy_desserts():
        return await _cat.get_sections("dessert", 1)

    @app.get("/cart")
    async def legacy_get_cart():
        c = await _cs.get_cart("default-kiosk-session")
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
                    "side": {"name": l.metadata.get("side_name", "Fries")} if l.line_type == "meal" else None,
                    "drink": {"name": l.metadata.get("drink_name", "Coke")} if l.line_type == "meal" else None,
                }
                for l in c.lines
            ],
            "itemCount": c.item_count,
            "subtotal": float(c.subtotal.amount),
            "total": float(c.subtotal.amount),
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

        sides = await _cat.get_by_category("side", 1)
        drinks = await _cat.get_by_category("drink", 1)
        
        # Determine baselines from DB
        default_side_med = next((s for s in sides if "fries (medium)" in s.name.lower()), sides[0] if sides else None)
        default_side_lrg = next((s for s in sides if "fries (king)" in s.name.lower()), default_side_med)
        default_drink = next((d for d in drinks if "coca cola" in d.name.lower() or "coke" in d.name.lower()), drinks[0] if drinks else None)

        def serialize_opt(item, is_default=False, baseline_price=0.0):
            img = item.image or ""
            if not img or not img.strip():
                img = get_category_default_image(item.category, item.name)
            elif not img.startswith("http") and not img.startswith("/"):
                img = "/" + img
            
            p = float(item.price.amount)
            extra = 0.0 if is_default else max(0.0, round(p - baseline_price, 2))
            return {
                "id": item.id,
                "name": item.name,
                "image": img,
                "price": p,
                "extra_price": extra,
                "is_default": is_default,
                "section": item.section or "Featured",
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
                serialize_opt(s, is_default=(def_side is not None and s.id == def_side.id), baseline_price=base_side_price)
                for s in sides
            ]
            d_options = [
                serialize_opt(d, is_default=(def_drink is not None and d.id == def_drink.id), baseline_price=base_drink_price)
                for d in drinks
            ]
            
            return {
                "size": size,
                "burger": burger_data,
                "side": serialize_opt(def_side, True, base_side_price) if def_side else {},
                "drink": serialize_opt(def_drink, True, base_drink_price) if def_drink else {},
                "burger_price": float(burger.price.amount),
                "upgrade_price": upgrade_price,
                "meal_price": float(burger.price.amount) + upgrade_price,
                "side_options": s_options,
                "drink_options": d_options,
            }

        return {
            "success": True,
            "product_id": burger.id,
            "product_name": burger.name,
            "is_meal_available": True,
            "meals": {
                "medium": build_meal("medium", 140.0, default_side_med, default_drink),
                "large": build_meal("large", 145.0, default_side_lrg, default_drink),
            },
        }

    @app.post("/meal/decline")
    async def legacy_meal_decline():
        return {"success": True, "message": "Meal offer declined"}

    @app.post("/cart/add")
    async def legacy_cart_add_item(payload: dict):
        item_id = payload.get("item_id")
        item_name = payload.get("item_name")
        quantity = int(payload.get("quantity", 1))
        session_id = payload.get("session_id", "default-kiosk-session")
        branch_id = int(payload.get("branch_id", 1))

        item = None
        if item_id:
            item = await _cat.get_by_id(int(item_id), branch_id)
        if not item and item_name:
            items = await _cat.search_by_name(item_name, branch_id)
            if items:
                item = items[0]

        if item:
            await _cs.add_item(
                session_id=session_id,
                item_id=item.id,
                quantity=quantity,
                branch_id=branch_id,
            )
        return await legacy_get_cart()

    @app.post("/cart/add-meal")
    async def legacy_cart_add_meal(payload: dict):
        meal = payload.get("meal", {})
        qty = int(payload.get("quantity", 1))
        burger_info = meal.get("burger", {})
        side_info = meal.get("side", {})
        drink_info = meal.get("drink", {})
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

        c = await _cs.get_cart("default-kiosk-session")
        from app.domain.cart.entities import CartLine
        from app.domain.catalog.value_objects import Price
        from decimal import Decimal
        import uuid

        c.lines.append(
            CartLine(
                line_id=str(uuid.uuid4()),
                item_id=burger_info.get("id", 1),
                item_name=meal_name,
                quantity=qty,
                unit_price=Price(Decimal(str(price_val))),
                category="meal",
                food_type=burger_info.get("foodType"),
                image=burger_info.get("image"),
                line_type="meal",
                metadata={
                    "side_name": side_info.get("name", "Fries"),
                    "side_extra": side_extra,
                    "drink_name": drink_info.get("name", "Coke"),
                    "drink_extra": drink_extra,
                    "custom_patty": custom_patty,
                    "custom_toppings": meal.get("custom_toppings"),
                    "size": size,
                },
            )
        )
        await _cs._save_cart(c)
        return await legacy_get_cart()

    @app.patch("/cart/item")
    async def legacy_cart_update_item(payload: dict):
        item_index = payload.get("item_index", 0)
        action = payload.get("action", "increase")
        c = await _cs.get_cart("default-kiosk-session")
        if 0 <= item_index < len(c.lines):
            line = c.lines[item_index]
            if action == "increase":
                line.quantity += 1
            elif action == "decrease":
                line.quantity -= 1
                if line.quantity <= 0:
                    c.lines.pop(item_index)
            elif action == "delete":
                c.lines.pop(item_index)
            await _cs._save_cart(c)
        return await legacy_get_cart()

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
    async def get_checkout_recommendations(session_id: str = "default-kiosk-session", branch_id: int = 1):
        cart = await _cs.get_cart(session_id)
        session = await _session_svc.get_session(session_id)
        if not session:
            session = await _session_svc.start_session()
        recs = await _rec_engine.get_cart_recommendations(session, cart.lines, branch_id=branch_id, limit=4)
        
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

    @app.get("/recommendations/product/{item_id}")
    async def get_product_recommendations(item_id: int, branch_id: int = 1):
        prod = await _cat.get_by_id(item_id, branch_id)
        cat_raw = str(prod.category.value if hasattr(prod.category, "value") else prod.category).lower() if prod else "burger"
        cat_norm = "burger" if "burger" in cat_raw else ("drink" if "drink" in cat_raw else ("side" if "side" in cat_raw else ("dessert" if "dessert" in cat_raw else "burger")))

        # Human-Centric Complementary Priorities (Strictly exclude self-category)
        if cat_norm == "burger":
            target_sequence = ["drink", "side", "dessert"]
        elif cat_norm == "drink":
            target_sequence = ["side", "burger", "dessert"]
        elif cat_norm == "side":
            target_sequence = ["drink", "burger", "dessert"]
        else:  # dessert
            target_sequence = ["drink", "side", "burger"]

        # Fetch curated cross-sells
        cross_sells = await _cat.get_cross_sells(item_id, limit=8)
        cross_by_cat = {}
        for cs in cross_sells:
            cs_cat = str(cs.category.value if hasattr(cs.category, "value") else cs.category).lower()
            cs_norm = "burger" if "burger" in cs_cat else ("drink" if "drink" in cs_cat else ("side" if "side" in cs_cat else ("dessert" if "dessert" in cs_cat else "side")))
            # Never accept self-category as complement to self
            if cs_norm != cat_norm and cs_norm not in cross_by_cat and cs.id != item_id:
                cross_by_cat[cs_norm] = cs

        recs = []
        chosen_ids = {item_id}

        # PASS 1: Category Slot Diversity (1 item per complementary category)
        for comp_cat in target_sequence:
            if len(recs) >= 4:
                break
            if comp_cat in cross_by_cat and cross_by_cat[comp_cat].id not in chosen_ids:
                chosen = cross_by_cat[comp_cat]
                recs.append(chosen)
                chosen_ids.add(chosen.id)
            else:
                cat_items = await _cat.get_by_category(comp_cat, branch_id)
                available = [i for i in cat_items if i.id not in chosen_ids and i.is_available]
                if available:
                    recs.append(available[0])
                    chosen_ids.add(available[0].id)

        # PASS 2: Fill 4th slot from complementary categories if catalog allows
        if len(recs) < 4:
            for comp_cat in target_sequence:
                if len(recs) >= 4:
                    break
                cat_items = await _cat.get_by_category(comp_cat, branch_id)
                available = [i for i in cat_items if i.id not in chosen_ids and i.is_available]
                if available:
                    recs.append(available[0])
                    chosen_ids.add(available[0].id)

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
            "item_id": item_id,
            "recommendations": [serialize_rec(r) for r in recs],
        }

    @app.get("/proactive/opportunity")
    async def get_proactive_opportunity(
        session_id: str = "default-kiosk-session",
        current_screen: str = "home",
        branch_id: int = 1,
    ):
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

    @app.post("/proactive/feedback")
    async def record_proactive_feedback(payload: dict):
        session_id = payload.get("session_id") or "default-kiosk-session"
        action = payload.get("action", "dismissed")
        item_id = payload.get("item_id")
        opp_type = payload.get("opportunity_type", "proactive")

        from app.domain.session.memory import ContextualObservation, ObservationScope, ObservationSource
        from datetime import datetime, timedelta

        obs = ContextualObservation(
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

    @app.post("/order/complete")
    async def legacy_order_complete(payload: dict = None):
        await _cs.clear_cart("default-kiosk-session")
        import random
        return {
            "success": True,
            "order_number": random.randint(1000, 9999),
            "message": "Order completed successfully",
        }


    @app.post("/message")
    async def legacy_message(payload: dict):
        from app.api.v1.conversation import handle_message, MessageRequest
        msg = payload.get("message", "")
        sid = payload.get("session_id") or "default-kiosk-session"
        return await handle_message(MessageRequest(message=msg, session_id=sid))

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

    @app.post("/cart/add")
    async def legacy_cart_add(payload: dict):
        item_name = payload.get("item_name")
        qty = payload.get("quantity", 1)
        matches = await _cat.search_by_name(item_name, 1) if item_name else []
        if matches:
            await _cs.add_item("default-kiosk-session", matches[0].id, qty, 1)
        return await legacy_get_cart()

    @app.post("/cart/clear")
    async def legacy_cart_clear():
        await _cs.clear_cart("default-kiosk-session")
        return await legacy_get_cart()

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
