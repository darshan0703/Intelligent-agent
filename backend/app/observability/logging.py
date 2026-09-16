"""
app/observability/logging.py
Structured logging configuration for TheAtom backend.

Provides:
- configure_logging()  : call once at application startup
- get_logger()         : returns a bound structlog logger
- bind_request_context(): attach per-request fields to the context var
- clear_request_context(): clean up after each request

In production (json_format=True) logs are emitted as JSON to stdout.
In development (json_format=False) logs use rich colored console output.

NEVER use print() — all output goes through structlog.
"""

from __future__ import annotations

import logging
import sys
from contextvars import ContextVar
from typing import Any

import structlog
from structlog.types import EventDict, WrappedLogger

# ── Context variable for per-request bound fields ─────────────────────────────
# Each async request binds its own context; no shared mutable global state.
_request_context: ContextVar[dict[str, Any]] = ContextVar(
    "_request_context", default={}
)


# ── Custom processors ─────────────────────────────────────────────────────────

def _inject_request_context(
    logger: WrappedLogger, method: str, event_dict: EventDict
) -> EventDict:
    """Merge the current request context into every log event."""
    ctx = _request_context.get({})
    if ctx:
        event_dict.update(ctx)
    return event_dict


def _drop_color_message_key(
    logger: WrappedLogger, method: str, event_dict: EventDict
) -> EventDict:
    """Remove uvicorn''s ''color_message'' key to keep JSON logs clean."""
    event_dict.pop("color_message", None)
    return event_dict


# ── Public API ────────────────────────────────────────────────────────────────

def configure_logging(
    level: str = "INFO",
    json_format: bool = False,
) -> None:
    """Configure structlog and stdlib logging.

    Must be called exactly once at application startup (e.g., in lifespan).

    Args:
        level:       Logging level string ("DEBUG", "INFO", etc.).
        json_format: When True, emit JSON (production). When False, emit
                     colored human-readable output (development).
    """
    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        _inject_request_context,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        _drop_color_message_key,
    ]

    if json_format:
        # Production: JSON lines to stdout — machine-parseable
        renderer: Any = structlog.processors.JSONRenderer()
    else:
        # Development: colored, pretty output
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelName(level.upper())
        ),
        context_class=dict,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    import io
    utf8_stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
    handler = logging.StreamHandler(utf8_stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(level.upper())

    # Quieten noisy third-party loggers
    for noisy in ("httpx", "httpcore", "asyncio", "multipart"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a named structlog bound logger.

    Args:
        name: Typically __name__ of the calling module.

    Returns:
        A structlog BoundLogger that carries the module name.
    """
    return structlog.get_logger(name)


def bind_request_context(
    request_id: str,
    session_id: str | None = None,
    tenant_id: str | None = None,
) -> None:
    """Bind per-request identifiers so they appear in every log line.

    This uses a ContextVar so it is async-safe — each coroutine carries its
    own copy without leaking to other concurrent requests.

    Args:
        request_id: Unique identifier for this HTTP request (e.g., UUID).
        session_id: Customer session identifier, if available.
        tenant_id:  Tenant/brand identifier, if available.
    """
    ctx: dict[str, Any] = {"request_id": request_id}
    if session_id is not None:
        ctx["session_id"] = session_id
    if tenant_id is not None:
        ctx["tenant_id"] = tenant_id
    _request_context.set(ctx)


def clear_request_context() -> None:
    """Remove all per-request bound fields.

    Call this in a finally block or middleware teardown to prevent context
    leaking between requests when using connection pools or task re-use.
    """
    _request_context.set({})
