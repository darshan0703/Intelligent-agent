"""
app/domain/order/entities.py
Pure domain entities for the order bounded context.

No framework imports. Decimal for all money. UUID strings for IDs.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional


class OrderStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    PREPARING = "preparing"
    READY = "ready"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


class PaymentMethod(str, Enum):
    CASH = "cash"
    CARD = "card"
    UPI = "upi"
    WALLET = "wallet"
    NOT_SET = "not_set"


class LineType(str, Enum):
    ITEM = "item"
    MEAL = "meal"
    ADDON = "addon"
    DISCOUNT = "discount"


@dataclass
class OrderLine:
    """A single line in an order."""

    id: str
    item_id: str
    item_name: str
    quantity: int
    unit_price: Decimal
    line_type: LineType = LineType.ITEM
    order_id: Optional[str] = None

    def __post_init__(self) -> None:
        if not isinstance(self.unit_price, Decimal):
            object.__setattr__(self, "unit_price", Decimal(str(self.unit_price)))

    @property
    def line_total(self) -> Decimal:
        return self.unit_price * Decimal(self.quantity)

    @classmethod
    def create(
        cls,
        item_id: str,
        item_name: str,
        quantity: int,
        unit_price: Decimal,
        line_type: LineType = LineType.ITEM,
    ) -> "OrderLine":
        return cls(
            id=str(uuid.uuid4()),
            item_id=item_id,
            item_name=item_name,
            quantity=quantity,
            unit_price=unit_price,
            line_type=line_type,
        )


@dataclass
class Order:
    """Aggregate root for an order."""

    id: str
    session_id: str
    tenant_id: str
    branch_id: str
    lines: list[OrderLine] = field(default_factory=list)
    status: OrderStatus = OrderStatus.PENDING
    payment_method: PaymentMethod = PaymentMethod.NOT_SET
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @property
    def total_amount(self) -> Decimal:
        return sum((line.line_total for line in self.lines), Decimal("0"))

    @classmethod
    def create(
        cls,
        session_id: str,
        tenant_id: str,
        branch_id: str,
        lines: Optional[list[OrderLine]] = None,
    ) -> "Order":
        return cls(
            id=str(uuid.uuid4()),
            session_id=session_id,
            tenant_id=tenant_id,
            branch_id=branch_id,
            lines=lines or [],
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

    def add_line(self, line: OrderLine) -> None:
        line.order_id = self.id
        self.lines.append(line)
        self.updated_at = datetime.utcnow()

    def confirm(self) -> None:
        if self.status != OrderStatus.PENDING:
            raise ValueError(f"Cannot confirm order in status {self.status}")
        self.status = OrderStatus.CONFIRMED
        self.updated_at = datetime.utcnow()

    def cancel(self) -> None:
        if self.status in (OrderStatus.DELIVERED, OrderStatus.CANCELLED):
            raise ValueError(f"Cannot cancel order in status {self.status}")
        self.status = OrderStatus.CANCELLED
        self.updated_at = datetime.utcnow()
