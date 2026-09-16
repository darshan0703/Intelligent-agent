import os

base_dir = r"C:\Users\Hemanth Raju N\Downloads\Working Model\TheAtom\backend\app"

files = {}

# 1. intelligence/recommendation/signals/inventory_signal.py
files["intelligence/recommendation/signals/inventory_signal.py"] = '''"""
app/intelligence/recommendation/signals/inventory_signal.py
Calculates score based on stock levels and expiry urgency.
"""
from __future__ import annotations
from app.domain.catalog.entities import MenuItem
from app.domain.recommendation.entities import SignalScore


class InventorySignal:
    name = "inventory_pressure"

    def __init__(self, weight: float = 0.25):
        self.weight = weight

    def score(self, item: MenuItem) -> SignalScore:
        if not item.inventory or item.inventory.stock <= 0:
            return SignalScore(
                signal_name=self.name,
                raw_score=0.0,
                weight=self.weight,
                explanation="Out of stock",
            )

        stock = item.inventory.stock
        stock_score = min(1.0, stock / 50.0)

        expiry_score = 0.0
        days = item.days_to_expiry
        if days is not None:
            if days <= 3:
                expiry_score = 1.0
            elif days <= 7:
                expiry_score = 0.7
            elif days <= 14:
                expiry_score = 0.4
            else:
                expiry_score = 0.1

        combined = 0.6 * stock_score + 0.4 * expiry_score
        return SignalScore(
            signal_name=self.name,
            raw_score=combined,
            weight=self.weight,
            explanation=f"Stock={stock}, DaysToExpiry={days}",
        )
'''

# 2. intelligence/recommendation/signals/popularity_signal.py
files["intelligence/recommendation/signals/popularity_signal.py"] = '''"""
app/intelligence/recommendation/signals/popularity_signal.py
Scores items according to popularity priors / sales volume.
"""
from __future__ import annotations
from app.domain.catalog.entities import MenuItem
from app.domain.recommendation.entities import SignalScore


class PopularitySignal:
    name = "popularity"

    def __init__(self, weight: float = 0.30):
        self.weight = weight
        self._default_priors = {
            "whopper": 0.95,
            "whopper jr": 0.88,
            "crispy chicken burger": 0.90,
            "classic fries": 0.92,
            "king peri peri fries": 0.85,
            "coke": 0.90,
            "cold coffee": 0.80,
            "bk fusion sundae": 0.75,
        }

    def score(self, item: MenuItem) -> SignalScore:
        item_key = item.name.lower()
        prior = self._default_priors.get(item_key, 0.50)
        return SignalScore(
            signal_name=self.name,
            raw_score=prior,
            weight=self.weight,
            explanation=f"Historical popularity prior: {prior:.2f}",
        )
'''

# 3. intelligence/recommendation/signals/session_signal.py
files["intelligence/recommendation/signals/session_signal.py"] = '''"""
app/intelligence/recommendation/signals/session_signal.py
Contextual relevance signal based on current session and cart.
"""
from __future__ import annotations
from app.domain.catalog.entities import MenuItem
from app.domain.recommendation.entities import SignalScore
from app.domain.session.entities import SessionState


class SessionSignal:
    name = "session_affinity"

    def __init__(self, weight: float = 0.25):
        self.weight = weight

    def score(self, item: MenuItem, session: SessionState, cart_item_ids: set[int]) -> SignalScore:
        raw = 0.50
        reasons = []

        if session.food_preference:
            pref = session.food_preference.lower()
            item_type = str(item.food_type).lower() if item.food_type else ""
            if pref == "veg" and "veg" in item_type and "non" not in item_type:
                raw += 0.30
                reasons.append("Matches veg preference")
            elif pref in ("non_veg", "non veg") and "non" in item_type:
                raw += 0.30
                reasons.append("Matches non-veg preference")

        if session.last_category and session.last_category.lower() == str(item.category).lower():
            raw += 0.15
            reasons.append("Matches active browsing category")

        if item.id in cart_item_ids:
            raw -= 0.35
            reasons.append("Already in cart (penalize duplicate)")

        raw = max(0.0, min(1.0, raw))
        return SignalScore(
            signal_name=self.name,
            raw_score=raw,
            weight=self.weight,
            explanation=", ".join(reasons) if reasons else "Neutral session context",
        )
'''

# 4. intelligence/recommendation/signals/crosssell_signal.py
files["intelligence/recommendation/signals/crosssell_signal.py"] = '''"""
app/intelligence/recommendation/signals/crosssell_signal.py
Scores items based on explicit pairing rules with current cart contents.
"""
from __future__ import annotations
from app.domain.catalog.entities import MenuItem
from app.domain.recommendation.entities import SignalScore


class CrossSellSignal:
    name = "cross_sell"

    def __init__(self, weight: float = 0.20):
        self.weight = weight

    def score(self, item: MenuItem, cross_sell_candidate_ids: set[int]) -> SignalScore:
        if item.id in cross_sell_candidate_ids:
            raw = 0.90
            exp = "Explicit pairing match with current cart"
        else:
            raw = 0.20
            exp = "Standard complement candidate"

        return SignalScore(
            signal_name=self.name,
            raw_score=raw,
            weight=self.weight,
            explanation=exp,
        )
'''

# 5. intelligence/recommendation/constraints.py
files["intelligence/recommendation/constraints.py"] = '''"""
app/intelligence/recommendation/constraints.py
Deterministic hard constraints filter.
Filters out items that violate stock, dietary preferences, or explicit rejections.
"""
from __future__ import annotations
from app.domain.catalog.entities import MenuItem
from app.domain.session.entities import SessionState


class ConstraintFilter:
    def filter_candidates(
        self,
        candidates: list[MenuItem],
        session: SessionState,
        rejected_item_ids: set[int] | None = None,
    ) -> list[MenuItem]:
        rejected = rejected_item_ids or set()
        valid: list[MenuItem] = []

        for item in candidates:
            if not item.is_available:
                continue
            if item.inventory and item.inventory.stock <= 0:
                continue
            if item.id in rejected:
                continue

            if session.food_preference:
                pref = session.food_preference.lower()
                food_type = str(item.food_type).lower() if item.food_type else ""
                if pref == "veg" and "non" in food_type:
                    continue
                if pref in ("non_veg", "non veg") and food_type == "veg":
                    continue

            valid.append(item)
        return valid
'''

# 6. intelligence/recommendation/diversity.py
files["intelligence/recommendation/diversity.py"] = '''"""
app/intelligence/recommendation/diversity.py
Maximal Marginal Relevance (MMR) re-ranking for recommendation diversity.
"""
from __future__ import annotations
from app.domain.recommendation.entities import Candidate


class MMRDiversity:
    def rerank(self, candidates: list[Candidate], top_k: int = 8, lambda_param: float = 0.7) -> list[Candidate]:
        if not candidates or len(candidates) <= top_k:
            return sorted(candidates, key=lambda c: c.weighted_score, reverse=True)

        selected: list[Candidate] = []
        remaining = list(candidates)

        remaining.sort(key=lambda c: c.weighted_score, reverse=True)
        selected.append(remaining.pop(0))

        while len(selected) < top_k and remaining:
            best_idx = 0
            best_mmr = -999.0

            for i, cand in enumerate(remaining):
                relevance = cand.weighted_score
                similarity = max(
                    1.0 if cand.item.category == s.item.category and cand.item.food_type == s.item.food_type else 0.2
                    for s in selected
                )
                mmr_score = lambda_param * relevance - (1.0 - lambda_param) * similarity
                if mmr_score > best_mmr:
                    best_mmr = mmr_score
                    best_idx = i

            selected.append(remaining.pop(best_idx))

        return selected
'''

# 7. intelligence/recommendation/engine.py
files["intelligence/recommendation/engine.py"] = '''"""
app/intelligence/recommendation/engine.py
Multi-objective recommendation engine with weighted signal fusion, MMR diversity, and tiering.
"""
from __future__ import annotations
from datetime import datetime
from app.domain.catalog.entities import MenuItem
from app.domain.recommendation.entities import Candidate, RecommendationSet
from app.domain.session.entities import SessionState
from app.intelligence.recommendation.constraints import ConstraintFilter
from app.intelligence.recommendation.diversity import MMRDiversity
from app.intelligence.recommendation.signals.crosssell_signal import CrossSellSignal
from app.intelligence.recommendation.signals.inventory_signal import InventorySignal
from app.intelligence.recommendation.signals.popularity_signal import PopularitySignal
from app.intelligence.recommendation.signals.session_signal import SessionSignal
from app.ports.catalog_port import CatalogRepository
from app.ports.recommendation_port import RecommendationEngine as RecommendationEnginePort


class HybridRecommendationEngine(RecommendationEnginePort):
    def __init__(self, catalog: CatalogRepository):
        self.catalog = catalog
        self.inventory_signal = InventorySignal(weight=0.25)
        self.popularity_signal = PopularitySignal(weight=0.30)
        self.session_signal = SessionSignal(weight=0.25)
        self.crosssell_signal = CrossSellSignal(weight=0.20)
        self.constraint_filter = ConstraintFilter()
        self.diversity = MMRDiversity()

    async def get_recommendations(
        self,
        session: SessionState,
        category: str | None = None,
        food_type: str | None = None,
        branch_id: int = 1,
    ) -> RecommendationSet:
        if category:
            raw_candidates = await self.catalog.get_by_category(category, branch_id)
        else:
            raw_candidates = await self.catalog.get_all_available(branch_id)

        valid_items = self.constraint_filter.filter_candidates(raw_candidates, session)
        cart_item_ids: set[int] = set()

        cross_sell_ids: set[int] = set()
        if session.last_item_id:
            pairings = await self.catalog.get_cross_sells(session.last_item_id, limit=4)
            cross_sell_ids = {p.id for p in pairings}

        scored_candidates: list[Candidate] = []
        for item in valid_items:
            scores = [
                self.inventory_signal.score(item),
                self.popularity_signal.score(item),
                self.session_signal.score(item, session, cart_item_ids),
                self.crosssell_signal.score(item, cross_sell_ids),
            ]
            scored_candidates.append(Candidate(item=item, scores=scores))

        ranked = self.diversity.rerank(scored_candidates, top_k=8)

        priority = ranked[:2]
        remaining = ranked[2:]
        premium = sorted(remaining, key=lambda c: c.item.price.amount, reverse=True)[:2]
        premium_ids = {p.item.id for p in premium}
        additional = [c for c in remaining if c.item.id not in premium_ids][:4]

        return RecommendationSet(
            session_id=session.session_id,
            context=f"category:{category}" if category else "general",
            priority=priority,
            premium=premium,
            additional=additional,
            generated_at=datetime.utcnow(),
            signals_used=["inventory_pressure", "popularity", "session_affinity", "cross_sell"],
        )
'''

# 8. intelligence/memory/memory_service.py
files["intelligence/memory/memory_service.py"] = '''"""
app/intelligence/memory/memory_service.py
Scoped contextual memory operations (rejections, affinities, preferences).
"""
from __future__ import annotations
from datetime import datetime, timedelta
from app.domain.session.memory import ContextualObservation, ObservationScope, ObservationSource
from app.ports.memory_port import MemoryStore


class MemoryService:
    def __init__(self, store: MemoryStore):
        self.store = store

    async def record_meal_rejection(self, session_id: str, item_id: int, context: dict | None = None) -> None:
        obs = ContextualObservation.meal_rejection(session_id=session_id, item_id=item_id, context=context)
        await self.store.add_observation(obs)

    async def should_offer_meal(self, session_id: str, item_id: int) -> bool:
        observations = await self.store.get_observations(
            session_id=session_id,
            subject="meal_offer",
            scope="item",
        )
        for obs in observations:
            if not obs.is_expired and obs.predicate == "rejected" and obs.value == str(item_id):
                return False
        return True

    async def record_preference(
        self,
        session_id: str,
        pref_type: str,
        value: str,
        confidence: float = 1.0,
    ) -> None:
        obs = ContextualObservation(
            session_id=session_id,
            subject="preference",
            predicate=pref_type,
            value=value,
            scope=ObservationScope.SESSION,
            context={},
            confidence=confidence,
            source=ObservationSource.EXPLICIT,
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(hours=2),
        )
        await self.store.add_observation(obs)
'''

# 9. infrastructure/repositories/memory_repository.py
files["infrastructure/repositories/memory_repository.py"] = '''"""
app/infrastructure/repositories/memory_repository.py
Database and Redis hybrid implementation of MemoryStore.
"""
from __future__ import annotations
from datetime import datetime
from sqlalchemy import and_, select
from app.domain.session.memory import ContextualObservation, ObservationScope, ObservationSource
from app.infrastructure.db.connection import get_async_session_maker
from app.infrastructure.db.models import ContextualObservationModel
from app.ports.memory_port import MemoryStore


class SQLAlchemyMemoryStore(MemoryStore):
    def __init__(self):
        self._session_maker = get_async_session_maker()

    async def add_observation(self, obs: ContextualObservation) -> None:
        async with self._session_maker() as session:
            async with session.begin():
                orm_obs = ContextualObservationModel(
                    id=obs.id,
                    session_id=obs.session_id,
                    subject=obs.subject,
                    predicate=obs.predicate,
                    value=obs.value,
                    scope=obs.scope.value,
                    context_data=obs.context,
                    confidence=obs.confidence,
                    source=obs.source.value,
                    created_at=obs.created_at,
                    expires_at=obs.expires_at,
                )
                session.add(orm_obs)

    async def get_observations(
        self,
        session_id: str,
        subject: str | None = None,
        scope: str | None = None,
    ) -> list[ContextualObservation]:
        async with self._session_maker() as session:
            stmt = select(ContextualObservationModel).where(ContextualObservationModel.session_id == session_id)
            if subject:
                stmt = stmt.where(ContextualObservationModel.subject == subject)
            if scope:
                stmt = stmt.where(ContextualObservationModel.scope == scope)

            stmt = stmt.where(
                (ContextualObservationModel.expires_at.is_(None)) | (ContextualObservationModel.expires_at > datetime.utcnow())
            )
            res = await session.execute(stmt)
            return [
                ContextualObservation(
                    id=row.id,
                    session_id=row.session_id,
                    subject=row.subject,
                    predicate=row.predicate,
                    value=row.value,
                    scope=ObservationScope(row.scope),
                    context=row.context_data,
                    confidence=row.confidence,
                    source=ObservationSource(row.source),
                    created_at=row.created_at,
                    expires_at=row.expires_at,
                )
                for row in res.scalars().all()
            ]

    async def invalidate(self, session_id: str, subject: str, predicate: str) -> None:
        async with self._session_maker() as session:
            async with session.begin():
                stmt = select(ContextualObservationModel).where(
                    ContextualObservationModel.session_id == session_id,
                    ContextualObservationModel.subject == subject,
                    ContextualObservationModel.predicate == predicate,
                )
                res = await session.execute(stmt)
                for row in res.scalars().all():
                    row.expires_at = datetime.utcnow()
'''

for rel_path, content in files.items():
    full_path = os.path.join(base_dir, rel_path)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, "w", encoding="utf-8") as f:
        f.write(content.strip() + "\n")
    print(f"Generated: {rel_path}")

print("Batch 3 completed successfully.")
