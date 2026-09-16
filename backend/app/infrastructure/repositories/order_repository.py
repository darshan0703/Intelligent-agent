"""
app/infrastructure/repositories/order_repository.py
Async SQLAlchemy Order repository with atomic inventory deduction via row locking.
"""
from __future__ import annotations
from decimal import Decimal
from sqlalchemy import select
from app.domain.catalog.value_objects import Price
from app.domain.order.entities import Order, OrderLine, OrderStatus
from app.infrastructure.db.connection import get_async_session_maker
from app.infrastructure.db.models import Inventory, OrderLineModel, OrderModel
from app.ports.order_port import OrderRepository


class SQLAlchemyOrderRepository(OrderRepository):
    def __init__(self):
        self._session_maker = get_async_session_maker()

    async def create(self, order: Order) -> Order:
        async with self._session_maker() as session:
            async with session.begin():
                orm_order = OrderModel(
                    id=order.order_id,
                    session_id=order.session_id,
                    tenant_id=order.tenant_id,
                    branch_id=order.branch_id,
                    status=order.status.value,
                    payment_method=order.payment_method,
                    total_amount=order.total.amount,
                    created_at=order.created_at,
                )
                session.add(orm_order)
                for line in order.lines:
                    orm_line = OrderLineModel(
                        order_id=order.order_id,
                        item_id=line.item_id,
                        item_name=line.item_name,
                        quantity=line.quantity,
                        unit_price=line.unit_price.amount,
                        line_type=line.line_type,
                    )
                    session.add(orm_line)
        return order

    async def get(self, order_id: str) -> Order | None:
        async with self._session_maker() as session:
            orm_order = await session.get(OrderModel, order_id)
            if not orm_order:
                return None
            lines_res = await session.execute(select(OrderLineModel).where(OrderLineModel.order_id == order_id))
            lines = [
                OrderLine(
                    item_id=l.item_id,
                    item_name=l.item_name,
                    quantity=l.quantity,
                    unit_price=Price(Decimal(str(l.unit_price))),
                    line_type=l.line_type,
                )
                for l in lines_res.scalars().all()
            ]
            return Order(
                order_id=orm_order.id,
                session_id=orm_order.session_id,
                tenant_id=orm_order.tenant_id,
                branch_id=orm_order.branch_id,
                lines=lines,
                status=OrderStatus(orm_order.status),
                payment_method=orm_order.payment_method,
                created_at=orm_order.created_at,
            )

    async def update_status(self, order_id: str, status: OrderStatus) -> None:
        async with self._session_maker() as session:
            async with session.begin():
                order = await session.get(OrderModel, order_id)
                if order:
                    order.status = status.value

    async def deduct_inventory(self, branch_id: int, item_id: int, quantity: int) -> bool:
        async with self._session_maker() as session:
            async with session.begin():
                stmt = (
                    select(Inventory)
                    .where(Inventory.branch_id == branch_id, Inventory.item_id == item_id)
                    .with_for_update()
                )
                res = await session.execute(stmt)
                inv = res.scalar_one_or_none()
                if not inv or inv.stock < quantity:
                    return False
                inv.stock -= quantity
                return True
