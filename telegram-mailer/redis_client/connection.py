"""Redis connection management."""

from typing import Optional

import redis.asyncio as redis
from redis.asyncio import Redis

from common.logger import get_logger

logger = get_logger(__name__)


class RedisManager:
    """
    Redis connection manager.

    Handles async connection pool for Redis operations.
    """

    def __init__(self, redis_url: str):
        """
        Initialize Redis manager.

        Args:
            redis_url: Redis connection URL
        """
        self._redis_url = redis_url
        self._client: Optional[Redis] = None

    @property
    def client(self) -> Redis:
        """Get Redis client, creating if necessary."""
        if self._client is None:
            self._client = redis.from_url(
                self._redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
            logger.info("Redis client created")
        return self._client

    async def init(self) -> None:
        """Initialize and test Redis connection."""
        logger.info("Initializing Redis connection")
        await self.client.ping()
        logger.info("Redis connection established")

    async def close(self) -> None:
        """Close Redis connection."""
        if self._client is not None:
            await self._client.close()
            self._client = None
            logger.info("Redis connection closed")

    async def health_check(self) -> bool:
        """
        Check Redis connection health.

        Returns:
            True if healthy, False otherwise
        """
        try:
            await self.client.ping()
            return True
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            return False


# Global Redis manager instance
_redis_manager: Optional[RedisManager] = None


def get_redis_manager() -> RedisManager:
    """Get the global Redis manager instance."""
    global _redis_manager
    if _redis_manager is None:
        from common.config import settings

        _redis_manager = RedisManager(settings.redis_url)
    return _redis_manager


async def get_redis() -> Redis:
    """
    Get Redis client.

    Returns:
        Redis client instance
    """
    return get_redis_manager().client
