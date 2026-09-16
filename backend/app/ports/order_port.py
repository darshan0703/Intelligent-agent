"""
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
