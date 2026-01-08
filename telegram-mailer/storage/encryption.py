"""Encryption module for secure data storage."""

import os
from pathlib import Path
from typing import Union

import aiofiles
from cryptography.fernet import Fernet, InvalidToken

from common.exceptions import EncryptionError, EncryptionKeyError
from common.logger import get_logger

logger = get_logger(__name__)


class EncryptionManager:
    """
    Manager for AES-256 encryption using Fernet.

    Provides file and data encryption/decryption capabilities.
    """

    def __init__(self, encryption_key: str):
        """
        Initialize encryption manager.

        Args:
            encryption_key: Fernet-compatible encryption key

        Raises:
            EncryptionKeyError: If key is invalid
        """
        try:
            self._fernet = Fernet(encryption_key.encode())
        except Exception as e:
            raise EncryptionKeyError(f"Invalid encryption key: {e}")

    @staticmethod
    def generate_key() -> str:
        """
        Generate a new Fernet encryption key.

        Returns:
            Base64-encoded encryption key
        """
        return Fernet.generate_key().decode()

    def encrypt_data(self, data: bytes) -> bytes:
        """
        Encrypt bytes data.

        Args:
            data: Data to encrypt

        Returns:
            Encrypted data
        """
        try:
            return self._fernet.encrypt(data)
        except Exception as e:
            raise EncryptionError(f"Encryption failed: {e}")

    def decrypt_data(self, encrypted_data: bytes) -> bytes:
        """
        Decrypt bytes data.

        Args:
            encrypted_data: Encrypted data

        Returns:
            Decrypted data

        Raises:
            EncryptionError: If decryption fails
        """
        try:
            return self._fernet.decrypt(encrypted_data)
        except InvalidToken:
            raise EncryptionError("Decryption failed: invalid token or key")
        except Exception as e:
            raise EncryptionError(f"Decryption failed: {e}")

    def encrypt_string(self, text: str) -> str:
        """
        Encrypt string data.

        Args:
            text: Text to encrypt

        Returns:
            Base64-encoded encrypted string
        """
        encrypted = self.encrypt_data(text.encode("utf-8"))
        return encrypted.decode("utf-8")

    def decrypt_string(self, encrypted_text: str) -> str:
        """
        Decrypt string data.

        Args:
            encrypted_text: Encrypted text

        Returns:
            Decrypted text
        """
        decrypted = self.decrypt_data(encrypted_text.encode("utf-8"))
        return decrypted.decode("utf-8")

    async def encrypt_file(
        self,
        source_path: Union[str, Path],
        dest_path: Union[str, Path],
    ) -> Path:
        """
        Encrypt a file.

        Args:
            source_path: Path to source file
            dest_path: Path to encrypted file

        Returns:
            Path to encrypted file

        Raises:
            EncryptionError: If encryption fails
        """
        source_path = Path(source_path)
        dest_path = Path(dest_path)

        if not source_path.exists():
            raise EncryptionError(f"Source file not found: {source_path}")

        try:
            # Read source file
            async with aiofiles.open(source_path, "rb") as f:
                data = await f.read()

            # Encrypt data
            encrypted_data = self.encrypt_data(data)

            # Write encrypted file
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            async with aiofiles.open(dest_path, "wb") as f:
                await f.write(encrypted_data)

            logger.info(f"File encrypted: {source_path} -> {dest_path}")
            return dest_path

        except EncryptionError:
            raise
        except Exception as e:
            raise EncryptionError(f"Failed to encrypt file: {e}")

    async def decrypt_file(
        self,
        source_path: Union[str, Path],
        dest_path: Union[str, Path],
    ) -> Path:
        """
        Decrypt a file.

        Args:
            source_path: Path to encrypted file
            dest_path: Path to decrypted file

        Returns:
            Path to decrypted file

        Raises:
            EncryptionError: If decryption fails
        """
        source_path = Path(source_path)
        dest_path = Path(dest_path)

        if not source_path.exists():
            raise EncryptionError(f"Encrypted file not found: {source_path}")

        try:
            # Read encrypted file
            async with aiofiles.open(source_path, "rb") as f:
                encrypted_data = await f.read()

            # Decrypt data
            data = self.decrypt_data(encrypted_data)

            # Write decrypted file
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            async with aiofiles.open(dest_path, "wb") as f:
                await f.write(data)

            logger.info(f"File decrypted: {source_path} -> {dest_path}")
            return dest_path

        except EncryptionError:
            raise
        except Exception as e:
            raise EncryptionError(f"Failed to decrypt file: {e}")

    async def encrypt_file_in_place(self, file_path: Union[str, Path]) -> Path:
        """
        Encrypt a file in place (adds .enc extension).

        Args:
            file_path: Path to file

        Returns:
            Path to encrypted file
        """
        file_path = Path(file_path)
        encrypted_path = file_path.with_suffix(file_path.suffix + ".enc")

        await self.encrypt_file(file_path, encrypted_path)

        # Remove original
        file_path.unlink()

        return encrypted_path

    async def decrypt_to_temp(
        self,
        encrypted_path: Union[str, Path],
        temp_dir: Union[str, Path, None] = None,
    ) -> Path:
        """
        Decrypt file to temporary location.

        Args:
            encrypted_path: Path to encrypted file
            temp_dir: Temporary directory (default: system temp)

        Returns:
            Path to temporary decrypted file
        """
        import tempfile

        encrypted_path = Path(encrypted_path)

        if temp_dir:
            temp_dir = Path(temp_dir)
            temp_dir.mkdir(parents=True, exist_ok=True)
        else:
            temp_dir = Path(tempfile.gettempdir())

        # Remove .enc extension for decrypted file
        original_name = encrypted_path.name
        if original_name.endswith(".enc"):
            original_name = original_name[:-4]

        # Create unique temp path
        temp_path = temp_dir / f"dec_{os.urandom(8).hex()}_{original_name}"

        return await self.decrypt_file(encrypted_path, temp_path)


def get_encryption_manager() -> EncryptionManager:
    """
    Get encryption manager with configured key.

    Returns:
        EncryptionManager instance
    """
    from common.config import settings

    return EncryptionManager(settings.encryption_key)
