"""Application configuration using pydantic-settings."""

import re
import warnings
from urllib.parse import quote
from functools import lru_cache
from typing import Optional

from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

SCHEMA_NAME_PATTERN: re.Pattern[str] = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]{0,62}$")


class Settings(BaseSettings):
    """Application settings loaded from environment variables and Lockbox."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    APP_NAME: str = "RestoBot"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = Field(
        default="development",
        validation_alias=AliasChoices("ENVIRONMENT", "ENV"),
        pattern=r"^(development|staging|production)$",
    )

    DATABASE_URL: Optional[str] = None
    DATABASE_HOST: Optional[str] = None
    DATABASE_PORT: int = 6432
    DATABASE_NAME: str = "restobot"
    DATABASE_USER: Optional[str] = None
    DATABASE_PASSWORD: Optional[str] = None
    DATABASE_POOL_MIN: int = 2
    DATABASE_POOL_MAX: int = 10
    DATABASE_CONNECT_RETRIES: int = 5
    DATABASE_CONNECT_RETRY_DELAY: float = 1.5

    REDIS_URL: Optional[str] = None
    REDIS_HOST: Optional[str] = None
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None
    REDIS_TLS_ENABLED: bool = False
    REDIS_CART_TTL: int = 1800

    TELEGRAM_BOT_TOKEN: str = Field(
        validation_alias=AliasChoices("TELEGRAM_BOT_TOKEN", "TELEGRAM_TOKEN")
    )
    TELEGRAM_WEBHOOK_URL: Optional[str] = None
    TELEGRAM_WEBHOOK_SECRET: Optional[str] = None
    TELEGRAM_BOT_DEFAULT_TENANT_ID: Optional[str] = None

    YC_CLOUD_ID: Optional[str] = None
    YC_FOLDER_ID: Optional[str] = None
    YC_IAM_TOKEN: Optional[str] = None
    YANDEXGPT_MODEL: str = "yandexgpt-lite"
    YANDEXGPT_PRO_MODEL: str = "yandexgpt"
    YANDEXGPT_TIMEOUT: float = 5.0
    YANDEXGPT_EMBED_TIMEOUT: float = 2.0

    YOOKASSA_ENABLED: bool = False
    YOOKASSA_SHOP_ID: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("YOOKASSA_SHOP_ID", "YOKASSA_SHOP_ID"),
    )
    YOOKASSA_SECRET_KEY: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("YOOKASSA_SECRET_KEY", "YOKASSA_SECRET_KEY"),
    )
    YOOKASSA_RETURN_URL: str = "https://t.me/restobot_bot"
    YOOKASSA_TIMEOUT: float = 10.0
    YOOKASSA_WEBHOOK_SECRET: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("YOOKASSA_WEBHOOK_SECRET", "YOKASSA_WEBHOOK_SECRET"),
    )

    COMPLIANCE_CONSENT_VERSION: int = 1
    COMPLIANCE_DATA_RETENTION_DAYS: int = 1825
    COMPLIANCE_PDN_RETENTION_DAYS: int = 30

    AI_TOP_K_RETRIEVAL: int = 3
    AI_VECTOR_DIMENSION: int = 768
    AI_MIN_SIMILARITY: float = 0.65
    AI_FALLBACK_ENABLED: bool = True
    AI_CACHE_TTL: int = 3600

    JWT_SECRET: str = Field(..., min_length=32)
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_MINUTES: int = 60
    ENABLE_BOOTSTRAP_API: bool = False
    BOOTSTRAP_API_TOKEN: Optional[str] = None

    LOG_LEVEL: str = Field(default="INFO", pattern=r"^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$")
    LOG_FORMAT: str = Field(default="json", pattern=r"^(json|text)$")

    YC_OBJECT_STORAGE_BUCKET: str
    YC_OBJECT_STORAGE_ENDPOINT: str = "https://storage.yandexcloud.net"
    YC_MESSAGE_QUEUE_URL: Optional[str] = None

    @model_validator(mode="after")
    def finalize_connection_urls(self) -> "Settings":
        """Build DSNs from component parts when explicit URLs are not provided."""
        if not self.DATABASE_URL:
            if not (self.DATABASE_HOST and self.DATABASE_USER and self.DATABASE_PASSWORD):
                raise ValueError(
                    "DATABASE_URL or DATABASE_HOST/DATABASE_USER/DATABASE_PASSWORD must be set"
                )
            self.DATABASE_URL = (
                "postgresql+asyncpg://"
                f"{self.DATABASE_USER}:{quote(self.DATABASE_PASSWORD, safe='')}"
                f"@{self.DATABASE_HOST}:{self.DATABASE_PORT}/{self.DATABASE_NAME}"
            )

        if "REDIS_URL" in self.model_fields_set and self.REDIS_URL:
            warnings.warn(
                "REDIS_URL is deprecated and unsafe with special characters in passwords. "
                "Use REDIS_HOST, REDIS_PORT, REDIS_PASSWORD, REDIS_DB, REDIS_TLS_ENABLED instead.",
                DeprecationWarning,
                stacklevel=2,
            )

        if not self.REDIS_URL:
            redis_scheme = "rediss" if self.REDIS_TLS_ENABLED else "redis"
            if self.REDIS_HOST and self.REDIS_PASSWORD:
                self.REDIS_URL = (
                    f"{redis_scheme}://:{quote(self.REDIS_PASSWORD, safe='')}@{self.REDIS_HOST}:{self.REDIS_PORT}/"
                    f"{self.REDIS_DB}"
                )
            elif self.REDIS_HOST:
                self.REDIS_URL = f"{redis_scheme}://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
            else:
                self.REDIS_URL = f"redis://localhost:6379/{self.REDIS_DB}"

        if self.ENVIRONMENT == "production":
            if self.YOOKASSA_ENABLED:
                if not self.YOOKASSA_SHOP_ID:
                    raise ValueError("YOOKASSA_SHOP_ID is required when YOOKASSA_ENABLED is true")
                if not self.YOOKASSA_SECRET_KEY:
                    raise ValueError("YOOKASSA_SECRET_KEY is required when YOOKASSA_ENABLED is true")
                if not self.YOOKASSA_WEBHOOK_SECRET or len(self.YOOKASSA_WEBHOOK_SECRET) < 32:
                    raise ValueError(
                        "YOOKASSA_WEBHOOK_SECRET must be set to at least 32 characters in production"
                    )
            if self.TELEGRAM_WEBHOOK_URL and (
                not self.TELEGRAM_WEBHOOK_SECRET or len(self.TELEGRAM_WEBHOOK_SECRET) < 32
            ):
                raise ValueError(
                    "TELEGRAM_WEBHOOK_SECRET must be set to at least 32 characters in production "
                    "when TELEGRAM_WEBHOOK_URL is configured"
                )

        return self

    @property
    def ENV(self) -> str:
        """Backward-compatible alias used by older modules."""
        return self.ENVIRONMENT

    @property
    def sqlalchemy_database_url(self) -> str:
        """Always return an async SQLAlchemy URL."""
        assert self.DATABASE_URL is not None
        if self.DATABASE_URL.startswith("postgresql+asyncpg://"):
            return self.DATABASE_URL
        if self.DATABASE_URL.startswith("postgresql://"):
            return self.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
        return self.DATABASE_URL

    @property
    def asyncpg_database_url(self) -> str:
        """Return a DSN suitable for asyncpg."""
        return self.sqlalchemy_database_url.replace("postgresql+asyncpg://", "postgresql://", 1)

    @property
    def alembic_database_url(self) -> str:
        """Return a DSN suitable for Alembic synchronous migrations."""
        return self.sqlalchemy_database_url.replace("postgresql+asyncpg://", "postgresql://", 1)

    @property
    def tenant_schema_prefix(self) -> str:
        return "tenant_"

    def get_tenant_schema(self, tenant_id: str) -> str:
        """Get full schema name for tenant."""
        schema = f"{self.tenant_schema_prefix}{tenant_id}"
        if not SCHEMA_NAME_PATTERN.match(schema):
            raise ValueError(f"Invalid tenant schema derived from tenant_id: {tenant_id}")
        return schema


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()  # type: ignore[call-arg]
