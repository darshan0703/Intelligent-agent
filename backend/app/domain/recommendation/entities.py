"""
app/domain/recommendation/entities.py
Domain entities for recommendation ranking and contextual observations.
"""
from __future__ import annotations
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from app.domain.catalog.entities import MenuItem


class ObservationScope(str, Enum):
    SESSION = "session"
    CUSTOMER = "customer"
    GLOBAL = "global"


@dataclass
class ContextualObservation:
    id: str
    session_id: str
    subject: str
    predicate: str
    value: str
    scope: ObservationScope
    confidence: float
    source: str
    context: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: datetime | None = None

    @property
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at


@dataclass
class SignalScore:
    signal_name: str
    raw_score: float
    weight: float
    explanation: str


@dataclass
class Candidate:
    item: MenuItem
    scores: list[SignalScore] = field(default_factory=list)

    @property
    def weighted_score(self) -> float:
        return sum(s.raw_score * s.weight for s in self.scores)

    @property
    def explanation(self) -> str:
        if not self.scores:
            return "No signals"
        top = sorted(self.scores, key=lambda s: s.raw_score * s.weight, reverse=True)
        return top[0].explanation


@dataclass
class RecommendationSet:
    session_id: str
    context: str
    priority: list[Candidate] = field(default_factory=list)
    premium: list[Candidate] = field(default_factory=list)
    additional: list[Candidate] = field(default_factory=list)
    generated_at: datetime = field(default_factory=datetime.utcnow)
    signals_used: list[str] = field(default_factory=list)
