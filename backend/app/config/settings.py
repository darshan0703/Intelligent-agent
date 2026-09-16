"""
app/config/settings.py
Application-wide settings loaded from environment variables via pydantic-settings.
All secrets are read from environment or .env file — never hard-coded.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn, RedisDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration object for TheAtom backend.

    All values can be overridden via environment variables or a .env file.
    Environment variable names are upper-cased versions of the field names.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ───────────────────────────────────────────────────────────
    app_name: str = Field(default="TheAtom", description="Human-readable service name")
    app_version: str = Field(default="1.0.0")
    environment: Literal["development", "staging", "production"] = Field(
        default="development"
    )
    debug: bool = Field(default=False)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO"
    )
    log_json: bool = Field(
        default=False,
        description="Emit JSON logs (True in production, False for dev console)",
    )

    # ── HTTP / CORS ───────────────────────────────────────────────────────────
    allowed_origins: list[str] = Field(
        default=["http://localhost:3000", "http://localhost:8080"]
    )
    api_prefix: str = Field(default="/api/v1")

    # ── Database ──────────────────────────────────────────────────────────────
    database_url: str = Field(
        default="postgresql+asyncpg://atom:atom@localhost:5432/theatom",
        description="Async SQLAlchemy database URL (asyncpg driver)",
    )
    sync_database_url: str = Field(
        default="postgresql+psycopg2://atom:atom@localhost:5432/theatom",
        description="Sync SQLAlchemy URL for Alembic migrations",
    )
    db_pool_size: int = Field(default=10)
    db_max_overflow: int = Field(default=20)
    db_pool_pre_ping: bool = Field(default=True)
    db_echo: bool = Field(default=False, description="Log all SQL statements")

    # ── Redis ─────────────────────────────────────────────────────────────────
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL",
    )
    redis_max_connections: int = Field(default=20)

    # ── Session ───────────────────────────────────────────────────────────────
    session_ttl_seconds: int = Field(
        default=3600,
        description="How long a session lives in Redis before expiry",
    )

    # ── LLM / Groq ────────────────────────────────────────────────────────────
    groq_api_key: str = Field(default="", description="Groq API key")
    groq_default_model: str = Field(default="llama-3.3-70b-versatile")
    groq_fast_model: str = Field(default="llama-3.1-8b-instant")
    groq_temperature: float = Field(default=0.2)
    groq_max_tokens: int = Field(default=2048)
    groq_timeout_seconds: int = Field(default=30)
    llm_retry_attempts: int = Field(default=3)
    llm_retry_min_wait: float = Field(default=1.0)
    llm_retry_max_wait: float = Field(default=8.0)

    # ── Multi-tenancy ─────────────────────────────────────────────────────────
    default_tenant_id: str = Field(default="default")
    default_branch_id: str = Field(default="branch-001")

    # ── Observability cache TTL ───────────────────────────────────────────────
    observation_cache_ttl: int = Field(
        default=300,
        description="TTL (seconds) for cached contextual observations in Redis",
    )

    # ── Validation ────────────────────────────────────────────────────────────
    @field_validator("groq_api_key")
    @classmethod
    def warn_empty_api_key(cls, v: str) -> str:
        # We allow empty in dev/test; production health-check will enforce it.
        return v

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def effective_log_json(self) -> bool:
        """JSON logs always on in production regardless of explicit setting."""
        return self.log_json or self.is_production


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the singleton Settings instance (cached after first call)."""
    return Settings()
