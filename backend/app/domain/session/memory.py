"""
app/domain/session/memory.py
-----------------------------
Contextual observation model for session-scoped memory.

A ``ContextualObservation`` records a single inferred or explicit fact about
a guest''s interaction within a session (e.g., "guest rejected a meal offer
for item 42 on the burger screen").

DESIGN NOTES:
- Observations are always session-scoped — there is NO global observation store.
- The ``MemoryStore`` port (see ``app/ports/memory_port.py``) is the only
  authorised persistence boundary.
- Observations expire: callers must check ``is_expired`` before using them.
- Factory class-methods make common observation patterns easy to construct
  without importing the full class signature everywhere.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class ObservationScope(str, Enum):
    """Scope at which an observation applies."""

    SESSION = "session"
    """Observation applies for the entire session lifetime."""

    ITEM = "item"
    """Observation is tied to a specific menu item ID."""

    CATEGORY = "category"
    """Observation applies to a whole category (e.g. all burgers)."""

    GLOBAL = "global"
    """Cross-session, cross-tenant signal (e.g. popularity trend).
    Only ever written by backend analytics — NOT by the conversation agent."""


class ObservationSource(str, Enum):
    """How the observation was generated."""

    EXPLICIT = "explicit"
    """Guest directly stated a preference (e.g. 'I don''t want a meal')."""

    INFERRED = "inferred"
    """The system inferred the observation from behaviour (e.g. repeated
    skipping of cross-sell offers)."""


# ---------------------------------------------------------------------------
# TTL defaults per scope (seconds)
# ---------------------------------------------------------------------------

_DEFAULT_TTL: dict[ObservationScope, int] = {
    ObservationScope.SESSION: 3600,      # 1 hour — session lifetime
    ObservationScope.ITEM: 1800,         # 30 minutes
    ObservationScope.CATEGORY: 1800,     # 30 minutes
    ObservationScope.GLOBAL: 86400,      # 24 hours
}


# ---------------------------------------------------------------------------
# ContextualObservation — the core domain object
# ---------------------------------------------------------------------------


@dataclass
class ContextualObservation:
    """A single recorded fact about a guest''s intent or preference.

    Follows a lightweight subject-predicate-value triple pattern so that
    the memory store can efficiently query for matching observations without
    schema-level awareness of every possible subject type.

    Attributes:
        id:          Unique identifier (UUID v4 string).
        session_id:  The session this observation belongs to.
        subject:     What the observation is about: ``'meal_offer'``, ``'item'``,
                     ``'category'``, ``'food_type'``, etc.
        predicate:   The relationship verb: ``'rejected'``, ``'accepted'``,
                     ``'viewed'``, ``'added_to_cart'``, ``'removed_from_cart'``.
        value:       The subject''s value — typically a string representation of
                     an ID or a category slug.
        scope:       ``ObservationScope`` enum controlling invalidation strategy.
        context:     Arbitrary dict with ambient context at observation time
                     (e.g. ``{screen: 'burger_menu', cart_size: 2}``).
        confidence:  0.0–1.0 certainty score.  Explicit observations = 1.0.
        source:      ``ObservationSource`` (EXPLICIT or INFERRED).
        created_at:  UTC timestamp when the observation was recorded.
        expires_at:  UTC timestamp after which the observation must be ignored.
    """

    id: str
    session_id: str
    subject: str
    predicate: str
    value: str
    scope: ObservationScope
    context: dict
    confidence: float
    source: ObservationSource
    created_at: datetime
    expires_at: datetime | None = None

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(
                f"ContextualObservation.confidence must be in [0.0, 1.0].  Got: {self.confidence}"
            )
        if not self.session_id:
            raise ValueError("ContextualObservation.session_id cannot be empty.")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    @property
    def is_expired(self) -> bool:
        """Return True when the observation''s TTL has passed."""
        if self.expires_at is None:
            return False
        return _utcnow() > self.expires_at

    @property
    def is_valid(self) -> bool:
        """Return True when the observation is not expired and confidence > 0."""
        return not self.is_expired and self.confidence > 0.0

    # ------------------------------------------------------------------
    # Factory methods — common observation types
    # ------------------------------------------------------------------

    @classmethod
    def _make(
        cls,
        session_id: str,
        subject: str,
        predicate: str,
        value: str,
        scope: ObservationScope,
        context: dict,
        confidence: float,
        source: ObservationSource,
        ttl_seconds: int | None = None,
    ) -> "ContextualObservation":
        now = _utcnow()
        if ttl_seconds is None:
            ttl_seconds = _DEFAULT_TTL[scope]
        return cls(
            id=str(uuid.uuid4()),
            session_id=session_id,
            subject=subject,
            predicate=predicate,
            value=value,
            scope=scope,
            context=context,
            confidence=confidence,
            source=source,
            created_at=now,
            expires_at=now + timedelta(seconds=ttl_seconds),
        )

    @classmethod
    def meal_rejection(
        cls,
        session_id: str,
        item_id: int,
        context: dict,
        confidence: float = 1.0,
    ) -> "ContextualObservation":
        """Factory: guest explicitly rejected a meal-upgrade offer for ``item_id``."""
        return cls._make(
            session_id=session_id,
            subject="meal_offer",
            predicate="rejected",
            value=str(item_id),
            scope=ObservationScope.ITEM,
            context=context,
            confidence=confidence,
            source=ObservationSource.EXPLICIT,
        )

    @classmethod
    def meal_acceptance(
        cls,
        session_id: str,
        item_id: int,
        context: dict,
    ) -> "ContextualObservation":
        """Factory: guest accepted a meal-upgrade offer for ``item_id``."""
        return cls._make(
            session_id=session_id,
            subject="meal_offer",
            predicate="accepted",
            value=str(item_id),
            scope=ObservationScope.ITEM,
            context=context,
            confidence=1.0,
            source=ObservationSource.EXPLICIT,
        )

    @classmethod
    def category_preference(
        cls,
        session_id: str,
        category: str,
        context: dict,
        confidence: float = 0.8,
    ) -> "ContextualObservation":
        """Factory: guest showed strong interest in a category."""
        return cls._make(
            session_id=session_id,
            subject="category",
            predicate="preferred",
            value=category,
            scope=ObservationScope.CATEGORY,
            context=context,
            confidence=confidence,
            source=ObservationSource.INFERRED,
        )

    @classmethod
    def food_type_preference(
        cls,
        session_id: str,
        food_type: str,
        context: dict,
        confidence: float = 0.9,
        source: ObservationSource = ObservationSource.EXPLICIT,
    ) -> "ContextualObservation":
        """Factory: guest stated or revealed a veg/non_veg preference."""
        return cls._make(
            session_id=session_id,
            subject="food_type",
            predicate="preferred",
            value=food_type,
            scope=ObservationScope.SESSION,
            context=context,
            confidence=confidence,
            source=source,
        )

    @classmethod
    def cross_sell_rejection(
        cls,
        session_id: str,
        recommended_item_id: int,
        context: dict,
    ) -> "ContextualObservation":
        """Factory: guest skipped or dismissed a cross-sell recommendation."""
        return cls._make(
            session_id=session_id,
            subject="cross_sell",
            predicate="rejected",
            value=str(recommended_item_id),
            scope=ObservationScope.ITEM,
            context=context,
            confidence=0.7,
            source=ObservationSource.INFERRED,
            ttl_seconds=900,  # 15 minutes — cross-sell suppression window
        )

    def __repr__(self) -> str:
        return (
            f"ContextualObservation(id={self.id!r}, session={self.session_id!r}, "
            f"{self.subject!r} {self.predicate!r} {self.value!r}, "
            f"scope={self.scope.value}, confidence={self.confidence:.2f})"
        )
