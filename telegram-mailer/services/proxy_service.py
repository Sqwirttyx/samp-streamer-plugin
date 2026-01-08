"""Proxy service - business logic for proxy management."""

import asyncio
from typing import Optional
from uuid import UUID

import aiohttp

from common.constants import ProxyType
from common.exceptions import NotFoundError, ValidationError
from common.logger import get_logger
from database import get_db_manager
from database.models import Proxy
from database.repositories import ProxyRepository

logger = get_logger(__name__)


class ProxyService:
    """
    Service for proxy management.

    Handles proxy CRUD, validation, and checking.
    """

    CHECK_TIMEOUT = 10  # seconds
    CHECK_URL = "https://api.telegram.org"

    async def get_by_id(
        self,
        proxy_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> Optional[Proxy]:
        """
        Get proxy by ID.

        Args:
            proxy_id: Proxy UUID
            user_id: Owner user ID (optional, for validation)

        Returns:
            Proxy or None
        """
        db_manager = get_db_manager()

        async with db_manager.readonly_session() as session:
            repo = ProxyRepository(session)
            proxy = await repo.get_by_id(proxy_id)

            if proxy and user_id and proxy.user_id != user_id:
                return None

            return proxy

    async def get_user_proxies(self, user_id: UUID) -> list[Proxy]:
        """
        Get all proxies for user.

        Args:
            user_id: User UUID

        Returns:
            List of proxies
        """
        db_manager = get_db_manager()

        async with db_manager.readonly_session() as session:
            repo = ProxyRepository(session)
            return await repo.get_by_user(user_id)

    async def add_proxy(
        self,
        user_id: UUID,
        proxy_string: str,
        name: Optional[str] = None,
    ) -> Proxy:
        """
        Add new proxy from string.

        Args:
            user_id: Owner user ID
            proxy_string: Proxy string (type://user:pass@host:port)
            name: Optional name

        Returns:
            Created proxy

        Raises:
            ValidationError: If proxy string is invalid
        """
        # Parse proxy string
        parsed = self._parse_proxy_string(proxy_string)
        if not parsed:
            raise ValidationError("Invalid proxy format")

        db_manager = get_db_manager()

        async with db_manager.session() as session:
            repo = ProxyRepository(session)

            # Check for duplicates
            existing = await repo.get_by_host_port(
                user_id=user_id,
                host=parsed["host"],
                port=parsed["port"],
            )
            if existing:
                raise ValidationError("Proxy already exists")

            proxy = await repo.create(
                user_id=user_id,
                proxy_type=parsed["type"],
                host=parsed["host"],
                port=parsed["port"],
                username=parsed.get("username"),
                password=parsed.get("password"),
                name=name,
            )

            logger.info(f"Proxy added: {proxy.id} for user {user_id}")
            return proxy

    async def delete_proxy(
        self,
        proxy_id: UUID,
        user_id: UUID,
    ) -> bool:
        """
        Delete proxy.

        Args:
            proxy_id: Proxy UUID
            user_id: Owner user ID

        Returns:
            True if deleted
        """
        proxy = await self.get_by_id(proxy_id, user_id)
        if not proxy:
            raise NotFoundError("Proxy not found")

        db_manager = get_db_manager()

        async with db_manager.session() as session:
            repo = ProxyRepository(session)
            result = await repo.delete(proxy_id)

            if result:
                logger.info(f"Proxy deleted: {proxy_id}")

            return result

    async def check_proxy(
        self,
        proxy_id: UUID,
        user_id: UUID,
    ) -> tuple[bool, str]:
        """
        Check if proxy is working.

        Args:
            proxy_id: Proxy UUID
            user_id: Owner user ID

        Returns:
            Tuple of (is_working, message)
        """
        proxy = await self.get_by_id(proxy_id, user_id)
        if not proxy:
            return False, "Proxy not found"

        return await self._check_proxy_connection(proxy)

    async def check_all_proxies(
        self,
        user_id: UUID,
    ) -> list[dict]:
        """
        Check all user proxies.

        Args:
            user_id: User UUID

        Returns:
            List of check results
        """
        proxies = await self.get_user_proxies(user_id)

        async def check_one(proxy: Proxy) -> dict:
            is_working, message = await self._check_proxy_connection(proxy)
            return {
                "proxy_id": str(proxy.id),
                "name": proxy.name,
                "host": proxy.host,
                "is_working": is_working,
                "message": message,
            }

        tasks = [check_one(p) for p in proxies]
        return await asyncio.gather(*tasks)

    async def _check_proxy_connection(
        self,
        proxy: Proxy,
    ) -> tuple[bool, str]:
        """
        Check proxy connection.

        Args:
            proxy: Proxy model

        Returns:
            Tuple of (is_working, message)
        """
        proxy_url = self._build_proxy_url(proxy)

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    self.CHECK_URL,
                    proxy=proxy_url,
                    timeout=aiohttp.ClientTimeout(total=self.CHECK_TIMEOUT),
                ) as response:
                    if response.status == 200:
                        # Update last check time
                        await self._update_check_result(proxy.id, True)
                        return True, "Proxy is working"
                    else:
                        await self._update_check_result(proxy.id, False)
                        return False, f"HTTP {response.status}"

        except asyncio.TimeoutError:
            await self._update_check_result(proxy.id, False)
            return False, "Connection timeout"
        except aiohttp.ClientProxyConnectionError as e:
            await self._update_check_result(proxy.id, False)
            return False, f"Proxy connection error: {e}"
        except Exception as e:
            await self._update_check_result(proxy.id, False)
            return False, f"Error: {str(e)}"

    async def _update_check_result(
        self,
        proxy_id: UUID,
        is_working: bool,
    ) -> None:
        """Update proxy check result in database."""
        db_manager = get_db_manager()

        async with db_manager.session() as session:
            repo = ProxyRepository(session)
            await repo.update_check_result(proxy_id, is_working)

    def _parse_proxy_string(self, proxy_string: str) -> Optional[dict]:
        """
        Parse proxy string into components.

        Formats:
        - type://host:port
        - type://user:pass@host:port
        - host:port:user:pass (legacy format)

        Args:
            proxy_string: Proxy string

        Returns:
            Parsed components or None
        """
        proxy_string = proxy_string.strip()

        # Try URL format first
        if "://" in proxy_string:
            try:
                from urllib.parse import urlparse

                parsed = urlparse(proxy_string)

                proxy_type = ProxyType.SOCKS5
                if parsed.scheme in ("http", "https"):
                    proxy_type = ProxyType.HTTP
                elif parsed.scheme == "socks5":
                    proxy_type = ProxyType.SOCKS5

                return {
                    "type": proxy_type,
                    "host": parsed.hostname,
                    "port": parsed.port or 1080,
                    "username": parsed.username,
                    "password": parsed.password,
                }
            except Exception:
                pass

        # Try legacy format (host:port:user:pass)
        parts = proxy_string.split(":")
        if len(parts) >= 2:
            try:
                result = {
                    "type": ProxyType.SOCKS5,
                    "host": parts[0],
                    "port": int(parts[1]),
                }
                if len(parts) >= 4:
                    result["username"] = parts[2]
                    result["password"] = parts[3]
                return result
            except ValueError:
                pass

        return None

    def _build_proxy_url(self, proxy: Proxy) -> str:
        """
        Build proxy URL from model.

        Args:
            proxy: Proxy model

        Returns:
            Proxy URL string
        """
        scheme = "http" if proxy.type == ProxyType.HTTP else "socks5"

        if proxy.username and proxy.password:
            return f"{scheme}://{proxy.username}:{proxy.password}@{proxy.host}:{proxy.port}"
        else:
            return f"{scheme}://{proxy.host}:{proxy.port}"

    def format_proxy(self, proxy: Proxy) -> str:
        """
        Format proxy for display.

        Args:
            proxy: Proxy model

        Returns:
            Formatted string
        """
        parts = [f"{proxy.type.value}://"]

        if proxy.username:
            parts.append(f"{proxy.username}:***@")

        parts.append(f"{proxy.host}:{proxy.port}")

        return "".join(parts)
