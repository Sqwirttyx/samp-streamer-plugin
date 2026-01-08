"""Telethon session storage management."""

import hashlib
import os
import tempfile
from pathlib import Path
from typing import Optional, Union
from uuid import UUID

import aiofiles

from common.exceptions import (
    SessionDecryptionError,
    SessionNotFoundError,
    SessionValidationError,
)
from common.logger import get_logger
from storage.encryption import EncryptionManager, get_encryption_manager

logger = get_logger(__name__)


class SessionStorage:
    """
    Manager for Telethon session file storage.

    Handles encrypted storage, retrieval, and validation of session files.

    Storage structure:
        {base_path}/{user_id}/{account_id}.session.enc
    """

    SESSION_EXTENSION = ".session"
    ENCRYPTED_EXTENSION = ".session.enc"

    def __init__(
        self,
        base_path: Union[str, Path],
        encryption_manager: Optional[EncryptionManager] = None,
    ):
        """
        Initialize session storage.

        Args:
            base_path: Base directory for session storage
            encryption_manager: Encryption manager (uses default if None)
        """
        self.base_path = Path(base_path)
        self.encryption = encryption_manager or get_encryption_manager()
        self._temp_dir = Path(tempfile.gettempdir()) / "telegram_sessions"

    def _user_dir(self, user_id: UUID) -> Path:
        """Get user's session directory."""
        return self.base_path / str(user_id)

    def _session_path(self, user_id: UUID, account_id: UUID) -> Path:
        """Get path for encrypted session file."""
        return self._user_dir(user_id) / f"{account_id}{self.ENCRYPTED_EXTENSION}"

    @staticmethod
    def hash_phone(phone: str) -> str:
        """
        Create hash of phone number.

        Args:
            phone: Phone number

        Returns:
            SHA256 hash of phone
        """
        normalized = "".join(filter(str.isdigit, phone))
        return hashlib.sha256(normalized.encode()).hexdigest()[:16]

    async def save_session(
        self,
        user_id: UUID,
        account_id: UUID,
        session_file: Union[str, Path, bytes],
    ) -> Path:
        """
        Save and encrypt session file.

        Args:
            user_id: User UUID
            account_id: Account UUID
            session_file: Path to session file or session data bytes

        Returns:
            Path to encrypted session file

        Raises:
            SessionValidationError: If session file is invalid
        """
        dest_path = self._session_path(user_id, account_id)
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        if isinstance(session_file, bytes):
            # Direct bytes data
            if not self._validate_session_data(session_file):
                raise SessionValidationError("Invalid session data format")

            encrypted = self.encryption.encrypt_data(session_file)
            async with aiofiles.open(dest_path, "wb") as f:
                await f.write(encrypted)
        else:
            # File path
            session_file = Path(session_file)
            if not session_file.exists():
                raise SessionNotFoundError(f"Session file not found: {session_file}")

            if not await self._validate_session_file(session_file):
                raise SessionValidationError("Invalid session file format")

            await self.encryption.encrypt_file(session_file, dest_path)

        logger.info(f"Session saved: {dest_path}")
        return dest_path

    async def get_session(
        self,
        user_id: UUID,
        account_id: UUID,
    ) -> Path:
        """
        Get decrypted session file (temporary).

        Args:
            user_id: User UUID
            account_id: Account UUID

        Returns:
            Path to temporary decrypted session file

        Raises:
            SessionNotFoundError: If session not found
            SessionDecryptionError: If decryption fails
        """
        encrypted_path = self._session_path(user_id, account_id)

        if not encrypted_path.exists():
            raise SessionNotFoundError(f"Session not found for account {account_id}")

        try:
            self._temp_dir.mkdir(parents=True, exist_ok=True)
            temp_path = self._temp_dir / f"{account_id}{self.SESSION_EXTENSION}"

            await self.encryption.decrypt_file(encrypted_path, temp_path)
            logger.debug(f"Session decrypted to: {temp_path}")

            return temp_path

        except Exception as e:
            raise SessionDecryptionError(f"Failed to decrypt session: {e}")

    async def get_session_data(
        self,
        user_id: UUID,
        account_id: UUID,
    ) -> bytes:
        """
        Get decrypted session data as bytes.

        Args:
            user_id: User UUID
            account_id: Account UUID

        Returns:
            Session data bytes

        Raises:
            SessionNotFoundError: If session not found
            SessionDecryptionError: If decryption fails
        """
        encrypted_path = self._session_path(user_id, account_id)

        if not encrypted_path.exists():
            raise SessionNotFoundError(f"Session not found for account {account_id}")

        try:
            async with aiofiles.open(encrypted_path, "rb") as f:
                encrypted_data = await f.read()

            return self.encryption.decrypt_data(encrypted_data)

        except Exception as e:
            raise SessionDecryptionError(f"Failed to decrypt session: {e}")

    async def delete_session(
        self,
        user_id: UUID,
        account_id: UUID,
    ) -> bool:
        """
        Delete session file.

        Args:
            user_id: User UUID
            account_id: Account UUID

        Returns:
            True if deleted, False if not found
        """
        encrypted_path = self._session_path(user_id, account_id)

        if encrypted_path.exists():
            encrypted_path.unlink()
            logger.info(f"Session deleted: {encrypted_path}")
            return True

        return False

    async def session_exists(
        self,
        user_id: UUID,
        account_id: UUID,
    ) -> bool:
        """
        Check if session exists.

        Args:
            user_id: User UUID
            account_id: Account UUID

        Returns:
            True if session exists
        """
        return self._session_path(user_id, account_id).exists()

    async def list_sessions(self, user_id: UUID) -> list[str]:
        """
        List all session IDs for user.

        Args:
            user_id: User UUID

        Returns:
            List of account ID strings
        """
        user_dir = self._user_dir(user_id)
        if not user_dir.exists():
            return []

        sessions = []
        for file in user_dir.iterdir():
            if file.suffix == ".enc" and file.stem.endswith(".session"):
                account_id = file.stem.replace(".session", "")
                sessions.append(account_id)

        return sessions

    async def cleanup_temp_sessions(self) -> int:
        """
        Clean up temporary decrypted session files.

        Returns:
            Number of files cleaned up
        """
        if not self._temp_dir.exists():
            return 0

        count = 0
        for file in self._temp_dir.iterdir():
            if file.suffix == self.SESSION_EXTENSION:
                file.unlink()
                count += 1

        if count > 0:
            logger.info(f"Cleaned up {count} temporary session files")

        return count

    async def _validate_session_file(self, path: Path) -> bool:
        """Validate session file format."""
        try:
            async with aiofiles.open(path, "rb") as f:
                data = await f.read()
            return self._validate_session_data(data)
        except Exception:
            return False

    @staticmethod
    def _validate_session_data(data: bytes) -> bool:
        """
        Validate session data format.

        Telethon SQLite session files have specific structure.
        """
        if len(data) < 100:  # Too small for valid session
            return False

        # SQLite database header
        if not data.startswith(b"SQLite format 3"):
            return False

        return True

    def get_session_string_path(
        self,
        user_id: UUID,
        account_id: UUID,
    ) -> str:
        """
        Get relative session path for Telethon StringSession.

        Args:
            user_id: User UUID
            account_id: Account UUID

        Returns:
            Relative path string
        """
        return str(self._session_path(user_id, account_id).relative_to(self.base_path))


def get_session_storage() -> SessionStorage:
    """
    Get session storage with configured path.

    Returns:
        SessionStorage instance
    """
    from common.config import settings

    return SessionStorage(settings.sessions_path)
