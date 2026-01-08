"""Redis distributed locks."""

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional
from uuid import UUID, uuid4

from redis.asyncio import Redis

from common.constants import REDIS_PREFIX_LOCK
from common.logger import get_logger

logger = get_logger(__name__)


class LockManager:
    """
    Manager for Redis-based distributed locks.

    Provides non-blocking and blocking lock acquisition for resources.
    """

    # Default lock settings
    DEFAULT_TTL = 30  # seconds
    DEFAULT_TIMEOUT = 10  # seconds for blocking acquire
    RETRY_INTERVAL = 0.1  # seconds between retries

    def __init__(self, redis: Redis):
        """
        Initialize lock manager.

        Args:
            redis: Redis client instance
        """
        self.redis = redis
        self._lock_token = str(uuid4())

    def _key(self, resource_type: str, resource_id: str) -> str:
        """Build lock key."""
        return f"{REDIS_PREFIX_LOCK}:{resource_type}:{resource_id}"

    async def acquire(
        self,
        resource_type: str,
        resource_id: str,
        ttl: int = DEFAULT_TTL,
    ) -> bool:
        """
        Try to acquire lock (non-blocking).

        Args:
            resource_type: Type of resource (e.g., 'account', 'campaign')
            resource_id: Resource ID
            ttl: Lock TTL in seconds

        Returns:
            True if lock acquired, False otherwise
        """
        key = self._key(resource_type, resource_id)
        token = f"{self._lock_token}:{resource_id}"

        # SET NX with expiration
        result = await self.redis.set(key, token, nx=True, ex=ttl)
        if result:
            logger.debug(f"Lock acquired: {key}")
            return True
        return False

    async def acquire_blocking(
        self,
        resource_type: str,
        resource_id: str,
        ttl: int = DEFAULT_TTL,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> bool:
        """
        Try to acquire lock with blocking (retry until timeout).

        Args:
            resource_type: Type of resource
            resource_id: Resource ID
            ttl: Lock TTL in seconds
            timeout: Maximum time to wait for lock

        Returns:
            True if lock acquired, False on timeout
        """
        elapsed = 0.0
        while elapsed < timeout:
            if await self.acquire(resource_type, resource_id, ttl):
                return True
            await asyncio.sleep(self.RETRY_INTERVAL)
            elapsed += self.RETRY_INTERVAL
        return False

    async def release(self, resource_type: str, resource_id: str) -> bool:
        """
        Release lock.

        Args:
            resource_type: Type of resource
            resource_id: Resource ID

        Returns:
            True if lock released, False if not owned
        """
        key = self._key(resource_type, resource_id)
        token = f"{self._lock_token}:{resource_id}"

        # Only release if we own the lock (check token)
        current = await self.redis.get(key)
        if current == token:
            await self.redis.delete(key)
            logger.debug(f"Lock released: {key}")
            return True
        return False

    async def extend(
        self,
        resource_type: str,
        resource_id: str,
        ttl: int = DEFAULT_TTL,
    ) -> bool:
        """
        Extend lock TTL.

        Args:
            resource_type: Type of resource
            resource_id: Resource ID
            ttl: New TTL in seconds

        Returns:
            True if extended, False if not owned
        """
        key = self._key(resource_type, resource_id)
        token = f"{self._lock_token}:{resource_id}"

        current = await self.redis.get(key)
        if current == token:
            await self.redis.expire(key, ttl)
            logger.debug(f"Lock extended: {key}")
            return True
        return False

    async def is_locked(self, resource_type: str, resource_id: str) -> bool:
        """
        Check if resource is locked.

        Args:
            resource_type: Type of resource
            resource_id: Resource ID

        Returns:
            True if locked
        """
        key = self._key(resource_type, resource_id)
        return await self.redis.exists(key) > 0

    async def get_lock_info(
        self,
        resource_type: str,
        resource_id: str,
    ) -> Optional[dict]:
        """
        Get lock information.

        Args:
            resource_type: Type of resource
            resource_id: Resource ID

        Returns:
            Lock info dict or None
        """
        key = self._key(resource_type, resource_id)
        token = await self.redis.get(key)
        if not token:
            return None

        ttl = await self.redis.ttl(key)
        return {
            "locked": True,
            "token": token,
            "ttl": ttl,
            "owned": token == f"{self._lock_token}:{resource_id}",
        }

    @asynccontextmanager
    async def lock(
        self,
        resource_type: str,
        resource_id: str,
        ttl: int = DEFAULT_TTL,
        timeout: float = DEFAULT_TIMEOUT,
        blocking: bool = True,
    ) -> AsyncGenerator[bool, None]:
        """
        Context manager for lock acquisition.

        Args:
            resource_type: Type of resource
            resource_id: Resource ID
            ttl: Lock TTL in seconds
            timeout: Timeout for blocking acquire
            blocking: Whether to block waiting for lock

        Yields:
            True if lock acquired, False otherwise

        Example:
            async with lock_manager.lock("account", account_id) as acquired:
                if acquired:
                    # do work
        """
        acquired = False
        try:
            if blocking:
                acquired = await self.acquire_blocking(
                    resource_type, resource_id, ttl, timeout
                )
            else:
                acquired = await self.acquire(resource_type, resource_id, ttl)
            yield acquired
        finally:
            if acquired:
                await self.release(resource_type, resource_id)

    # Convenience methods for common lock types
    async def lock_account(
        self,
        account_id: UUID,
        ttl: int = DEFAULT_TTL,
    ) -> bool:
        """Lock account for exclusive access."""
        return await self.acquire("account", str(account_id), ttl)

    async def unlock_account(self, account_id: UUID) -> bool:
        """Unlock account."""
        return await self.release("account", str(account_id))

    async def lock_campaign(
        self,
        campaign_id: UUID,
        ttl: int = DEFAULT_TTL,
    ) -> bool:
        """Lock campaign for exclusive access."""
        return await self.acquire("campaign", str(campaign_id), ttl)

    async def unlock_campaign(self, campaign_id: UUID) -> bool:
        """Unlock campaign."""
        return await self.release("campaign", str(campaign_id))

    @asynccontextmanager
    async def account_lock(
        self,
        account_id: UUID,
        ttl: int = DEFAULT_TTL,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> AsyncGenerator[bool, None]:
        """Context manager for account lock."""
        async with self.lock("account", str(account_id), ttl, timeout) as acquired:
            yield acquired

    @asynccontextmanager
    async def campaign_lock(
        self,
        campaign_id: UUID,
        ttl: int = DEFAULT_TTL,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> AsyncGenerator[bool, None]:
        """Context manager for campaign lock."""
        async with self.lock("campaign", str(campaign_id), ttl, timeout) as acquired:
            yield acquired
