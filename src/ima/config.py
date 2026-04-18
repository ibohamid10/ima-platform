"""Application settings and environment validation."""

from __future__ import annotations

from functools import lru_cache
from urllib.parse import urlparse

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed settings loaded from environment variables and `.env`."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    ima_env: str = Field(default="local", alias="IMA_ENV")
    postgres_user: str = Field(default="ima", alias="POSTGRES_USER")
    postgres_password: str = Field(default="ima", alias="POSTGRES_PASSWORD")
    postgres_db: str = Field(default="ima", alias="POSTGRES_DB")
    database_url: str = Field(
        default="postgresql+asyncpg://ima:ima@localhost:5432/ima",
        alias="DATABASE_URL",
    )
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    temporal_address: str = Field(default="localhost:7233", alias="TEMPORAL_ADDRESS")
    qdrant_url: str = Field(default="http://localhost:6333", alias="QDRANT_URL")
    langfuse_host: str = Field(default="http://localhost:3000", alias="LANGFUSE_HOST")
    langfuse_base_url: str | None = Field(default=None, alias="LANGFUSE_BASE_URL")
    langfuse_project_id: str | None = Field(default=None, alias="LANGFUSE_INIT_PROJECT_ID")
    langfuse_public_key: str | None = Field(default=None, alias="LANGFUSE_PUBLIC_KEY")
    langfuse_secret_key: str | None = Field(default=None, alias="LANGFUSE_SECRET_KEY")
    anthropic_api_key: str | None = Field(default=None, alias="ANTHROPIC_API_KEY")
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    instantly_api_key: str | None = Field(default=None, alias="INSTANTLY_API_KEY")
    hunter_api_key: str | None = Field(default=None, alias="HUNTER_API_KEY")
    meta_access_token: str | None = Field(default=None, alias="META_ACCESS_TOKEN")
    youtube_data_api_key: str | None = Field(default=None, alias="YOUTUBE_DATA_API_KEY")
    youtube_data_api_base_url: str = Field(
        default="https://www.googleapis.com/youtube/v3",
        alias="YOUTUBE_DATA_API_BASE_URL",
    )
    meta_graph_api_base_url: str = Field(
        default="https://graph.facebook.com/v23.0",
        alias="META_GRAPH_API_BASE_URL",
    )
    niches_config_dir: str = Field(default="config/niches", alias="NICHES_CONFIG_DIR")
    evidence_storage_backend: str = Field(default="local", alias="EVIDENCE_STORAGE_BACKEND")
    evidence_storage_root: str = Field(default="data/evidence", alias="EVIDENCE_STORAGE_ROOT")
    evidence_storage_bucket: str = Field(
        default="ima-evidence-dev", alias="EVIDENCE_STORAGE_BUCKET"
    )
    scoring_config_path: str = Field(
        default="config/scoring.default.yaml",
        alias="SCORING_CONFIG_PATH",
    )
    evidence_fetch_timeout_seconds: float = Field(
        default=15.0,
        alias="EVIDENCE_FETCH_TIMEOUT_SECONDS",
    )
    evidence_fetch_user_agent: str = Field(
        default="IMA-EvidenceBuilder/0.1 (+https://github.com/ibohamid10/ima-platform)",
        alias="EVIDENCE_FETCH_USER_AGENT",
    )
    evidence_screenshot_timeout_seconds: float = Field(
        default=20.0,
        alias="EVIDENCE_SCREENSHOT_TIMEOUT_SECONDS",
    )
    evidence_screenshot_viewport_width: int = Field(
        default=1440,
        alias="EVIDENCE_SCREENSHOT_VIEWPORT_WIDTH",
    )
    evidence_screenshot_viewport_height: int = Field(
        default=1024,
        alias="EVIDENCE_SCREENSHOT_VIEWPORT_HEIGHT",
    )
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_format: str = Field(default="dev", alias="LOG_FORMAT")
    llm_daily_budget_usd: float = Field(default=20.0, alias="LLM_DAILY_BUDGET_USD")

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        """Validate that the database URL uses the async PostgreSQL driver."""

        if not value.startswith("postgresql+asyncpg://"):
            raise ValueError("DATABASE_URL muss mit postgresql+asyncpg:// beginnen.")
        return value

    @field_validator(
        "redis_url",
        "qdrant_url",
        "langfuse_host",
        "youtube_data_api_base_url",
        "meta_graph_api_base_url",
    )
    @classmethod
    def validate_urls(cls, value: str) -> str:
        """Validate that URLs include at least a scheme and host."""

        parsed = urlparse(value)
        if not parsed.scheme or not parsed.netloc:
            raise ValueError(f"Ungueltige URL: {value}")
        return value

    @field_validator("temporal_address")
    @classmethod
    def validate_temporal_address(cls, value: str) -> str:
        """Validate Temporal host:port notation."""

        if ":" not in value:
            raise ValueError("TEMPORAL_ADDRESS muss host:port enthalten.")
        return value

    @field_validator("log_format")
    @classmethod
    def validate_log_format(cls, value: str) -> str:
        """Restrict log format to supported values."""

        if value not in {"dev", "json"}:
            raise ValueError("LOG_FORMAT muss 'dev' oder 'json' sein.")
        return value

    @field_validator("evidence_storage_backend")
    @classmethod
    def validate_evidence_storage_backend(cls, value: str) -> str:
        """Restrict evidence storage backends to supported development values."""

        if value not in {"local"}:
            raise ValueError("EVIDENCE_STORAGE_BACKEND muss aktuell 'local' sein.")
        return value

    @property
    def effective_langfuse_base_url(self) -> str:
        """Return the configured Langfuse base URL."""

        return self.langfuse_base_url or self.langfuse_host

    @property
    def langfuse_enabled(self) -> bool:
        """Return whether Langfuse tracing is configured."""

        return bool(self.langfuse_public_key and self.langfuse_secret_key)

    def require_provider_key(self, provider_name: str) -> None:
        """Ensure credentials are present when a provider is actively used."""

        if provider_name == "anthropic" and not self.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY fehlt fuer den Anthropic-Provider.")
        if provider_name == "openai" and not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY fehlt fuer den OpenAI-Provider.")
        if provider_name == "instantly" and not self.instantly_api_key:
            raise ValueError("INSTANTLY_API_KEY fehlt fuer den Instantly-Provider.")
        if provider_name == "hunter" and not self.hunter_api_key:
            raise ValueError("HUNTER_API_KEY fehlt fuer den Hunter-Provider.")
        if provider_name == "youtube_data_api" and not self.youtube_data_api_key:
            raise ValueError("YOUTUBE_DATA_API_KEY fehlt fuer den YouTube-Data-API-Provider.")
        if provider_name == "meta" and not self.meta_access_token:
            raise ValueError("META_ACCESS_TOKEN fehlt fuer den Meta-Provider.")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached settings instance."""

    return Settings()


settings = get_settings()
