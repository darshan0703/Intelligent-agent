"""
tests/integration/test_api.py
Integration tests for FastAPI endpoints and conversational decision engine.
"""
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_health_check():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/health")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "healthy"
        assert data["service"] == "TheAtom"


@pytest.mark.asyncio
async def test_menu_catalog():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/menu/burgers")
        assert res.status_code == 200
        burgers = res.json()
        assert len(burgers) > 0
        first = burgers[0]
        assert "name" in first
        assert "price" in first
        assert "stock" in first


@pytest.mark.asyncio
async def test_session_lifecycle():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post("/session/start")
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert "session_id" in data


@pytest.mark.asyncio
async def test_cart_workflow():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Clear cart
        await client.post("/cart/clear")

        # Add item
        res = await client.post("/cart/add", json={"item_name": "Whopper", "quantity": 1})
        assert res.status_code == 200
        cart = res.json()
        assert cart["itemCount"] >= 1
        assert cart["total"] > 0
