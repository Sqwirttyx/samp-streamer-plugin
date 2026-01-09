"""Application configuration using pydantic-settings."""

import os
from functools import lru_cache
from typing import List, Optional

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
    bot_token: str = Field(default="", description="Telegram Bot API token")
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
    encryption_key: str = Field(default="", description="Fernet encryption key")

    # Telegram API (for Telethon)
    # Support both api_id/api_hash and telegram_api_id/telegram_api_hash
    telegram_api_id: Optional[int] = Field(default=None, description="Telegram API ID")
    telegram_api_hash: Optional[str] = Field(default=None, description="Telegram API Hash")

    # File Storage
    sessions_path: str = Field(default="/app/data/sessions", description="Sessions storage path")
    media_path: str = Field(default="/app/data/media", description="Media storage path")

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
        """Parse admin IDs from comma-separated string."""
        if v is None or v == "":
            return []
        if isinstance(v, str):
            # Handle comma-separated format: "123,456,789"
            v = v.strip()
            if not v:
                return []
            # Remove brackets if present (JSON format)
            v = v.strip("[]")
            return [int(x.strip()) for x in v.split(",") if x.strip()]
        if isinstance(v, list):
            return [int(x) for x in v if x]
        return []

    @property
    def api_id(self) -> Optional[int]:
        """Alias for telegram_api_id."""
        return self.telegram_api_id

    @property
    def api_hash(self) -> Optional[str]:
        """Alias for telegram_api_hash."""
        return self.telegram_api_hash


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Only instantiate if not in migration mode
# This allows migrations to run without full config
def _should_load_settings() -> bool:
    """Check if we should load full settings."""
    # Don't auto-load during alembic migrations
    import sys
    return "alembic" not in sys.modules


# Lazy settings - only loaded when accessed
class LazySettings:
    """Lazy settings loader."""

    _instance: Optional[Settings] = None

    def __getattr__(self, name: str):
        if self._instance is None:
            self._instance = get_settings()
        return getattr(self._instance, name)


settings = LazySettings()
