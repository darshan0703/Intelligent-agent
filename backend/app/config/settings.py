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
    deals_enabled: bool = Field(
        default=False,
        description="Master policy toggle for promotional discounts and micro-deals",
    )

    # ── Server / Hosting ──────────────────────────────────────────────────────
    host: str = Field(default="0.0.0.0", description="Server bind host interface")
    port: int = Field(default=8000, description="Server port")
    frontend_url: str = Field(
        default="http://localhost:5173",
        description="Frontend web application URL",
    )

    # ── HTTP / CORS ───────────────────────────────────────────────────────────
    allowed_origins: list[str] = Field(
        default=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:5174",
            "http://127.0.0.1:5174",
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:8080",
        ],
        description="Allowed CORS origin domains",
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

    # ── Supabase (Optional Managed Storage / Remote DB) ───────────────────────
    supabase_url: str = Field(
        default="",
        description="Supabase project URL (e.g. https://xyz.supabase.co)",
    )
    supabase_key: str = Field(
        default="",
        description="Supabase publishable or service role key",
    )
    supabase_db_url: str = Field(
        default="",
        description="Direct Supabase PostgreSQL connection URI",
    )

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

    # ── LLM / Gemini ──────────────────────────────────────────────────────────
    gemini_api_key: str = Field(
        default="",
        description="Google Gemini API key (loaded from GEMINI_API_KEY env)",
    )
    google_api_key: str = Field(
        default="",
        description="Google AI API key alias (loaded from GOOGLE_API_KEY env)",
    )
    gemini_default_model: str = Field(default="gemini-3.6-flash")
    gemini_fallback_model: str = Field(default="gemini-2.5-flash-lite")
    gemini_temperature: float = Field(default=0.2)
    gemini_timeout_seconds: int = Field(default=30)

    # ── Voice / Audio Engine ──────────────────────────────────────────────────
    tts_enabled: bool = Field(default=True, description="Enable Kokoro TTS pipeline")
    kokoro_lang_code: str = Field(default="a", description="Kokoro language code")
    stt_enabled: bool = Field(default=True, description="Enable Whisper STT transcription")
    whisper_model: str = Field(default="base", description="Whisper model size/name")

    # ── Multi-tenancy ─────────────────────────────────────────────────────────
    default_tenant_id: str = Field(default="default")
    default_branch_id: str = Field(default="1")

    # ── Cache & Performance Tuning ────────────────────────────────────────────
    observation_cache_ttl: int = Field(
        default=300,
        description="TTL (seconds) for cached contextual observations in Redis",
    )
    rec_cache_ttl_seconds: float = Field(
        default=45.0,
        description="TTL (seconds) for in-memory catalog cache",
    )
    rec_max_candidates: int = Field(
        default=8,
        description="Max candidates per recommendation set",
    )

    # ── Validation & Sanitization ─────────────────────────────────────────────
    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_allowed_origins(cls, v: object) -> list[str]:
        if isinstance(v, str):
            v_stripped = v.strip()
            if v_stripped.startswith("[") and v_stripped.endswith("]"):
                import json
                try:
                    return [item.strip() for item in json.loads(v_stripped) if item.strip()]
                except Exception:
                    pass
            return [part.strip() for part in v_stripped.split(",") if part.strip()]
        if isinstance(v, (list, tuple, set)):
            return [str(item).strip() for item in v if str(item).strip()]
        return [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:5174",
            "http://127.0.0.1:5174",
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ]

    @field_validator("groq_api_key")
    @classmethod
    def warn_empty_api_key(cls, v: str) -> str:
        return v

    @property
    def effective_gemini_api_key(self) -> str:
        """Returns gemini_api_key or falls back to google_api_key."""
        return self.gemini_api_key or self.google_api_key

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
