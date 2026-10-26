"""
backend/perf.py
Lightweight, structured performance timing instrumentation for TheAtom kiosk.

Provides:
- High-precision monotonic timing via time.perf_counter()
- Unique interaction tracking across frontend and backend
- Thread-safe and coroutine-safe context isolation via ContextVar
- Structured log output: [PERF] interaction=<id> event=<event> duration_ms=<X> elapsed_ms=<Y> ...
"""

import os
import time
import uuid
from contextvars import ContextVar
from typing import Optional, Dict, Any

# Controlled via PERF_LOGGING environment variable (default: enabled in development)
PERF_LOGGING_ENABLED = os.getenv("PERF_LOGGING", "true").lower() in ("true", "1", "yes")


class PerfTracer:
    """
    Per-interaction performance tracer.
    Tracks elapsed time from the start of an interaction and measures individual stages.
    """

    def __init__(self, interaction_id: Optional[str] = None, initial_start: Optional[float] = None):
        self.interaction_id = interaction_id or f"perf_{uuid.uuid4().hex[:8]}"
        self.start_time = initial_start if initial_start is not None else time.perf_counter()
        self.stages: Dict[str, float] = {}

    def log(self, event: str, duration_ms: Optional[float] = None, **kwargs):
        """
        Emit a structured performance log line.
        Format: [PERF] interaction=<id> event=<event> [duration_ms=<X>] elapsed_ms=<Y> [key=val ...]
        """
        if not PERF_LOGGING_ENABLED:
            return

        elapsed_ms = (time.perf_counter() - self.start_time) * 1000.0
        parts = [
            f"[PERF] interaction={self.interaction_id}",
            f"event={event}",
        ]

        if duration_ms is not None:
            parts.append(f"duration_ms={duration_ms:.2f}")

        parts.append(f"elapsed_ms={elapsed_ms:.2f}")

        for k, v in kwargs.items():
            if v is not None:
                parts.append(f"{k}={v}")

        print(" ".join(parts), flush=True)

    def measure(self, stage_name: str, **kwargs):
        """
        Context manager to measure and log the duration of a synchronous code block.
        """
        tracer = self

        class MeasureContext:
            def __init__(self):
                self.t0 = None
                self.duration_ms = None

            def __enter__(self):
                self.t0 = time.perf_counter()
                return self

            def __exit__(self, exc_type, exc_val, exc_tb):
                t1 = time.perf_counter()
                self.duration_ms = (t1 - self.t0) * 1000.0
                tracer.stages[stage_name] = self.duration_ms
                tracer.log(stage_name, duration_ms=self.duration_ms, **kwargs)

        return MeasureContext()


# Coroutine- and thread-safe per-request tracer context
current_perf_tracer: ContextVar[Optional[PerfTracer]] = ContextVar("current_perf_tracer", default=None)


def get_current_tracer() -> Optional[PerfTracer]:
    """Retrieve the active tracer for the current execution context."""
    return current_perf_tracer.get()


def extract_or_create_tracer(request=None, headers=None, interaction_id: Optional[str] = None) -> PerfTracer:
    """
    Extract interaction_id from HTTP headers ('X-Interaction-ID') or create a new tracer.
    """
    req_id = interaction_id
    if not req_id and headers:
        req_id = headers.get("x-interaction-id") or headers.get("X-Interaction-ID")
    if not req_id and request:
        try:
            req_id = request.headers.get("x-interaction-id")
        except AttributeError:
            pass

    return PerfTracer(interaction_id=req_id)
