"""
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
