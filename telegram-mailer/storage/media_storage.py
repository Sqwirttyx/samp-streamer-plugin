"""Media file storage management."""

import hashlib
import mimetypes
import os
from pathlib import Path
from typing import Optional, Union
from uuid import UUID

import aiofiles

from common.logger import get_logger

logger = get_logger(__name__)


class MediaStorage:
    """
    Manager for campaign media file storage.

    Handles storage and retrieval of images, videos, and documents
    for campaign messages.

    Storage structure:
        {base_path}/{campaign_id}/{media_id}.{ext}
    """

    ALLOWED_EXTENSIONS = {
        # Images
        ".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp",
        # Videos
        ".mp4", ".avi", ".mov", ".webm", ".mkv",
        # Documents
        ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".txt",
        # Audio
        ".mp3", ".ogg", ".wav", ".flac",
    }

    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB

    def __init__(self, base_path: Union[str, Path]):
        """
        Initialize media storage.

        Args:
            base_path: Base directory for media storage
        """
        self.base_path = Path(base_path)

    def _campaign_dir(self, campaign_id: UUID) -> Path:
        """Get campaign's media directory."""
        return self.base_path / str(campaign_id)

    def _media_path(
        self,
        campaign_id: UUID,
        media_id: str,
        extension: str,
    ) -> Path:
        """Get path for media file."""
        return self._campaign_dir(campaign_id) / f"{media_id}{extension}"

    @staticmethod
    def generate_media_id(data: bytes) -> str:
        """
        Generate unique media ID from content hash.

        Args:
            data: File data

        Returns:
            Media ID string
        """
        return hashlib.sha256(data).hexdigest()[:16]

    @staticmethod
    def get_extension(filename: str) -> str:
        """Get file extension from filename."""
        return Path(filename).suffix.lower()

    @staticmethod
    def get_mime_type(path: Path) -> str:
        """Get MIME type for file."""
        mime_type, _ = mimetypes.guess_type(str(path))
        return mime_type or "application/octet-stream"

    def validate_file(
        self,
        data: bytes,
        filename: str,
    ) -> tuple[bool, Optional[str]]:
        """
        Validate file for storage.

        Args:
            data: File data
            filename: Original filename

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check size
        if len(data) > self.MAX_FILE_SIZE:
            return False, f"File too large: {len(data)} bytes (max {self.MAX_FILE_SIZE})"

        # Check extension
        ext = self.get_extension(filename)
        if ext not in self.ALLOWED_EXTENSIONS:
            return False, f"Invalid file type: {ext}"

        return True, None

    async def save_media(
        self,
        campaign_id: UUID,
        data: bytes,
        filename: str,
    ) -> dict:
        """
        Save media file.

        Args:
            campaign_id: Campaign UUID
            data: File data
            filename: Original filename

        Returns:
            Dictionary with media info (id, path, size, mime_type)

        Raises:
            ValueError: If file validation fails
        """
        is_valid, error = self.validate_file(data, filename)
        if not is_valid:
            raise ValueError(error)

        media_id = self.generate_media_id(data)
        extension = self.get_extension(filename)
        media_path = self._media_path(campaign_id, media_id, extension)

        # Create directory
        media_path.parent.mkdir(parents=True, exist_ok=True)

        # Save file
        async with aiofiles.open(media_path, "wb") as f:
            await f.write(data)

        logger.info(f"Media saved: {media_path}")

        return {
            "id": media_id,
            "path": str(media_path),
            "filename": filename,
            "extension": extension,
            "size": len(data),
            "mime_type": self.get_mime_type(media_path),
        }

    async def save_media_from_file(
        self,
        campaign_id: UUID,
        source_path: Union[str, Path],
    ) -> dict:
        """
        Save media from existing file.

        Args:
            campaign_id: Campaign UUID
            source_path: Path to source file

        Returns:
            Dictionary with media info
        """
        source_path = Path(source_path)

        async with aiofiles.open(source_path, "rb") as f:
            data = await f.read()

        return await self.save_media(
            campaign_id=campaign_id,
            data=data,
            filename=source_path.name,
        )

    async def get_media(
        self,
        campaign_id: UUID,
        media_id: str,
    ) -> Optional[Path]:
        """
        Get media file path.

        Args:
            campaign_id: Campaign UUID
            media_id: Media ID

        Returns:
            Path to media file or None if not found
        """
        campaign_dir = self._campaign_dir(campaign_id)
        if not campaign_dir.exists():
            return None

        # Search for file with any extension
        for file in campaign_dir.iterdir():
            if file.stem == media_id:
                return file

        return None

    async def get_media_data(
        self,
        campaign_id: UUID,
        media_id: str,
    ) -> Optional[bytes]:
        """
        Get media file data.

        Args:
            campaign_id: Campaign UUID
            media_id: Media ID

        Returns:
            File data or None if not found
        """
        path = await self.get_media(campaign_id, media_id)
        if not path:
            return None

        async with aiofiles.open(path, "rb") as f:
            return await f.read()

    async def delete_media(
        self,
        campaign_id: UUID,
        media_id: str,
    ) -> bool:
        """
        Delete media file.

        Args:
            campaign_id: Campaign UUID
            media_id: Media ID

        Returns:
            True if deleted, False if not found
        """
        path = await self.get_media(campaign_id, media_id)
        if path:
            path.unlink()
            logger.info(f"Media deleted: {path}")
            return True
        return False

    async def delete_campaign_media(self, campaign_id: UUID) -> int:
        """
        Delete all media for campaign.

        Args:
            campaign_id: Campaign UUID

        Returns:
            Number of files deleted
        """
        campaign_dir = self._campaign_dir(campaign_id)
        if not campaign_dir.exists():
            return 0

        count = 0
        for file in campaign_dir.iterdir():
            file.unlink()
            count += 1

        # Remove directory
        campaign_dir.rmdir()
        logger.info(f"Campaign media deleted: {count} files from {campaign_id}")

        return count

    async def list_campaign_media(self, campaign_id: UUID) -> list[dict]:
        """
        List all media for campaign.

        Args:
            campaign_id: Campaign UUID

        Returns:
            List of media info dictionaries
        """
        campaign_dir = self._campaign_dir(campaign_id)
        if not campaign_dir.exists():
            return []

        media_list = []
        for file in campaign_dir.iterdir():
            stat = file.stat()
            media_list.append({
                "id": file.stem,
                "path": str(file),
                "extension": file.suffix,
                "size": stat.st_size,
                "mime_type": self.get_mime_type(file),
            })

        return media_list

    async def get_total_size(self, campaign_id: UUID) -> int:
        """
        Get total size of campaign media.

        Args:
            campaign_id: Campaign UUID

        Returns:
            Total size in bytes
        """
        campaign_dir = self._campaign_dir(campaign_id)
        if not campaign_dir.exists():
            return 0

        return sum(f.stat().st_size for f in campaign_dir.iterdir())

    async def cleanup_orphaned(self, valid_campaign_ids: set[str]) -> int:
        """
        Clean up media for deleted campaigns.

        Args:
            valid_campaign_ids: Set of valid campaign ID strings

        Returns:
            Number of directories cleaned up
        """
        if not self.base_path.exists():
            return 0

        count = 0
        for dir_path in self.base_path.iterdir():
            if dir_path.is_dir() and dir_path.name not in valid_campaign_ids:
                # Delete all files in directory
                for file in dir_path.iterdir():
                    file.unlink()
                dir_path.rmdir()
                count += 1
                logger.info(f"Orphaned media cleaned: {dir_path}")

        return count


def get_media_storage() -> MediaStorage:
    """
    Get media storage with configured path.

    Returns:
        MediaStorage instance
    """
    from common.config import settings

    return MediaStorage(settings.media_path)
