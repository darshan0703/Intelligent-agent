"""
app/ports/event_port.py
Protocol for telemetry and event publishing.
"""
from __future__ import annotations
from typing import Protocol, Any, runtime_checkable

@runtime_checkable
class EventPublisher(Protocol):
    async def publish(self, event_type: str, payload: dict[str, Any]) -> None:
        ...
