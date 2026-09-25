"""
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
            stmt = select(ContextualObservationModel).where(
                ContextualObservationModel.session_id == session_id,
                ContextualObservationModel.subject.isnot(None),
            )
            if subject:
                stmt = stmt.where(ContextualObservationModel.subject == subject)
            if scope:
                stmt = stmt.where(ContextualObservationModel.scope == scope)

            stmt = stmt.where(
                (ContextualObservationModel.expires_at.is_(None)) | (ContextualObservationModel.expires_at > datetime.utcnow())
            )
            res = await session.execute(stmt)
            observations = []
            for row in res.scalars().all():
                try:
                    c_data = row.context_data
                    if isinstance(c_data, str):
                        try:
                            import json
                            c_data = json.loads(c_data)
                        except Exception:
                            c_data = {}
                    elif not isinstance(c_data, dict):
                        c_data = {}

                    obs = ContextualObservation(
                        id=str(row.id),
                        session_id=row.session_id,
                        subject=row.subject or "",
                        predicate=row.predicate or "",
                        value=row.value or "",
                        scope=ObservationScope(row.scope) if row.scope else ObservationScope.SESSION,
                        context=c_data,
                        confidence=float(row.confidence if row.confidence is not None else 1.0),
                        source=ObservationSource(row.source) if row.source else ObservationSource.INFERRED,
                        created_at=row.created_at,
                        expires_at=row.expires_at,
                    )
                    observations.append(obs)
                except Exception:
                    pass
            return observations

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


PostgresMemoryStore = SQLAlchemyMemoryStore
