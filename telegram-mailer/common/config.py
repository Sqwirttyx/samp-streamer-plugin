"""Application configuration using pydantic-settings."""

from functools import lru_cache
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Bot Configuration
    bot_token: str = Field(..., description="Telegram Bot API token")
    admin_ids: List[int] = Field(default_factory=list, description="Admin Telegram IDs")

    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://mailer:password@localhost:5432/mailer",
        description="PostgreSQL connection URL",
    )
    database_echo: bool = Field(default=False, description="Echo SQL queries")

    # Redis
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL",
    )

    # Encryption
    encryption_key: str = Field(..., description="Fernet encryption key")

    # Telegram API (for Telethon)
    api_id: int = Field(..., description="Telegram API ID")
    api_hash: str = Field(..., description="Telegram API Hash")

    # File Storage
    sessions_path: str = Field(default="/storage/sessions", description="Sessions storage path")
    media_path: str = Field(default="/storage/media", description="Media storage path")

    # User Limits
    max_accounts_per_user: int = Field(default=50)
    max_proxies_per_user: int = Field(default=50)
    max_folders_per_user: int = Field(default=100)
    max_campaigns_per_user: int = Field(default=50)

    # Default Campaign Settings
    default_work_hours: int = Field(default=4)
    default_rest_minutes: int = Field(default=30)
    default_interval_min: int = Field(default=25)
    default_interval_max: int = Field(default=45)

    # 16/8 Cycle
    default_user_window_start: str = Field(default="08:00")
    user_window_hours: int = Field(default=16)
    admin_window_hours: int = Field(default=8)

    # Logging
    log_level: str = Field(default="INFO")
    log_format: str = Field(default="json")

    # Worker
    worker_health_check_interval: int = Field(default=300)
    worker_stats_flush_interval: int = Field(default=60)

    @field_validator("admin_ids", mode="before")
    @classmethod
    def parse_admin_ids(cls, v):
        if isinstance(v, str):
            return [int(x.strip()) for x in v.split(",") if x.strip()]
        return v


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
