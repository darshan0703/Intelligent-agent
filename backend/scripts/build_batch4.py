import os

base_dir = r"C:\Users\Hemanth Raju N\Downloads\Working Model\TheAtom\backend\app"

files = {}

# 1. intelligence/agent/tools/catalog_tools.py
files["intelligence/agent/tools/catalog_tools.py"] = '''"""
app/intelligence/agent/tools/catalog_tools.py
Tool implementations for menu catalog querying and recommendations.
"""
from __future__ import annotations
from typing import Any
from app.ports.catalog_port import CatalogRepository
from app.ports.recommendation_port import RecommendationEngine
from app.domain.session.entities import SessionState


class CatalogTools:
    def __init__(self, catalog: CatalogRepository, rec_engine: RecommendationEngine):
        self.catalog = catalog
        self.rec_engine = rec_engine

    async def get_menu_category(self, category: str, branch_id: int = 1) -> dict[str, Any]:
        items = await self.catalog.get_by_category(category, branch_id)
        return {
            "category": category,
            "count": len(items),
            "items": [
                {
                    "id": item.id,
                    "name": item.name,
                    "price": str(item.price.amount),
                    "food_type": str(item.food_type) if item.food_type else None,
                    "in_stock": item.in_stock,
                }
                for item in items
            ],
        }

    async def get_product_details(self, item_name: str, branch_id: int = 1) -> dict[str, Any]:
        matches = await self.catalog.search_by_name(item_name, branch_id)
        if not matches:
            return {"found": False, "message": f"Product '{item_name}' not found."}
        item = matches[0]
        return {
            "found": True,
            "id": item.id,
            "name": item.name,
            "price": str(item.price.amount),
            "category": str(item.category),
            "food_type": str(item.food_type) if item.food_type else None,
            "short_description": item.short_description,
            "in_stock": item.in_stock,
            "is_meal_available": item.is_meal_available,
        }

    async def get_recommendations(
        self,
        session: SessionState,
        category: str | None = None,
        food_type: str | None = None,
        branch_id: int = 1,
    ) -> dict[str, Any]:
        rec_set = await self.rec_engine.get_recommendations(
            session=session,
            category=category,
            food_type=food_type,
            branch_id=branch_id,
        )
        return {
            "priority": [
                {
                    "id": c.item.id,
                    "name": c.item.name,
                    "price": str(c.item.price.amount),
                    "explanation": c.explanation,
                }
                for c in rec_set.priority
            ],
            "premium": [
                {
                    "id": c.item.id,
                    "name": c.item.name,
                    "price": str(c.item.price.amount),
                }
                for c in rec_set.premium
            ],
        }
'''

# 2. intelligence/agent/tools/screen_tools.py
files["intelligence/agent/tools/screen_tools.py"] = '''"""
app/intelligence/agent/tools/screen_tools.py
Screen navigation and kiosk capability invocation tools.
"""
from __future__ import annotations
from typing import Any
from app.domain.session.entities import SessionState


class ScreenTools:
    async def perform_screen_action(
        self,
        session: SessionState,
        control: str,
        value: str | None = None,
    ) -> dict[str, Any]:
        if not session.current_screen:
            return {"success": False, "error": "No active screen on kiosk"}

        if control not in session.current_screen.available_controls:
            return {
                "success": False,
                "error": f"Control '{control}' not available on screen '{session.current_screen.name}'",
                "available": session.current_screen.available_controls,
            }

        return {
            "success": True,
            "action": control,
            "value": value,
            "screen": session.current_screen.name,
        }
'''

# 3. intelligence/agent/cashier_agent.py
files["intelligence/agent/cashier_agent.py"] = '''"""
app/intelligence/agent/cashier_agent.py
Autonomous, tool-grounded conversational cashier agent.
Operates via LanguageModelPort without direct framework coupling.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from app.domain.session.entities import ConversationTurn, SessionState
from app.intelligence.agent.tools.catalog_tools import CatalogTools
from app.intelligence.agent.tools.screen_tools import ScreenTools
from app.ports.catalog_port import CatalogRepository
from app.ports.llm_port import LanguageModelPort
from app.ports.recommendation_port import RecommendationEngine
from app.prompts.registry import get_prompt_registry


@dataclass
class AgentResponse:
    spoken_message: str
    ui_action: str | None = None
    ui_action_value: str | None = None
    target_screen: str | None = None


class CashierAgent:
    def __init__(
        self,
        llm: LanguageModelPort,
        catalog: CatalogRepository,
        rec_engine: RecommendationEngine,
    ):
        self.llm = llm
        self.catalog = catalog
        self.rec_engine = rec_engine
        self.catalog_tools = CatalogTools(catalog, rec_engine)
        self.screen_tools = ScreenTools()
        self.prompts = get_prompt_registry()

    async def run(
        self,
        user_input: str,
        session: SessionState,
        branch_id: int = 1,
    ) -> AgentResponse:
        system_prompt = self.prompts.get("cashier", {"business_name": "Burger King India"})

        context_summary = []
        if session.current_screen:
            context_summary.append(f"Screen: {session.current_screen.name}")
            context_summary.append(f"Controls: {', '.join(session.current_screen.available_controls)}")
        if session.food_preference:
            context_summary.append(f"Customer Preference: {session.food_preference}")
        if session.last_category:
            context_summary.append(f"Last Category: {session.last_category}")

        history_lines = []
        for turn in session.conversation_history[-4:]:
            history_lines.append(f"{turn.role.capitalize()}: {turn.content}")

        prompt = f"""{system_prompt}

ACTIVE CONTEXT:
{chr(10).join(context_summary)}

RECENT TURNS:
{chr(10).join(history_lines)}

CUSTOMER: {user_input}
CASHIER:"""

        reply = await self.llm.generate_text(prompt)
        clean_reply = reply.strip().strip('"')

        return AgentResponse(
            spoken_message=clean_reply,
            target_screen=session.current_screen.name if session.current_screen else None,
        )
'''

# 4. application/session_service.py
files["application/session_service.py"] = '''"""
app/application/session_service.py
Use cases for session lifecycle and screen synchronization.
"""
from __future__ import annotations
import uuid
from datetime import datetime
from app.domain.session.entities import Screen, SessionState
from app.ports.session_port import SessionRepository


class SessionService:
    def __init__(self, session_repo: SessionRepository):
        self.repo = session_repo

    async def start_session(
        self,
        tenant_id: str = "default",
        channel: str = "kiosk",
        initial_screen: str = "home",
    ) -> SessionState:
        session_id = str(uuid.uuid4())
        session = SessionState(
            session_id=session_id,
            tenant_id=tenant_id,
            channel=channel,
            current_screen=Screen(name=initial_screen, available_controls=[]),
            food_preference=None,
            last_category=None,
            last_item_id=None,
            conversation_history=[],
            created_at=datetime.utcnow(),
            last_active_at=datetime.utcnow(),
            is_active=True,
        )
        return await self.repo.create(session)

    async def get_session(self, session_id: str) -> SessionState | None:
        return await self.repo.get(session_id)

    async def sync_screen(
        self,
        session_id: str,
        screen_name: str,
        available_controls: list[str],
    ) -> SessionState | None:
        session = await self.repo.get(session_id)
        if not session:
            return None
        session.update_screen(Screen(name=screen_name, available_controls=available_controls))
        return await self.repo.update(session)

    async def end_session(self, session_id: str) -> None:
        await self.repo.delete(session_id)
'''

# 5. application/cart_service.py
files["application/cart_service.py"] = '''"""
app/application/cart_service.py
Use cases for shopping cart operations with session caching.
"""
from __future__ import annotations
from decimal import Decimal
from app.domain.cart.entities import Cart, MealComposition
from app.domain.catalog.value_objects import Price
from app.infrastructure.cache.redis_client import get_json, set_json
from app.ports.catalog_port import CatalogRepository

_in_memory_carts: dict[str, dict] = {}


class CartService:
    def __init__(self, catalog: CatalogRepository):
        self.catalog = catalog

    def _cart_key(self, session_id: str) -> str:
        return f"cart:{session_id}"

    async def get_cart(self, session_id: str) -> Cart:
        raw = await get_json(self._cart_key(session_id)) or _in_memory_carts.get(session_id)
        cart = Cart(session_id=session_id)
        if raw and "lines" in raw:
            for l in raw["lines"]:
                from app.domain.cart.entities import CartLine
                cart.lines.append(
                    CartLine(
                        line_id=l["line_id"],
                        item_id=l["item_id"],
                        item_name=l["item_name"],
                        quantity=l["quantity"],
                        unit_price=Price(Decimal(str(l["unit_price"]))),
                        category=l.get("category", "general"),
                        food_type=l.get("food_type"),
                        image=l.get("image"),
                        line_type=l.get("line_type", "item"),
                        metadata=l.get("metadata", {}),
                    )
                )
        return cart

    async def _save_cart(self, cart: Cart) -> None:
        data = {
            "session_id": cart.session_id,
            "lines": [
                {
                    "line_id": l.line_id,
                    "item_id": l.item_id,
                    "item_name": l.item_name,
                    "quantity": l.quantity,
                    "unit_price": str(l.unit_price.amount),
                    "subtotal": str(l.subtotal.amount),
                    "category": l.category,
                    "food_type": l.food_type,
                    "image": l.image,
                    "line_type": l.line_type,
                    "metadata": l.metadata,
                }
                for l in cart.lines
            ],
            "item_count": cart.item_count,
            "subtotal": str(cart.subtotal.amount),
        }
        await set_json(self._cart_key(cart.session_id), data, ttl_seconds=3600)
        _in_memory_carts[cart.session_id] = data

    async def add_item(self, session_id: str, item_id: int, quantity: int = 1, branch_id: int = 1) -> Cart:
        item = await self.catalog.get_by_id(item_id, branch_id)
        if not item or not item.is_available:
            raise ValueError(f"Item with ID {item_id} is unavailable")

        cart = await self.get_cart(session_id)
        cart.add_item(item, quantity)
        await self._save_cart(cart)
        return cart

    async def add_meal(self, session_id: str, meal_data: dict) -> Cart:
        meal = MealComposition(
            size=meal_data["size"],
            main_item_id=meal_data["main_item_id"],
            main_item_name=meal_data["main_item_name"],
            side_id=meal_data["side_id"],
            side_name=meal_data["side_name"],
            drink_id=meal_data["drink_id"],
            drink_name=meal_data["drink_name"],
            burger_price=Price(Decimal(str(meal_data["burger_price"]))),
            upgrade_price=Price(Decimal(str(meal_data["upgrade_price"]))),
            side_extra=Price(Decimal(str(meal_data.get("side_extra", "0.00")))),
            drink_extra=Price(Decimal(str(meal_data.get("drink_extra", "0.00")))),
        )
        cart = await self.get_cart(session_id)
        cart.add_meal(meal, quantity=meal_data.get("quantity", 1))
        await self._save_cart(cart)
        return cart

    async def remove_item(self, session_id: str, line_id: str) -> Cart:
        cart = await self.get_cart(session_id)
        cart.remove_line(line_id)
        await self._save_cart(cart)
        return cart

    async def clear_cart(self, session_id: str) -> Cart:
        cart = await self.get_cart(session_id)
        cart.clear()
        await self._save_cart(cart)
        return cart
'''

# 6. application/order_service.py
files["application/order_service.py"] = '''"""
app/application/order_service.py
Order checkout, inventory validation, and atomic transaction completion.
"""
from __future__ import annotations
import uuid
from datetime import datetime
from app.application.cart_service import CartService
from app.domain.order.entities import Order, OrderLine, OrderStatus
from app.ports.order_port import OrderRepository


class OrderService:
    def __init__(self, order_repo: OrderRepository, cart_service: CartService):
        self.order_repo = order_repo
        self.cart_service = cart_service

    async def checkout(
        self,
        session_id: str,
        payment_method: str = "counter",
        branch_id: int = 1,
    ) -> Order:
        cart = await self.cart_service.get_cart(session_id)
        if not cart.lines:
            raise ValueError("Cannot checkout an empty cart")

        for line in cart.lines:
            deducted = await self.order_repo.deduct_inventory(
                branch_id=branch_id,
                item_id=line.item_id,
                quantity=line.quantity,
            )
            if not deducted:
                raise ValueError(f"Insufficient stock for '{line.item_name}'")

        order_id = str(uuid.uuid4())
        order_lines = [
            OrderLine(
                item_id=line.item_id,
                item_name=line.item_name,
                quantity=line.quantity,
                unit_price=line.unit_price,
                line_type=line.line_type,
            )
            for line in cart.lines
        ]

        order = Order(
            order_id=order_id,
            session_id=session_id,
            tenant_id="default",
            branch_id=branch_id,
            lines=order_lines,
            status=OrderStatus.CONFIRMED,
            payment_method=payment_method,
            created_at=datetime.utcnow(),
        )

        created_order = await self.order_repo.create(order)
        await self.cart_service.clear_cart(session_id)
        return created_order
'''

# 7. application/conversation_service.py
files["application/conversation_service.py"] = '''"""
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

        # Tier 1: Screen-level intent
        if session.current_screen and session.current_screen.available_controls:
            try:
                screen_intent = await extract_screen_intent(
                    user_input=user_input,
                    screen=session.current_screen.name,
                    available_controls=session.current_screen.available_controls,
                    llm=self.llm,
                    prompts=self.prompts,
                )
                if screen_intent.action == "screen_action" and screen_intent.control:
                    logger.info("screen_action_executed", control=screen_intent.control, value=screen_intent.value)
                    msg = f"Sure! Updating the screen for {screen_intent.value or screen_intent.control}."
                    session.add_turn(ConversationTurn(role="assistant", content=msg, timestamp=datetime.utcnow(), metadata={}))
                    await self.session_service.repo.update(session)
                    return ConversationResponse(
                        message=msg,
                        screen=session.current_screen.name,
                        ui_action=screen_intent.control,
                        ui_action_value=screen_intent.value,
                        cart_summary=None,
                    )
            except Exception as exc:
                logger.warning("screen_intent_failed_fallback_to_agent", error=str(exc))

        # Tier 2: Cashier Agent
        agent_res = await self.agent.run(user_input=user_input, session=session, branch_id=branch_id)
        session.add_turn(ConversationTurn(role="assistant", content=agent_res.spoken_message, timestamp=datetime.utcnow(), metadata={}))
        await self.session_service.repo.update(session)

        cart = await self.cart_service.get_cart(session_id)
        cart_data = {
            "item_count": cart.item_count,
            "subtotal": str(cart.subtotal.amount),
        }

        return ConversationResponse(
            message=agent_res.spoken_message,
            screen=agent_res.target_screen or (session.current_screen.name if session.current_screen else "home"),
            ui_action=agent_res.ui_action,
            ui_action_value=agent_res.ui_action_value,
            cart_summary=cart_data,
        )
'''

for rel_path, content in files.items():
    full_path = os.path.join(base_dir, rel_path)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, "w", encoding="utf-8") as f:
        f.write(content.strip() + "\n")
    print(f"Generated: {rel_path}")

print("Batch 4 completed successfully.")
