"""
app/infrastructure/db/session_cleanup.py
Session TTL Purge Job (v4.0 Specification §1.1).

Cleans up dead anonymous sessions older than the configured TTL (30–90 days).
Prevents unbounded table growth in PostgreSQL / Redis while preserving authenticated
user histories stitched to user_id.
"""
from __future__ import annotations
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.connection import get_async_session_maker
from app.infrastructure.db.models import SessionModel
from app.observability.logging import get_logger

logger = get_logger("session_cleanup")


class SessionPurgeService:
    """Automated TTL session expiration and cleanup service."""

    DEFAULT_TTL_DAYS = 60  # 30-90 day window per v4 specification

    @classmethod
    async def purge_expired_sessions(
        cls,
        ttl_days: int = DEFAULT_TTL_DAYS,
        session: Optional[AsyncSession] = None,
    ) -> int:
        """
        Deletes anonymous guest sessions (user_id IS NULL) older than ttl_days.
        Authenticated sessions stitched to a user_id are preserved or retained.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=ttl_days)
        deleted_count = 0

        async def _execute_purge(db_session: AsyncSession) -> int:
            stmt = (
                delete(SessionModel)
                .where(SessionModel.user_id.is_(None))
                .where(SessionModel.last_seen_at < cutoff)
            )
            result = await db_session.execute(stmt)
            await db_session.commit()
            return result.rowcount or 0

        try:
            if session:
                deleted_count = await _execute_purge(session)
            else:
                maker = get_async_session_maker()
                async with maker() as db_session:
                    deleted_count = await _execute_purge(db_session)

            logger.info("expired_sessions_purged", deleted_count=deleted_count, ttl_days=ttl_days, cutoff=cutoff.isoformat())
        except Exception as exc:
            logger.warning("session_purge_failed_or_skipped", error=str(exc))

        return deleted_count

    @classmethod
    async def run_periodic_purge_worker(cls, interval_hours: int = 24, ttl_days: int = DEFAULT_TTL_DAYS):
        """Background worker loop running periodically to clean up dead sessions."""
        logger.info("session_purge_worker_started", interval_hours=interval_hours, ttl_days=ttl_days)
        while True:
            try:
                await cls.purge_expired_sessions(ttl_days=ttl_days)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("session_purge_worker_exception", error=str(exc))
            await asyncio.sleep(interval_hours * 3600)
