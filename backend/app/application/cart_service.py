"""
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

    async def add_item(
        self,
        session_id: str,
        item_id: int,
        quantity: int = 1,
        branch_id: int = 1,
        custom_price: Decimal | None = None,
        metadata: dict | None = None,
    ) -> Cart:
        if hasattr(self.catalog, "get_live_stock"):
            live_stock = await self.catalog.get_live_stock(item_id, branch_id)
            if live_stock < quantity:
                raise ValueError(f"Item with ID {item_id} is out of stock (available: {live_stock})")

        item = await self.catalog.get_by_id(item_id, branch_id)
        if not item or not item.is_available:
            raise ValueError(f"Item with ID {item_id} is unavailable")
        if item.inventory and item.inventory.stock < quantity:
            raise ValueError(f"Item with ID {item_id} is out of stock")

        cart = await self.get_cart(session_id)
        custom_p = Price(custom_price) if custom_price is not None else None
        cart.add_item(item, quantity, custom_price=custom_p, metadata=metadata)
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
