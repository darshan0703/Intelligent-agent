import os

base_dir = r"C:\Users\Hemanth Raju N\Downloads\Working Model\TheAtom\backend"
app_dir = os.path.join(base_dir, "app")

files = {}

# 1. api/middleware/request_id.py
files["app/api/middleware/request_id.py"] = '''"""
app/api/middleware/request_id.py
Binds X-Request-ID and X-Response-Time-Ms to requests and structlog context.
"""
from __future__ import annotations
import time
import uuid
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from app.observability.logging import bind_request_context, clear_request_context


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        req_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        tenant_id = request.headers.get("X-Tenant-ID") or "default"
        session_id = request.headers.get("X-Session-ID")

        bind_request_context(request_id=req_id, session_id=session_id, tenant_id=tenant_id)
        start_time = time.monotonic()
        try:
            response = await call_next(request)
            duration_ms = int((time.monotonic() - start_time) * 1000)
            response.headers["X-Request-ID"] = req_id
            response.headers["X-Response-Time-Ms"] = str(duration_ms)
            return response
        finally:
            clear_request_context()
'''

# 2. api/middleware/error_handler.py
files["app/api/middleware/error_handler.py"] = '''"""
app/api/middleware/error_handler.py
RFC 7807 compliant exception handling.
"""
from __future__ import annotations
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from app.observability.logging import get_logger

logger = get_logger(__name__)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
        logger.warning("validation_error", path=request.url.path, error=str(exc))
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "type": "https://theatom.ai/errors/bad-request",
                "title": "Bad Request",
                "status": 400,
                "detail": str(exc),
                "instance": request.url.path,
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.error("internal_server_error", path=request.url.path, error=str(exc), exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "type": "https://theatom.ai/errors/internal-server-error",
                "title": "Internal Server Error",
                "status": 500,
                "detail": "An unexpected error occurred while processing the request.",
                "instance": request.url.path,
            },
        )
'''

# 3. api/v1/session.py
files["app/api/v1/session.py"] = '''"""
app/api/v1/session.py
Session lifecycle and screen synchronization endpoints.
"""
from __future__ import annotations
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.application.session_service import SessionService
from app.infrastructure.repositories.session_repository import RedisSessionRepository

router = APIRouter(prefix="/session", tags=["session"])
_session_repo = RedisSessionRepository()
_session_service = SessionService(_session_repo)


class StartSessionRequest(BaseModel):
    tenant_id: str = "default"
    channel: str = "kiosk"
    screen: str = "home"


class SyncScreenRequest(BaseModel):
    screen: str
    available_controls: list[str] = []


@router.post("/start")
async def start_session(req: StartSessionRequest | None = None):
    tenant = req.tenant_id if req else "default"
    channel = req.channel if req else "kiosk"
    initial_screen = req.screen if req else "home"

    session = await _session_service.start_session(tenant_id=tenant, channel=channel, initial_screen=initial_screen)
    return {
        "success": True,
        "session_id": session.session_id,
        "screen": session.current_screen.name if session.current_screen else "home",
        "message": "Welcome to Burger King India! How can I help you today?",
        "voice_enabled": True,
    }


@router.post("/{session_id}/screen")
async def sync_screen(session_id: str, req: SyncScreenRequest):
    session = await _session_service.sync_screen(
        session_id=session_id,
        screen_name=req.screen,
        available_controls=req.available_controls,
    )
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return {
        "success": True,
        "screen": session.current_screen.name if session.current_screen else req.screen,
        "available_controls": session.current_screen.available_controls if session.current_screen else [],
    }


@router.delete("/{session_id}")
async def end_session(session_id: str):
    await _session_service.end_session(session_id)
    return {"success": True, "message": "Session ended"}
'''

# 4. api/v1/catalog.py
files["app/api/v1/catalog.py"] = '''"""
app/api/v1/catalog.py
Menu items, category browsing, and meal upgrade options.
"""
from __future__ import annotations
from fastapi import APIRouter, HTTPException
from app.infrastructure.repositories.catalog_repository import SQLAlchemyCatalogRepository

router = APIRouter(prefix="/catalog", tags=["catalog"])
_catalog_repo = SQLAlchemyCatalogRepository()


@router.get("/menu/{category}")
async def get_category_items(category: str, branch_id: int = 1):
    items = await _catalog_repo.get_by_category(category, branch_id)
    return {
        "category": category,
        "items": [
            {
                "id": item.id,
                "name": item.name,
                "shortDescription": item.short_description,
                "longDescription": item.long_description,
                "price": float(item.price.amount),
                "foodType": str(item.food_type) if item.food_type else None,
                "servingType": str(item.serving_type) if item.serving_type else None,
                "image": item.image,
                "meal_image": item.meal_image,
                "is_meal_available": item.is_meal_available,
                "stock": item.inventory.stock if item.inventory else 0,
            }
            for item in items
        ],
    }


@router.get("/sections/{category}")
async def get_category_sections(category: str, branch_id: int = 1):
    return await _catalog_repo.get_sections(category, branch_id)


@router.get("/product/{item_id}")
async def get_product(item_id: int, branch_id: int = 1):
    item = await _catalog_repo.get_by_id(item_id, branch_id)
    if not item:
        raise HTTPException(status_code=404, detail="Product not found")
    return {
        "id": item.id,
        "name": item.name,
        "price": float(item.price.amount),
        "category": str(item.category),
        "foodType": str(item.food_type) if item.food_type else None,
        "shortDescription": item.short_description,
        "longDescription": item.long_description,
        "image": item.image,
        "meal_image": item.meal_image,
        "is_meal_available": item.is_meal_available,
        "stock": item.inventory.stock if item.inventory else 0,
    }


@router.get("/meal/{item_id}/options")
async def get_meal_options(item_id: int):
    options = await _catalog_repo.get_meal_options(item_id)
    if not options:
        return {"success": False, "is_meal_available": False, "message": "Meal options not available"}
    return {"success": True, **options}
'''

# 5. api/v1/cart.py
files["app/api/v1/cart.py"] = '''"""
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
'''

# 6. api/v1/order.py
files["app/api/v1/order.py"] = '''"""
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
'''

# 7. api/v1/conversation.py
files["app/api/v1/conversation.py"] = '''"""
app/api/v1/conversation.py
Conversational agent message processing endpoint.
"""
from __future__ import annotations
from fastapi import APIRouter
from pydantic import BaseModel
from app.application.cart_service import CartService
from app.application.conversation_service import ConversationService
from app.application.session_service import SessionService
from app.infrastructure.llm.groq_adapter import GroqAdapter
from app.infrastructure.repositories.catalog_repository import SQLAlchemyCatalogRepository
from app.infrastructure.repositories.session_repository import RedisSessionRepository
from app.intelligence.agent.cashier_agent import CashierAgent
from app.intelligence.recommendation.engine import HybridRecommendationEngine

router = APIRouter(prefix="", tags=["conversation"])

# Instantiate singletons for dependency wiring
_catalog = SQLAlchemyCatalogRepository()
_session_repo = RedisSessionRepository()
_session_service = SessionService(_session_repo)
_cart_service = CartService(_catalog)
_llm = GroqAdapter()
_rec_engine = HybridRecommendationEngine(_catalog)
_agent = CashierAgent(_llm, _catalog, _rec_engine)

_conversation_service = ConversationService(
    session_service=_session_service,
    cart_service=_cart_service,
    catalog=_catalog,
    llm=_llm,
    agent=_agent,
)


class MessageRequest(BaseModel):
    message: str
    session_id: str | None = None
    branch_id: int = 1


@router.post("/message")
async def handle_message(req: MessageRequest):
    sid = req.session_id or "default-kiosk-session"
    res = await _conversation_service.process_message(
        session_id=sid,
        user_input=req.message,
        branch_id=req.branch_id,
    )
    return {
        "message": res.message,
        "screen": res.screen,
        "ui_action": res.ui_action,
        "ui_action_value": res.ui_action_value,
        "cart": res.cart_summary,
    }
'''

# 8. api/v1/voice.py
files["app/api/v1/voice.py"] = '''"""
app/api/v1/voice.py
Voice endpoints (TTS and STT) with configurable local engine or fallback.
"""
from __future__ import annotations
from fastapi import APIRouter
from pydantic import BaseModel
from app.observability.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="", tags=["voice"])


class TTSRequest(BaseModel):
    text: str


@router.post("/tts")
async def tts(req: TTSRequest):
    # Returns audio synthesis instruction for client or audio bytes
    return {"success": True, "message": "TTS ready", "text": req.text}
'''

# 9. api/v1/router.py
files["app/api/v1/router.py"] = '''"""
app/api/v1/router.py
Main v1 router aggregator.
"""
from __future__ import annotations
from fastapi import APIRouter
from app.api.v1.cart import router as cart_router
from app.api.v1.catalog import router as catalog_router
from app.api.v1.conversation import router as conversation_router
from app.api.v1.order import router as order_router
from app.api.v1.session import router as session_router
from app.api.v1.voice import router as voice_router

api_v1_router = APIRouter()

api_v1_router.include_router(session_router)
api_v1_router.include_router(catalog_router)
api_v1_router.include_router(cart_router)
api_v1_router.include_router(order_router)
api_v1_router.include_router(conversation_router)
api_v1_router.include_router(voice_router)
'''

# 10. main.py
files["app/main.py"] = '''"""
app/main.py
Application Entry Point and FastAPI Factory for TheAtom Commercial Intelligence Engine.
"""
from __future__ import annotations
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.middleware.error_handler import register_exception_handlers
from app.api.middleware.request_id import RequestContextMiddleware
from app.api.v1.router import api_v1_router
from app.config.settings import get_settings
from app.infrastructure.cache.redis_client import close_redis_client, get_redis_client
from app.infrastructure.db.connection import close_db_engine
from app.observability.logging import configure_logging, get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(level=settings.log_level, json_format=settings.effective_log_json)
    logger.info("theatom_starting_up", version=settings.app_version, env=settings.environment)

    # Initialize warm connections
    await get_redis_client()

    yield

    logger.info("theatom_shutting_down")
    await close_redis_client()
    await close_db_engine()


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="TheAtom — Universal Commercial Intelligence & Decision Engine",
        lifespan=lifespan,
    )

    # 1. Error handlers
    register_exception_handlers(app)

    # 2. Middlewares (outermost executed first)
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 3. Mount versioned API routes
    app.include_router(api_v1_router, prefix=settings.api_prefix)

    # 4. Backward-compatible / legacy endpoints for kiosk frontend compatibility
    # Kiosk frontend hits /menu/burgers, /cart, etc. directly
    from app.infrastructure.repositories.catalog_repository import SQLAlchemyCatalogRepository
    from app.infrastructure.repositories.order_repository import SQLAlchemyOrderRepository
    from app.application.cart_service import CartService

    _cat = SQLAlchemyCatalogRepository()
    _ord = SQLAlchemyOrderRepository()
    _cs = CartService(_cat)

    @app.get("/menu/burgers")
    async def legacy_burgers():
        items = await _cat.get_by_category("burger", 1)
        return [
            {
                "id": i.id, "name": i.name, "price": float(i.price.amount),
                "foodType": str(i.food_type) if i.food_type else None,
                "image": i.image, "meal_image": i.meal_image,
                "is_meal_available": i.is_meal_available,
                "stock": i.inventory.stock if i.inventory else 0,
            }
            for i in items
        ]

    @app.get("/menu/drinks")
    async def legacy_drinks():
        items = await _cat.get_by_category("drink", 1)
        return [
            {
                "id": i.id, "name": i.name, "price": float(i.price.amount),
                "type": str(i.serving_type) if i.serving_type else None,
                "image": i.image, "stock": i.inventory.stock if i.inventory else 0,
            }
            for i in items
        ]

    @app.get("/menu/sides")
    async def legacy_sides():
        items = await _cat.get_by_category("side", 1)
        return [
            {
                "id": i.id, "name": i.name, "price": float(i.price.amount),
                "image": i.image, "stock": i.inventory.stock if i.inventory else 0,
            }
            for i in items
        ]

    @app.get("/menu/desserts")
    async def legacy_desserts():
        items = await _cat.get_by_category("dessert", 1)
        return [
            {
                "id": i.id, "name": i.name, "price": float(i.price.amount),
                "image": i.image, "stock": i.inventory.stock if i.inventory else 0,
            }
            for i in items
        ]

    @app.get("/cart")
    async def legacy_get_cart():
        c = await _cs.get_cart("default-kiosk-session")
        return {
            "success": True,
            "cart": [
                {
                    "line_id": l.line_id, "item_id": l.item_id, "name": l.item_name,
                    "quantity": l.quantity, "unitPrice": float(l.unit_price.amount),
                    "subtotal": float(l.subtotal.amount), "image": l.image,
                }
                for l in c.lines
            ],
            "itemCount": c.item_count,
            "subtotal": float(c.subtotal.amount),
            "total": float(c.subtotal.amount),
        }

    @app.post("/message")
    async def legacy_message(payload: dict):
        from app.api.v1.conversation import handle_message, MessageRequest
        msg = payload.get("message", "")
        sid = payload.get("session_id") or "default-kiosk-session"
        return await handle_message(MessageRequest(message=msg, session_id=sid))

    @app.get("/health")
    async def health():
        return {"status": "healthy", "service": settings.app_name, "version": settings.app_version}

    return app


app = create_app()
'''

for rel_path, content in files.items():
    full_path = os.path.join(base_dir, rel_path)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, "w", encoding="utf-8") as f:
        f.write(content.strip() + "\n")
    print(f"Generated: {rel_path}")

print("Batch 5 completed successfully.")
