"""Redis caching layer."""

import json
from typing import Any, Optional
from uuid import UUID

from redis.asyncio import Redis

from common.constants import (
    CACHE_TTL_ACCOUNT_HEALTH,
    CACHE_TTL_FOLDER_CHATS,
    CACHE_TTL_USER_SETTINGS,
    REDIS_PREFIX_CACHE,
)
from common.logger import get_logger

logger = get_logger(__name__)


class CacheManager:
    """
    Manager for Redis-based caching.

    Provides typed caching for various application data.
    """

    def __init__(self, redis: Redis):
        """
        Initialize cache manager.

        Args:
            redis: Redis client instance
        """
        self.redis = redis

    def _key(self, *parts: str) -> str:
        """Build cache key from parts."""
        return f"{REDIS_PREFIX_CACHE}:{':'.join(parts)}"

    # Generic operations
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
    ) -> None:
        """
        Set cache value.

        Args:
            key: Cache key
            value: Value to cache (will be JSON serialized)
            ttl: Time to live in seconds
        """
        serialized = json.dumps(value, default=str)
        if ttl:
            await self.redis.setex(key, ttl, serialized)
        else:
            await self.redis.set(key, serialized)

    async def get(self, key: str) -> Optional[Any]:
        """
        Get cached value.

        Args:
            key: Cache key

        Returns:
            Cached value or None
        """
        data = await self.redis.get(key)
        if data:
            return json.loads(data)
        return None

    async def delete(self, key: str) -> bool:
        """
        Delete cached value.

        Args:
            key: Cache key

        Returns:
            True if deleted
        """
        result = await self.redis.delete(key)
        return result > 0

    async def exists(self, key: str) -> bool:
        """
        Check if key exists.

        Args:
            key: Cache key

        Returns:
            True if exists
        """
        return await self.redis.exists(key) > 0

    async def ttl(self, key: str) -> int:
        """
        Get remaining TTL for key.

        Args:
            key: Cache key

        Returns:
            TTL in seconds (-1 if no TTL, -2 if not exists)
        """
        return await self.redis.ttl(key)

    # Folder chats caching
    async def get_folder_chats(self, folder_id: UUID) -> Optional[list[int]]:
        """
        Get cached folder chat IDs.

        Args:
            folder_id: Folder UUID

        Returns:
            List of chat IDs or None
        """
        key = self._key("folder", str(folder_id), "chats")
        return await self.get(key)

    async def set_folder_chats(
        self,
        folder_id: UUID,
        chat_ids: list[int],
        ttl: int = CACHE_TTL_FOLDER_CHATS,
    ) -> None:
        """
        Cache folder chat IDs.

        Args:
            folder_id: Folder UUID
            chat_ids: List of chat IDs
            ttl: Cache TTL in seconds
        """
        key = self._key("folder", str(folder_id), "chats")
        await self.set(key, chat_ids, ttl)

    async def invalidate_folder_chats(self, folder_id: UUID) -> bool:
        """
        Invalidate folder chats cache.

        Args:
            folder_id: Folder UUID

        Returns:
            True if invalidated
        """
        key = self._key("folder", str(folder_id), "chats")
        return await self.delete(key)

    # Account health caching
    async def get_account_health(self, account_id: UUID) -> Optional[dict]:
        """
        Get cached account health data.

        Args:
            account_id: Account UUID

        Returns:
            Health data or None
        """
        key = self._key("account", str(account_id), "health")
        return await self.get(key)

    async def set_account_health(
        self,
        account_id: UUID,
        health_data: dict,
        ttl: int = CACHE_TTL_ACCOUNT_HEALTH,
    ) -> None:
        """
        Cache account health data.

        Args:
            account_id: Account UUID
            health_data: Health data dictionary
            ttl: Cache TTL in seconds
        """
        key = self._key("account", str(account_id), "health")
        await self.set(key, health_data, ttl)

    async def invalidate_account_health(self, account_id: UUID) -> bool:
        """
        Invalidate account health cache.

        Args:
            account_id: Account UUID

        Returns:
            True if invalidated
        """
        key = self._key("account", str(account_id), "health")
        return await self.delete(key)

    # User settings caching
    async def get_user_settings(self, user_id: UUID) -> Optional[dict]:
        """
        Get cached user settings.

        Args:
            user_id: User UUID

        Returns:
            Settings or None
        """
        key = self._key("user", str(user_id), "settings")
        return await self.get(key)

    async def set_user_settings(
        self,
        user_id: UUID,
        settings: dict,
        ttl: int = CACHE_TTL_USER_SETTINGS,
    ) -> None:
        """
        Cache user settings.

        Args:
            user_id: User UUID
            settings: Settings dictionary
            ttl: Cache TTL in seconds
        """
        key = self._key("user", str(user_id), "settings")
        await self.set(key, settings, ttl)

    async def invalidate_user_settings(self, user_id: UUID) -> bool:
        """
        Invalidate user settings cache.

        Args:
            user_id: User UUID

        Returns:
            True if invalidated
        """
        key = self._key("user", str(user_id), "settings")
        return await self.delete(key)

    # Campaign progress caching (for quick status access)
    async def get_campaign_progress(self, campaign_id: UUID) -> Optional[dict]:
        """
        Get cached campaign progress.

        Args:
            campaign_id: Campaign UUID

        Returns:
            Progress data or None
        """
        key = self._key("campaign", str(campaign_id), "progress")
        return await self.get(key)

    async def set_campaign_progress(
        self,
        campaign_id: UUID,
        progress: dict,
        ttl: int = 60,
    ) -> None:
        """
        Cache campaign progress (short TTL for real-time updates).

        Args:
            campaign_id: Campaign UUID
            progress: Progress dictionary
            ttl: Cache TTL in seconds
        """
        key = self._key("campaign", str(campaign_id), "progress")
        await self.set(key, progress, ttl)

    async def invalidate_campaign_progress(self, campaign_id: UUID) -> bool:
        """
        Invalidate campaign progress cache.

        Args:
            campaign_id: Campaign UUID

        Returns:
            True if invalidated
        """
        key = self._key("campaign", str(campaign_id), "progress")
        return await self.delete(key)

    # Bulk invalidation
    async def invalidate_user_cache(self, user_id: UUID) -> int:
        """
        Invalidate all cache for user.

        Args:
            user_id: User UUID

        Returns:
            Number of deleted keys
        """
        pattern = self._key("*", str(user_id), "*")
        keys = []
        async for key in self.redis.scan_iter(match=pattern):
            keys.append(key)

        if keys:
            return await self.redis.delete(*keys)
        return 0
