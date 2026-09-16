"""
app/application/conversation_service.py
Core end-to-end conversation orchestration pipeline.
Two-tier routing: Screen Intent -> Cashier Agent with structured fallback.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from app.application.cart_service import CartService
from app.application.session_service import SessionService
from app.domain.session.entities import ConversationTurn
from app.intelligence.agent.cashier_agent import CashierAgent
from app.intelligence.entity_resolution.resolver import EntityResolver
from app.intelligence.intent.screen_intent import extract_screen_intent
from app.observability.logging import get_logger
from app.ports.catalog_port import CatalogRepository
from app.ports.llm_port import LanguageModelPort
from app.prompts.registry import get_prompt_registry

logger = get_logger(__name__)


@dataclass
class ConversationResponse:
    message: str
    screen: str | None
    ui_action: str | None
    ui_action_value: str | None
    cart_summary: dict | None
    data: dict | None = None


class ConversationService:
    def __init__(
        self,
        session_service: SessionService,
        cart_service: CartService,
        catalog: CatalogRepository,
        llm: LanguageModelPort,
        agent: CashierAgent,
    ):
        self.session_service = session_service
        self.cart_service = cart_service
        self.catalog = catalog
        self.llm = llm
        self.agent = agent
        self.resolver = EntityResolver()
        self.prompts = get_prompt_registry()

    def _serialize_item(self, item) -> dict:
        is_veg = False
        if item.food_type:
            ft = str(item.food_type.value if hasattr(item.food_type, "value") else item.food_type).lower()
            is_veg = "veg" in ft and "non" not in ft

        img = item.image or ""
        if img and not img.startswith("http") and not img.startswith("/"):
            img = "/" + img
        meal_img = item.meal_image or img
        if meal_img and not meal_img.startswith("http") and not meal_img.startswith("/"):
            meal_img = "/" + meal_img

        return {
            "id": item.id,
            "name": item.name,
            "price": float(item.price.amount),
            "foodType": "veg" if is_veg else "non veg",
            "type": "veg" if is_veg else "non veg",
            "category": str(item.category.value if hasattr(item.category, "value") else item.category),
            "image": img or "https://images.unsplash.com/photo-1568901346375-23c9450c58cd?w=500&auto=format&fit=crop&q=60",
            "meal_image": meal_img or img,
            "shortDescription": item.short_description or item.name,
            "longDescription": item.long_description or item.name,
            "is_meal_available": item.is_meal_available,
            "stock": item.inventory.stock if item.inventory else 50,
        }

    async def _build_screen_data(self, category: str, branch_id: int = 1) -> dict:
        items = await self.catalog.get_by_category(category, branch_id)
        if not items:
            items = await self.catalog.get_all_available(branch_id)

        serialized = [self._serialize_item(i) for i in items]

        if category == "burger":
            veg_items = [i for i in serialized if i["foodType"] == "veg"]
            non_veg_items = [i for i in serialized if i["foodType"] != "veg"]

            def build_set(lst):
                by_price = sorted(lst, key=lambda x: x["price"], reverse=True)
                prio = lst[:2] if len(lst) >= 2 else (lst + serialized)[:2]
                prem = by_price[:2] if len(by_price) >= 2 else (by_price + serialized)[:2]
                add = [i for i in lst if i not in prio and i not in prem][:4]
                if not add:
                    add = [i for i in serialized if i not in prio and i not in prem][:4]
                return {
                    "priority": prio,
                    "premium": prem,
                    "additional": add,
                }

            both_priority = []
            if veg_items:
                both_priority.append(veg_items[0])
            if non_veg_items:
                both_priority.append(non_veg_items[0])
            if len(both_priority) < 2:
                both_priority = serialized[:2]

            both_premium = sorted(serialized, key=lambda x: x["price"], reverse=True)[:2]
            both_additional = [i for i in serialized if i not in both_priority and i not in both_premium][:4]

            return {
                "both": {
                    "priority": both_priority,
                    "premium": both_premium,
                    "additional": both_additional,
                },
                "veg": build_set(veg_items) if veg_items else build_set(serialized),
                "non_veg": build_set(non_veg_items) if non_veg_items else build_set(serialized),
            }
        else:
            by_price = sorted(serialized, key=lambda x: x["price"], reverse=True)
            return {
                "priority": serialized[:2],
                "premium": by_price[:2],
                "additional": serialized[2:6],
            }


    async def _try_fast_path(self, text: str, session: SessionState, branch_id: int) -> ConversationResponse | None:
        import re
        t = text.strip().lower()

        # 1. Back navigation (0ms)
        if re.search(r"^(go\s+)?back$|^previous(\s+screen)?$|^piche\s*jao$|^wapas\s*jao$", t):
            msg = "Going back to the previous screen."
            session.add_turn(ConversationTurn(role="assistant", content=msg, timestamp=datetime.utcnow(), metadata={}))
            await self.session_service.repo.update(session)
            return ConversationResponse(
                message=msg,
                screen="home",
                ui_action="go_back",
                ui_action_value="back",
                cart_summary=None,
            )

        # 2. Dietary Filter fast-path (0ms)
        if re.search(r"^(show\s+)?(veg|veggie|vegetarian)(\s+only)?$|^shakahari$|^sirf\s*veg$|^kuch\s*veg(\s*dikhana)?$", t):
            session.food_preference = "veg"
            target_scr = session.current_screen.name if session.current_screen else "recommended_burgers"
            if target_scr in ("home", "category_selection"):
                target_scr = "recommended_burgers"
            cat_slug = target_scr.replace("recommended_", "").rstrip("s")
            cat_slug = "burger" if "burger" in cat_slug else ("drink" if "drink" in cat_slug else ("side" if "side" in cat_slug else ("dessert" if "dessert" in cat_slug else "burger")))
            screen_data = await self._build_screen_data(cat_slug, branch_id)
            if screen_data:
                screen_data["preference"] = "veg"
            msg = "Showing our delicious 100% pure vegetarian options!"
            session.add_turn(ConversationTurn(role="assistant", content=msg, timestamp=datetime.utcnow(), metadata={}))
            await self.session_service.repo.update(session)
            return ConversationResponse(
                message=msg,
                screen=target_scr,
                ui_action="filter_veg",
                ui_action_value="veg",
                cart_summary=None,
                data=screen_data,
            )

        if re.search(r"^(show\s+)?non\s*veg(\s+only)?$|^mansahari$|^sirf\s*non\s*veg$", t):
            session.food_preference = "non_veg"
            target_scr = session.current_screen.name if session.current_screen else "recommended_burgers"
            if target_scr in ("home", "category_selection"):
                target_scr = "recommended_burgers"
            cat_slug = target_scr.replace("recommended_", "").rstrip("s")
            cat_slug = "burger" if "burger" in cat_slug else ("drink" if "drink" in cat_slug else ("side" if "side" in cat_slug else ("dessert" if "dessert" in cat_slug else "burger")))
            screen_data = await self._build_screen_data(cat_slug, branch_id)
            if screen_data:
                screen_data["preference"] = "non_veg"
            msg = "Showing our mouth-watering non-veg selections!"
            session.add_turn(ConversationTurn(role="assistant", content=msg, timestamp=datetime.utcnow(), metadata={}))
            await self.session_service.repo.update(session)
            return ConversationResponse(
                message=msg,
                screen=target_scr,
                ui_action="filter_non_veg",
                ui_action_value="non_veg",
                cart_summary=None,
                data=screen_data,
            )

        if re.search(r"^(show\s+)?(both|all)(\s+items)?$|^reset\s+filter$|^sab\s*dikhana$", t):
            session.food_preference = "both"
            target_scr = session.current_screen.name if session.current_screen else "recommended_burgers"
            cat_slug = target_scr.replace("recommended_", "").rstrip("s")
            cat_slug = "burger" if "burger" in cat_slug else ("drink" if "drink" in cat_slug else ("side" if "side" in cat_slug else ("dessert" if "dessert" in cat_slug else "burger")))
            screen_data = await self._build_screen_data(cat_slug, branch_id)
            if screen_data:
                screen_data["preference"] = "both"
            msg = "Showing all items on the menu."
            session.add_turn(ConversationTurn(role="assistant", content=msg, timestamp=datetime.utcnow(), metadata={}))
            await self.session_service.repo.update(session)
            return ConversationResponse(
                message=msg,
                screen=target_scr,
                ui_action="filter_both",
                ui_action_value="both",
                cart_summary=None,
                data=screen_data,
            )

        # 3. Direct Category fast-path (0ms)
        cat_map = {
            "burger": ["burger", "burgers", "show burgers", "open burgers", "burger menu", "burger chahiye"],
            "drink": ["drink", "drinks", "beverage", "beverages", "show drinks", "open drinks", "shakes", "cold drinks"],
            "side": ["side", "sides", "fries", "show sides", "open sides", "french fries", "snacks"],
            "dessert": ["dessert", "desserts", "sweet", "sweets", "sundae", "ice cream", "show desserts", "open desserts"],
        }
        for cat, phrases in cat_map.items():
            if t in phrases or t == f"i want {cat}" or t == f"show me {cat}" or t == f"i want a {cat}":
                session.last_category = cat
                target_scr = f"recommended_{cat}s"
                screen_data = await self._build_screen_data(cat, branch_id)
                msg = f"Opening our delicious {cat} selections for you!"
                session.add_turn(ConversationTurn(role="assistant", content=msg, timestamp=datetime.utcnow(), metadata={}))
                await self.session_service.repo.update(session)
                return ConversationResponse(
                    message=msg,
                    screen=target_scr,
                    ui_action="open_category",
                    ui_action_value=cat,
                    cart_summary=None,
                    data=screen_data,
                )

        # 4. Direct Checkout / Cart fast-path (0ms)
        if re.search(r"^(go\s+to\s+)?(checkout|cart|view\s+cart|open\s+cart|pay|review\s+and\s+pay|bill\s+banao)$", t):
            msg = "Taking you straight to review and checkout your order!"
            session.add_turn(ConversationTurn(role="assistant", content=msg, timestamp=datetime.utcnow(), metadata={}))
            await self.session_service.repo.update(session)
            return ConversationResponse(
                message=msg,
                screen="cart",
                ui_action="checkout",
                ui_action_value="checkout",
                cart_summary=None,
            )

        return None

    async def process_message(
        self,
        session_id: str,
        user_input: str,
        branch_id: int = 1,
    ) -> ConversationResponse:
        session = await self.session_service.get_session(session_id)
        if not session:
            session = await self.session_service.start_session()
            session_id = session.session_id

        session.add_turn(ConversationTurn(role="user", content=user_input, timestamp=datetime.utcnow(), metadata={}))

        # Tier 0: 0ms High-Confidence Fast-Path Heuristics for direct kiosk controls
        fast_res = await self._try_fast_path(user_input, session, branch_id)
        if fast_res:
            return fast_res

        # Tier 1: Cashier Agent (single high-performance structured call)
        agent_res = await self.agent.run(user_input=user_input, session=session, branch_id=branch_id)
        session.add_turn(ConversationTurn(role="assistant", content=agent_res.spoken_message, timestamp=datetime.utcnow(), metadata={}))
        await self.session_service.repo.update(session)

        # Synchronize voice action directly to domain cart
        if agent_res.ui_action in ("add_to_cart", "add_item") and agent_res.ui_action_value:
            try:
                matches = await self.catalog.search_by_name(agent_res.ui_action_value, branch_id)
                if matches:
                    await self.cart_service.add_item(session_id, matches[0].id, quantity=1, branch_id=branch_id)
            except Exception as exc:
                logger.warning("failed_to_add_cart_item_from_voice", error=str(exc))

        cart = await self.cart_service.get_cart(session_id)
        cart_data = {
            "item_count": cart.item_count,
            "subtotal": str(cart.subtotal.amount),
        }

        # Build screen recommendation data if navigating to category
        target_scr = agent_res.target_screen or (session.current_screen.name if session.current_screen else "home")
        screen_data = None
        if "burger" in target_scr:
            screen_data = await self._build_screen_data("burger", branch_id)
        elif "drink" in target_scr:
            screen_data = await self._build_screen_data("drink", branch_id)
        elif "side" in target_scr:
            screen_data = await self._build_screen_data("side", branch_id)
        elif "dessert" in target_scr:
            screen_data = await self._build_screen_data("dessert", branch_id)

        if screen_data and session.food_preference:
            screen_data["preference"] = session.food_preference

        return ConversationResponse(
            message=agent_res.spoken_message,
            screen=target_scr,
            ui_action=agent_res.ui_action,
            ui_action_value=agent_res.ui_action_value,
            cart_summary=cart_data,
            data=screen_data,
        )
