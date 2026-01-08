"""Proxy repository."""

from datetime import datetime
from typing import Optional, Sequence
from uuid import UUID

from sqlalchemy import select, update

from common.constants import ProxyStatus, ProxyType
from database.models.proxy import Proxy
from database.repositories.base import BaseRepository


class ProxyRepository(BaseRepository[Proxy]):
    """Repository for Proxy model operations."""

    model = Proxy

    async def get_by_user(
        self,
        user_id: UUID,
        status: Optional[ProxyStatus] = None,
        offset: int = 0,
        limit: int = 100,
    ) -> Sequence[Proxy]:
        """
        Get proxies by user ID.

        Args:
            user_id: User UUID
            status: Filter by status (optional)
            offset: Pagination offset
            limit: Pagination limit

        Returns:
            List of proxies
        """
        query = select(Proxy).where(Proxy.user_id == user_id)

        if status:
            query = query.where(Proxy.status == status)

        query = query.offset(offset).limit(limit)
        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_active_by_user(self, user_id: UUID) -> Sequence[Proxy]:
        """
        Get active proxies for user.

        Args:
            user_id: User UUID

        Returns:
            List of active proxies
        """
        return await self.get_by_user(user_id, status=ProxyStatus.ACTIVE)

    async def get_available(self, user_id: UUID) -> Optional[Proxy]:
        """
        Get first available proxy for user.

        Args:
            user_id: User UUID

        Returns:
            Available proxy or None
        """
        result = await self.session.execute(
            select(Proxy)
            .where(
                Proxy.user_id == user_id,
                Proxy.status == ProxyStatus.ACTIVE,
            )
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def create_proxy(
        self,
        user_id: UUID,
        proxy_type: ProxyType,
        host: str,
        port: int,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ) -> Proxy:
        """
        Create a new proxy.

        Args:
            user_id: User UUID
            proxy_type: Proxy type
            host: Proxy host
            port: Proxy port
            username: Proxy username (optional)
            password: Proxy password (optional)

        Returns:
            Created proxy instance
        """
        return await self.create(
            user_id=user_id,
            type=proxy_type,
            host=host,
            port=port,
            username=username,
            password=password,
            status=ProxyStatus.ACTIVE,
        )

    async def update_status(
        self,
        proxy_id: UUID,
        status: ProxyStatus,
    ) -> Optional[Proxy]:
        """
        Update proxy status.

        Args:
            proxy_id: Proxy UUID
            status: New status

        Returns:
            Updated proxy or None
        """
        await self.session.execute(
            update(Proxy)
            .where(Proxy.id == proxy_id)
            .values(status=status, last_check=datetime.utcnow())
        )
        await self.session.flush()
        return await self.get_by_id(proxy_id)

    async def mark_checked(self, proxy_id: UUID, is_alive: bool) -> Optional[Proxy]:
        """
        Mark proxy as checked.

        Args:
            proxy_id: Proxy UUID
            is_alive: Whether proxy is alive

        Returns:
            Updated proxy or None
        """
        status = ProxyStatus.ACTIVE if is_alive else ProxyStatus.DEAD
        return await self.update_status(proxy_id, status)

    async def count_by_user(self, user_id: UUID) -> int:
        """
        Count proxies for user.

        Args:
            user_id: User UUID

        Returns:
            Number of proxies
        """
        return await self.count(user_id=user_id)

    async def get_dead_proxies(self, user_id: UUID) -> Sequence[Proxy]:
        """
        Get dead proxies for user.

        Args:
            user_id: User UUID

        Returns:
            List of dead proxies
        """
        return await self.get_by_user(user_id, status=ProxyStatus.DEAD)

    @staticmethod
    def parse_proxy_string(proxy_string: str) -> dict:
        """
        Parse proxy connection string.

        Format: type://user:pass@host:port or type://host:port

        Args:
            proxy_string: Proxy connection string

        Returns:
            Dictionary with proxy parameters

        Raises:
            ValueError: If format is invalid
        """
        import re

        pattern = r"^(socks5|http|mtproxy)://(?:([^:]+):([^@]+)@)?([^:]+):(\d+)$"
        match = re.match(pattern, proxy_string)

        if not match:
            raise ValueError(f"Invalid proxy format: {proxy_string}")

        proxy_type, username, password, host, port = match.groups()

        return {
            "type": ProxyType(proxy_type),
            "host": host,
            "port": int(port),
            "username": username,
            "password": password,
        }
