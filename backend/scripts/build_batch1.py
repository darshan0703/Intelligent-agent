import os
import sys

base_dir = r"C:\Users\Hemanth Raju N\Downloads\Working Model\TheAtom\backend\app"

files = {}

# 1. domain/cart/entities.py
files["domain/cart/entities.py"] = '''"""
app/domain/cart/entities.py
Pure domain entities for cart operations.
Pure Python — zero framework imports. All money operations use Decimal.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from decimal import Decimal
import uuid
from app.domain.catalog.value_objects import Price
from app.domain.catalog.entities import MenuItem


@dataclass
class CartLine:
    line_id: str
    item_id: int
    item_name: str
    quantity: int
    unit_price: Price
    category: str
    food_type: str | None = None
    image: str | None = None
    line_type: str = "item"  # 'item' | 'meal'
    metadata: dict = field(default_factory=dict)

    @property
    def subtotal(self) -> Price:
        return Price(self.unit_price.amount * Decimal(self.quantity))


@dataclass
class MealComposition:
    size: str  # 'medium' | 'large'
    main_item_id: int
    main_item_name: str
    side_id: int
    side_name: str
    drink_id: int
    drink_name: str
    burger_price: Price
    upgrade_price: Price
    side_extra: Price = field(default_factory=lambda: Price(Decimal("0.00")))
    drink_extra: Price = field(default_factory=lambda: Price(Decimal("0.00")))

    @property
    def total_price(self) -> Price:
        return Price(
            self.burger_price.amount
            + self.upgrade_price.amount
            + self.side_extra.amount
            + self.drink_extra.amount
        )


@dataclass
class Cart:
    session_id: str
    lines: list[CartLine] = field(default_factory=list)

    @property
    def item_count(self) -> int:
        return sum(line.quantity for line in self.lines)

    @property
    def subtotal(self) -> Price:
        total = Decimal("0.00")
        for line in self.lines:
            total += line.subtotal.amount
        return Price(total)

    def find_line(self, item_id: int, line_type: str = "item") -> CartLine | None:
        for line in self.lines:
            if line.item_id == item_id and line.line_type == line_type:
                return line
        return None

    def add_item(self, item: MenuItem, quantity: int = 1) -> CartLine:
        existing = self.find_line(item.id, "item")
        if existing:
            existing.quantity += quantity
            return existing
        new_line = CartLine(
            line_id=str(uuid.uuid4()),
            item_id=item.id,
            item_name=item.name,
            quantity=quantity,
            unit_price=item.price,
            category=str(item.category),
            food_type=str(item.food_type) if item.food_type else None,
            image=item.image,
            line_type="item",
        )
        self.lines.append(new_line)
        return new_line

    def add_meal(self, meal: MealComposition, quantity: int = 1) -> CartLine:
        meal_name = f"{meal.main_item_name} ({meal.size.capitalize()} Meal)"
        new_line = CartLine(
            line_id=str(uuid.uuid4()),
            item_id=meal.main_item_id,
            item_name=meal_name,
            quantity=quantity,
            unit_price=meal.total_price,
            category="meal",
            line_type="meal",
            metadata={
                "size": meal.size,
                "side_id": meal.side_id,
                "side_name": meal.side_name,
                "drink_id": meal.drink_id,
                "drink_name": meal.drink_name,
            },
        )
        self.lines.append(new_line)
        return new_line

    def remove_item(self, item_id: int, quantity: int = 1) -> bool:
        line = self.find_line(item_id)
        if not line:
            return False
        if line.quantity > quantity:
            line.quantity -= quantity
        else:
            self.lines.remove(line)
        return True

    def remove_line(self, line_id: str) -> bool:
        for i, line in enumerate(self.lines):
            if line.line_id == line_id:
                self.lines.pop(i)
                return True
        return False

    def clear(self) -> None:
        self.lines.clear()
'''

# 2. ports/
files["ports/llm_port.py"] = '''"""
app/ports/llm_port.py
Abstract protocol for Language Model providers.
Domain and application layers depend ONLY on this protocol.
"""
from __future__ import annotations
from typing import Protocol, TypeVar, Any, runtime_checkable
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

@runtime_checkable
class LanguageModelPort(Protocol):
    async def structured_complete(self, prompt: str, output_schema: type[T], **kwargs: Any) -> T:
        """Extract structured data from LLM with strict schema enforcement."""
        ...

    async def generate_text(self, prompt: str, **kwargs: Any) -> str:
        """Generate natural language response."""
        ...

    async def complete_with_tools(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
        """Tool-calling completion for autonomous cashier agent."""
        ...
'''

files["ports/embedding_port.py"] = '''"""
app/ports/embedding_port.py
Abstract protocol for Vector Embedding providers.
"""
from __future__ import annotations
from typing import Protocol, runtime_checkable

@runtime_checkable
class EmbeddingPort(Protocol):
    async def embed_text(self, text: str) -> list[float]:
        ...

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        ...

    @property
    def dimensions(self) -> int:
        ...
'''

files["ports/catalog_port.py"] = '''"""
app/ports/catalog_port.py
Repository protocol for accessing menu catalog and inventory data.
"""
from __future__ import annotations
from typing import Protocol, runtime_checkable
from app.domain.catalog.entities import MenuItem

@runtime_checkable
class CatalogRepository(Protocol):
    async def get_by_category(self, category: str, branch_id: int) -> list[MenuItem]:
        ...

    async def get_all_available(self, branch_id: int) -> list[MenuItem]:
        ...

    async def get_by_id(self, item_id: int, branch_id: int) -> MenuItem | None:
        ...

    async def search_by_name(self, name: str, branch_id: int) -> list[MenuItem]:
        ...

    async def get_cross_sells(self, item_id: int, limit: int = 4) -> list[MenuItem]:
        ...

    async def get_meal_options(self, item_id: int) -> dict | None:
        ...

    async def get_sections(self, category: str, branch_id: int) -> list[dict]:
        ...
'''

files["ports/session_port.py"] = '''"""
app/ports/session_port.py
Repository protocol for session state management.
"""
from __future__ import annotations
from typing import Protocol, runtime_checkable
from app.domain.session.entities import SessionState

@runtime_checkable
class SessionRepository(Protocol):
    async def create(self, session: SessionState) -> SessionState:
        ...

    async def get(self, session_id: str) -> SessionState | None:
        ...

    async def update(self, session: SessionState) -> SessionState:
        ...

    async def delete(self, session_id: str) -> None:
        ...
'''

files["ports/memory_port.py"] = '''"""
app/ports/memory_port.py
Repository protocol for scoped contextual observations.
"""
from __future__ import annotations
from typing import Protocol, runtime_checkable
from app.domain.session.memory import ContextualObservation

@runtime_checkable
class MemoryStore(Protocol):
    async def add_observation(self, obs: ContextualObservation) -> None:
        ...

    async def get_observations(
        self,
        session_id: str,
        subject: str | None = None,
        scope: str | None = None,
    ) -> list[ContextualObservation]:
        ...

    async def invalidate(self, session_id: str, subject: str, predicate: str) -> None:
        ...
'''

files["ports/order_port.py"] = '''"""
app/ports/order_port.py
Repository protocol for orders and inventory transactions.
"""
from __future__ import annotations
from typing import Protocol, runtime_checkable
from app.domain.order.entities import Order, OrderStatus

@runtime_checkable
class OrderRepository(Protocol):
    async def create(self, order: Order) -> Order:
        ...

    async def get(self, order_id: str) -> Order | None:
        ...

    async def update_status(self, order_id: str, status: OrderStatus) -> None:
        ...

    async def deduct_inventory(self, branch_id: int, item_id: int, quantity: int) -> bool:
        ...
'''

files["ports/recommendation_port.py"] = '''"""
app/ports/recommendation_port.py
Protocol for recommendation engine.
"""
from __future__ import annotations
from typing import Protocol, runtime_checkable
from app.domain.session.entities import SessionState
from app.domain.recommendation.entities import RecommendationSet

@runtime_checkable
class RecommendationEngine(Protocol):
    async def get_recommendations(
        self,
        session: SessionState,
        category: str | None,
        food_type: str | None,
        branch_id: int,
    ) -> RecommendationSet:
        ...
'''

files["ports/event_port.py"] = '''"""
app/ports/event_port.py
Protocol for telemetry and event publishing.
"""
from __future__ import annotations
from typing import Protocol, Any, runtime_checkable

@runtime_checkable
class EventPublisher(Protocol):
    async def publish(self, event_type: str, payload: dict[str, Any]) -> None:
        ...
'''

for rel_path, content in files.items():
    full_path = os.path.join(base_dir, rel_path)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, "w", encoding="utf-8") as f:
        f.write(content.strip() + "\n")
    print(f"Generated: {rel_path}")

print("Batch 1 completed successfully.")
