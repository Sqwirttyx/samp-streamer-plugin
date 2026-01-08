"""Telegram folder parsing utilities."""

import re
from typing import List, Optional, Tuple

from telethon import TelegramClient
from telethon.tl.functions.chatlists import (
    CheckChatlistInviteRequest,
    GetChatlistUpdatesRequest,
    JoinChatlistInviteRequest,
)
from telethon.tl.types import (
    Channel,
    Chat,
    InputChatlistDialogFilter,
    User,
)

from common.exceptions import FolderSyncError, InvalidFolderLinkError
from common.logger import get_logger

logger = get_logger(__name__)


class FolderParser:
    """
    Parser for Telegram chat folders.

    Handles folder link parsing, joining, and chat list extraction.
    """

    # Folder link pattern: https://t.me/addlist/SLUG
    FOLDER_LINK_PATTERN = re.compile(
        r"(?:https?://)?(?:t\.me|telegram\.me)/addlist/([a-zA-Z0-9_-]+)"
    )

    def __init__(self, client: TelegramClient):
        """
        Initialize folder parser.

        Args:
            client: Connected TelegramClient instance
        """
        self.client = client

    @classmethod
    def parse_folder_link(cls, link: str) -> str:
        """
        Extract folder slug from link.

        Args:
            link: Folder invite link

        Returns:
            Folder slug

        Raises:
            InvalidFolderLinkError: If link format is invalid
        """
        match = cls.FOLDER_LINK_PATTERN.search(link)
        if not match:
            raise InvalidFolderLinkError(
                f"Invalid folder link format: {link}. "
                "Expected format: https://t.me/addlist/SLUG"
            )
        return match.group(1)

    async def check_folder(self, folder_slug: str) -> dict:
        """
        Check folder invite without joining.

        Args:
            folder_slug: Folder slug from link

        Returns:
            Dict with folder info (title, chats_count, etc.)

        Raises:
            FolderSyncError: If check fails
        """
        try:
            result = await self.client(
                CheckChatlistInviteRequest(slug=folder_slug)
            )

            return {
                "title": result.title,
                "emoticon": getattr(result, "emoticon", None),
                "chats": result.chats,
                "already_peers": getattr(result, "already_peers", []),
            }

        except Exception as e:
            raise FolderSyncError(f"Failed to check folder: {e}")

    async def join_folder(self, folder_slug: str) -> Tuple[int, List[int]]:
        """
        Join folder and get chat list.

        Args:
            folder_slug: Folder slug from link

        Returns:
            Tuple of (filter_id, chat_ids)

        Raises:
            FolderSyncError: If join fails
        """
        try:
            # First check the folder
            check_result = await self.check_folder(folder_slug)

            # Get peer list from chats
            peers = []
            for chat in check_result["chats"]:
                if isinstance(chat, (Channel, Chat)):
                    peers.append(chat)

            if not peers:
                raise FolderSyncError("Folder contains no accessible chats")

            # Join the folder
            result = await self.client(
                JoinChatlistInviteRequest(
                    slug=folder_slug,
                    peers=peers,
                )
            )

            # Get filter ID from result
            filter_id = result.filter_id

            # Extract chat IDs
            chat_ids = [self._get_chat_id(chat) for chat in check_result["chats"]]
            chat_ids = [cid for cid in chat_ids if cid is not None]

            logger.info(
                f"Joined folder {folder_slug}: filter_id={filter_id}, chats={len(chat_ids)}"
            )

            return filter_id, chat_ids

        except FolderSyncError:
            raise
        except Exception as e:
            raise FolderSyncError(f"Failed to join folder: {e}")

    async def get_folder_chats(self, filter_id: int) -> List[int]:
        """
        Get chat IDs from existing folder.

        Args:
            filter_id: Telegram filter ID

        Returns:
            List of chat IDs

        Raises:
            FolderSyncError: If getting chats fails
        """
        try:
            result = await self.client(
                GetChatlistUpdatesRequest(
                    chatlist=InputChatlistDialogFilter(filter_id=filter_id)
                )
            )

            chat_ids = []
            for chat in getattr(result, "chats", []):
                chat_id = self._get_chat_id(chat)
                if chat_id:
                    chat_ids.append(chat_id)

            return chat_ids

        except Exception as e:
            raise FolderSyncError(f"Failed to get folder chats: {e}")

    async def sync_folder(
        self,
        folder_link: str,
        existing_filter_id: Optional[int] = None,
    ) -> Tuple[int, List[int], str]:
        """
        Sync folder - join if new or update existing.

        Args:
            folder_link: Folder invite link
            existing_filter_id: Existing filter ID if updating

        Returns:
            Tuple of (filter_id, chat_ids, folder_name)

        Raises:
            FolderSyncError: If sync fails
        """
        folder_slug = self.parse_folder_link(folder_link)

        # Check folder first
        folder_info = await self.check_folder(folder_slug)
        folder_name = folder_info.get("title", "Unnamed Folder")

        if existing_filter_id:
            # Try to get existing chats
            try:
                chat_ids = await self.get_folder_chats(existing_filter_id)
                if chat_ids:
                    return existing_filter_id, chat_ids, folder_name
            except Exception:
                pass  # Will rejoin

        # Join folder
        filter_id, chat_ids = await self.join_folder(folder_slug)
        return filter_id, chat_ids, folder_name

    def _get_chat_id(self, entity) -> Optional[int]:
        """
        Extract chat ID from entity.

        Args:
            entity: Telegram entity (Channel, Chat, User)

        Returns:
            Chat ID or None
        """
        if isinstance(entity, Channel):
            return -100 * 10**10 + entity.id  # Supergroup/Channel format
        elif isinstance(entity, Chat):
            return -entity.id  # Group format
        elif isinstance(entity, User):
            return entity.id
        elif hasattr(entity, "id"):
            return entity.id
        return None

    async def get_chat_info(self, chat_id: int) -> Optional[dict]:
        """
        Get info about specific chat.

        Args:
            chat_id: Chat ID

        Returns:
            Dict with chat info or None
        """
        try:
            entity = await self.client.get_entity(chat_id)
            return {
                "id": chat_id,
                "title": getattr(entity, "title", getattr(entity, "first_name", "Unknown")),
                "username": getattr(entity, "username", None),
                "type": type(entity).__name__,
            }
        except Exception as e:
            logger.error(f"Failed to get chat info for {chat_id}: {e}")
            return None

    async def filter_accessible_chats(self, chat_ids: List[int]) -> List[int]:
        """
        Filter list to only accessible chats.

        Args:
            chat_ids: List of chat IDs

        Returns:
            List of accessible chat IDs
        """
        accessible = []

        for chat_id in chat_ids:
            try:
                entity = await self.client.get_entity(chat_id)
                # Check if we can write
                if hasattr(entity, "default_banned_rights"):
                    if entity.default_banned_rights and entity.default_banned_rights.send_messages:
                        continue
                accessible.append(chat_id)
            except Exception:
                continue

        logger.info(f"Filtered chats: {len(accessible)}/{len(chat_ids)} accessible")
        return accessible
