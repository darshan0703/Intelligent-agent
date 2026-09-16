"""
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
