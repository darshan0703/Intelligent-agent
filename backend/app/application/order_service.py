"""
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
