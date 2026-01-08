"""Telethon session management."""

from pathlib import Path
from typing import Optional
from uuid import UUID

from telethon import TelegramClient
from telethon.sessions import StringSession

from common.config import settings
from common.exceptions import (
    AccountSessionInvalidError,
    ProxyConnectionError,
    SessionDecryptionError,
)
from common.logger import get_logger
from storage.session_storage import get_session_storage

logger = get_logger(__name__)


class SessionManager:
    """
    Manager for Telethon client sessions.

    Handles loading, validating, and managing Telegram client connections.
    """

    def __init__(self):
        """Initialize session manager."""
        self.api_id = settings.api_id
        self.api_hash = settings.api_hash
        self.storage = get_session_storage()
        self._clients: dict[str, TelegramClient] = {}

    async def load_session(
        self,
        user_id: UUID,
        account_id: UUID,
        proxy: Optional[dict] = None,
    ) -> TelegramClient:
        """
        Load and connect Telethon client from stored session.

        Args:
            user_id: User UUID
            account_id: Account UUID
            proxy: Proxy configuration dict (optional)

        Returns:
            Connected TelegramClient

        Raises:
            SessionDecryptionError: If session decryption fails
            AccountSessionInvalidError: If session is invalid
            ProxyConnectionError: If proxy connection fails
        """
        account_key = str(account_id)

        # Check if already loaded
        if account_key in self._clients:
            client = self._clients[account_key]
            if client.is_connected():
                return client

        # Get decrypted session path
        try:
            session_path = await self.storage.get_session(user_id, account_id)
        except Exception as e:
            raise SessionDecryptionError(f"Failed to load session: {e}")

        # Build proxy config for Telethon
        proxy_config = None
        if proxy:
            proxy_config = self._build_proxy_config(proxy)

        # Create client
        client = TelegramClient(
            str(session_path),
            self.api_id,
            self.api_hash,
            proxy=proxy_config,
        )

        # Connect
        try:
            await client.connect()

            if not await client.is_user_authorized():
                raise AccountSessionInvalidError("Session is not authorized")

            self._clients[account_key] = client
            logger.info(f"Session loaded for account {account_id}")

            return client

        except AccountSessionInvalidError:
            raise
        except Exception as e:
            await client.disconnect()
            if "proxy" in str(e).lower():
                raise ProxyConnectionError(f"Proxy connection failed: {e}")
            raise AccountSessionInvalidError(f"Failed to connect: {e}")

    async def validate_session(self, client: TelegramClient) -> bool:
        """
        Validate session by checking authorization and ability to send.

        Args:
            client: TelegramClient instance

        Returns:
            True if session is valid
        """
        try:
            if not client.is_connected():
                await client.connect()

            if not await client.is_user_authorized():
                return False

            # Try to get own info
            me = await client.get_me()
            return me is not None

        except Exception as e:
            logger.error(f"Session validation failed: {e}")
            return False

    async def get_me(self, client: TelegramClient):
        """
        Get current user info.

        Args:
            client: TelegramClient instance

        Returns:
            User object
        """
        return await client.get_me()

    async def close_session(self, account_id: UUID) -> None:
        """
        Close and cleanup session.

        Args:
            account_id: Account UUID
        """
        account_key = str(account_id)

        if account_key in self._clients:
            client = self._clients[account_key]
            try:
                await client.disconnect()
            except Exception as e:
                logger.error(f"Error closing session: {e}")
            finally:
                del self._clients[account_key]
                logger.info(f"Session closed for account {account_id}")

    async def close_all(self) -> None:
        """Close all active sessions."""
        for account_key in list(self._clients.keys()):
            await self.close_session(UUID(account_key))

    def _build_proxy_config(self, proxy: dict) -> tuple:
        """
        Build Telethon proxy configuration.

        Args:
            proxy: Proxy dict with type, host, port, username, password

        Returns:
            Proxy tuple for Telethon
        """
        import socks

        proxy_type_map = {
            "socks5": socks.SOCKS5,
            "socks4": socks.SOCKS4,
            "http": socks.HTTP,
        }

        proxy_type = proxy_type_map.get(proxy.get("type", "socks5"), socks.SOCKS5)

        return (
            proxy_type,
            proxy["host"],
            proxy["port"],
            True,  # rdns
            proxy.get("username"),
            proxy.get("password"),
        )

    async def test_connection(
        self,
        client: TelegramClient,
    ) -> bool:
        """
        Test connection by sending message to Saved Messages.

        Args:
            client: TelegramClient instance

        Returns:
            True if test successful
        """
        try:
            await client.send_message("me", "🔄 Test message - connection check")
            return True
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False

    def get_active_count(self) -> int:
        """Get number of active sessions."""
        return len(self._clients)

    def is_loaded(self, account_id: UUID) -> bool:
        """Check if session is loaded."""
        return str(account_id) in self._clients


# Global session manager
_session_manager: Optional[SessionManager] = None


def get_session_manager() -> SessionManager:
    """Get global session manager instance."""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager
