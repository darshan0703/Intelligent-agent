"""
app/api/v1/order.py
Order checkout and completion endpoint.
"""
from __future__ import annotations
from fastapi import APIRouter
from pydantic import BaseModel
from app.application.cart_service import CartService
from app.application.order_service import OrderService
from app.infrastructure.repositories.catalog_repository import SQLAlchemyCatalogRepository
from app.infrastructure.repositories.order_repository import SQLAlchemyOrderRepository

router = APIRouter(prefix="/order", tags=["order"])
_order_repo = SQLAlchemyOrderRepository()
_catalog_repo = SQLAlchemyCatalogRepository()
_cart_service = CartService(_catalog_repo)
_order_service = OrderService(_order_repo, _cart_service)


class CheckoutRequest(BaseModel):
    payment_method: str = "counter"
    branch_id: int = 1


@router.post("/{session_id}/complete")
async def complete_order(session_id: str, req: CheckoutRequest | None = None):
    payment = req.payment_method if req else "counter"
    branch = req.branch_id if req else 1
    order = await _order_service.checkout(session_id=session_id, payment_method=payment, branch_id=branch)
    return {
        "success": True,
        "order_id": order.order_id,
        "status": order.status.value,
        "item_count": order.item_count,
        "total": float(order.total.amount),
        "payment_method": order.payment_method,
        "message": f"Your order #{order.order_id[:8]} has been placed successfully!",
    }
