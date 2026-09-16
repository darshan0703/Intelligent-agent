"""
app/api/v1/cart.py
Cart management endpoints with full typing.
"""
from __future__ import annotations
from fastapi import APIRouter
from pydantic import BaseModel
from app.application.cart_service import CartService
from app.infrastructure.repositories.catalog_repository import SQLAlchemyCatalogRepository

router = APIRouter(prefix="/cart", tags=["cart"])
_catalog = SQLAlchemyCatalogRepository()
_cart_service = CartService(_catalog)


class AddItemRequest(BaseModel):
    item_id: int
    quantity: int = 1
    branch_id: int = 1


class AddMealRequest(BaseModel):
    size: str
    main_item_id: int
    main_item_name: str
    side_id: int
    side_name: str
    drink_id: int
    drink_name: str
    burger_price: float
    upgrade_price: float
    side_extra: float = 0.0
    drink_extra: float = 0.0
    quantity: int = 1


@router.get("/{session_id}")
async def get_cart(session_id: str):
    cart = await _cart_service.get_cart(session_id)
    return {
        "success": True,
        "cart": [
            {
                "line_id": l.line_id,
                "item_id": l.item_id,
                "name": l.item_name,
                "quantity": l.quantity,
                "unitPrice": float(l.unit_price.amount),
                "subtotal": float(l.subtotal.amount),
                "category": l.category,
                "image": l.image,
                "type": l.line_type,
            }
            for l in cart.lines
        ],
        "itemCount": cart.item_count,
        "subtotal": float(cart.subtotal.amount),
        "total": float(cart.subtotal.amount),
    }


@router.post("/{session_id}/add")
async def add_item(session_id: str, req: AddItemRequest):
    cart = await _cart_service.add_item(session_id, req.item_id, req.quantity, req.branch_id)
    return await get_cart(session_id)


@router.post("/{session_id}/add-meal")
async def add_meal(session_id: str, req: AddMealRequest):
    await _cart_service.add_meal(session_id, req.model_dump())
    return await get_cart(session_id)


@router.delete("/{session_id}/item/{line_id}")
async def remove_item(session_id: str, line_id: str):
    await _cart_service.remove_item(session_id, line_id)
    return await get_cart(session_id)


@router.post("/{session_id}/clear")
async def clear_cart(session_id: str):
    await _cart_service.clear_cart(session_id)
    return await get_cart(session_id)
