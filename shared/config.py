# shared/config.py
"""Application configuration using pydantic-settings."""

import re
from functools import lru_cache
from typing import Optional

from pydantic import Field, PostgresDsn, RedisDsn
from pydantic_settings import BaseSettings, SettingsConfigDict

# Whitelist pattern for PostgreSQL schema names (SQL injection prevention)
SCHEMA_NAME_PATTERN: re.Pattern[str] = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]{0,62}$")


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ─── Application ─────────────────────────────────────────────────
    APP_NAME: str = "RestoBot"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = Field(default=False)
    ENV: str = Field(default="production", pattern=r"^(development|staging|production)$")

    # ─── Database ────────────────────────────────────────────────────
    DATABASE_URL: PostgresDsn
    DATABASE_POOL_MIN: int = 5
    DATABASE_POOL_MAX: int = 20

    # ─── Redis ───────────────────────────────────────────────────────
    REDIS_URL: RedisDsn = Field(default=RedisDsn("redis://localhost:6379/0"))
    REDIS_CART_TTL: int = 1800  # 30 minutes

    # ─── Telegram ────────────────────────────────────────────────────
    TELEGRAM_BOT_TOKEN: str
    TELEGRAM_WEBHOOK_URL: Optional[str] = None
    TELEGRAM_WEBHOOK_SECRET: Optional[str] = None

    # ─── Yandex Cloud / YandexGPT ────────────────────────────────────
    YC_FOLDER_ID: str
    YC_IAM_TOKEN: Optional[str] = None  # If None, use metadata service inside YC VM
    YANDEXGPT_MODEL: str = "yandexgpt-lite"
    YANDEXGPT_PRO_MODEL: str = "yandexgpt"
    YANDEXGPT_TIMEOUT: float = 5.0
    YANDEXGPT_EMBED_TIMEOUT: float = 2.0

    # ─── Payments (ЮKassa) ───────────────────────────────────────────
    YOOKASSA_SHOP_ID: str
    YOOKASSA_SECRET_KEY: str
    YOOKASSA_RETURN_URL: str = "https://t.me/restobot_bot"
    YOOKASSA_TIMEOUT: float = 10.0
    YOOKASSA_WEBHOOK_SECRET: Optional[str] = None

    # ─── Compliance ──────────────────────────────────────────────────
    COMPLIANCE_CONSENT_VERSION: int = 1
    COMPLIANCE_DATA_RETENTION_DAYS: int = 1825  # 5 years for orders
    COMPLIANCE_PDN_RETENTION_DAYS: int = 30  # 30 days after consent withdrawal

    # ─── AI / RAG ────────────────────────────────────────────────────
    AI_TOP_K_RETRIEVAL: int = 3
    AI_VECTOR_DIMENSION: int = 768
    AI_MIN_SIMILARITY: float = 0.65
    AI_FALLBACK_ENABLED: bool = True
    AI_CACHE_TTL: int = 3600  # 1 hour

    # ─── Security ────────────────────────────────────────────────────
    JWT_SECRET: str = Field(..., min_length=32)
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_MINUTES: int = 60

    # ─── Logging ─────────────────────────────────────────────────────
    LOG_LEVEL: str = Field(default="INFO", pattern=r"^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$")
    LOG_FORMAT: str = "json"  # json or text

    # ─── Yandex Cloud Services ───────────────────────────────────────
    YC_OBJECT_STORAGE_BUCKET: str
    YC_OBJECT_STORAGE_ENDPOINT: str = "https://storage.yandexcloud.net"
    YC_MESSAGE_QUEUE_URL: Optional[str] = None

    @property
    def tenant_schema_prefix(self) -> str:
        """Prefix for tenant schemas."""
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
