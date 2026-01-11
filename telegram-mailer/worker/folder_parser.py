"""Telegram folder parsing utilities."""

import re
from typing import List, Optional, Tuple

from telethon import TelegramClient
from telethon.tl.functions.chatlists import (
    CheckChatlistInviteRequest,
    GetChatlistUpdatesRequest,
    JoinChatlistInviteRequest,
)
from telethon.tl.functions.messages import GetDialogFiltersRequest
from telethon.tl.types import (
    Channel,
    Chat,
    ChatlistInvite,
    ChatlistInviteAlready,
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

    Supports two scenarios:
    1. New folder (ChatlistInvite) - needs to be joined
    2. Already joined folder (ChatlistInviteAlready) - just get chats
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
            Dict with folder info:
                - title: Folder name
                - chats: List of chat objects
                - already_joined: Whether already joined
                - filter_id: Filter ID (if already joined)

        Raises:
            FolderSyncError: If check fails
        """
        try:
            result = await self.client(
                CheckChatlistInviteRequest(slug=folder_slug)
            )

            # Handle ChatlistInviteAlready (folder already joined)
            if isinstance(result, ChatlistInviteAlready):
                logger.info(f"Folder {folder_slug} already joined, filter_id={result.filter_id}")
                return {
                    "title": None,  # Not available for already joined
                    "chats": getattr(result, "chats", []),
                    "already_joined": True,
                    "filter_id": result.filter_id,
                    "missing_peers": getattr(result, "missing_peers", []),
                    "already_peers": getattr(result, "already_peers", []),
                }

            # Handle ChatlistInvite (new folder)
            if isinstance(result, ChatlistInvite):
                return {
                    "title": result.title,
                    "chats": getattr(result, "chats", []),
                    "already_joined": False,
                    "filter_id": None,
                    "emoticon": getattr(result, "emoticon", None),
                    "peers": getattr(result, "peers", []),
                }

            # Unknown type - try to extract what we can
            logger.warning(f"Unknown check result type: {type(result).__name__}")
            return {
                "title": getattr(result, "title", None),
                "chats": getattr(result, "chats", []),
                "already_joined": hasattr(result, "filter_id"),
                "filter_id": getattr(result, "filter_id", None),
            }

        except Exception as e:
            raise FolderSyncError(f"Failed to check folder: {e}")

    async def get_folder_title_from_filters(self, filter_id: int) -> Optional[str]:
        """
        Get folder title from dialog filters by filter_id.

        Args:
            filter_id: Telegram filter ID

        Returns:
            Folder title or None
        """
        try:
            filters_result = await self.client(GetDialogFiltersRequest())

            for f in getattr(filters_result, 'filters', []):
                if hasattr(f, 'id') and f.id == filter_id:
                    return getattr(f, 'title', None)

            # Also check if filters_result is a list directly
            if isinstance(filters_result, list):
                for f in filters_result:
                    if hasattr(f, 'id') and f.id == filter_id:
                        return getattr(f, 'title', None)

            return None
        except Exception as e:
            logger.warning(f"Could not get folder title: {e}")
            return None

    async def join_folder(self, folder_slug: str) -> Tuple[int, List[int], str]:
        """
        Join folder and get chat list.

        Args:
            folder_slug: Folder slug from link

        Returns:
            Tuple of (filter_id, chat_ids, folder_name)

        Raises:
            FolderSyncError: If join fails
        """
        try:
            # First check the folder
            check_result = await self.check_folder(folder_slug)
            chats = check_result.get("chats", [])

            # If already joined, just return existing data
            if check_result.get("already_joined"):
                filter_id = check_result.get("filter_id", 0)

                # Get folder name from filters
                folder_name = await self.get_folder_title_from_filters(filter_id)
                if not folder_name:
                    folder_name = f"Folder {filter_id}"

                # Extract chat IDs
                chat_ids = [self._get_chat_id(chat) for chat in chats]
                chat_ids = [cid for cid in chat_ids if cid is not None]

                logger.info(
                    f"Folder {folder_slug} already joined: filter_id={filter_id}, chats={len(chat_ids)}"
                )
                return filter_id, chat_ids, folder_name

            # New folder - need to join
            folder_name = check_result.get("title") or "Unnamed Folder"

            # Get peer list from chats
            peers = []
            for chat in chats:
                if isinstance(chat, (Channel, Chat)):
                    peers.append(chat)

            if not peers:
                # Maybe peers are in a different field
                peers = check_result.get("peers", [])

            if not peers:
                raise FolderSyncError("Folder contains no accessible chats")

            # Join the folder
            result = await self.client(
                JoinChatlistInviteRequest(
                    slug=folder_slug,
                    peers=peers,
                )
            )

            # Extract filter_id from result
            filter_id = await self._extract_filter_id(result, folder_name)

            # Extract chat IDs
            chat_ids = [self._get_chat_id(chat) for chat in chats]
            chat_ids = [cid for cid in chat_ids if cid is not None]

            logger.info(
                f"Joined folder {folder_slug}: filter_id={filter_id}, chats={len(chat_ids)}"
            )

            return filter_id, chat_ids, folder_name

        except FolderSyncError:
            raise
        except Exception as e:
            raise FolderSyncError(f"Failed to join folder: {e}")

    async def _extract_filter_id(self, result, folder_title: str = "") -> int:
        """
        Extract filter_id from JoinChatlistInviteRequest result.

        Args:
            result: Result from JoinChatlistInviteRequest
            folder_title: Folder title for matching

        Returns:
            Filter ID or 0 if not found
        """
        filter_id = None

        # Method 1: Direct attribute
        if hasattr(result, 'filter_id'):
            return result.filter_id

        # Method 2: Search in updates
        if hasattr(result, 'updates'):
            for update in result.updates:
                if hasattr(update, 'filter_id'):
                    return update.filter_id
                if hasattr(update, 'filter') and hasattr(update.filter, 'id'):
                    return update.filter.id

        # Method 3: Query dialog filters
        try:
            filters_result = await self.client(GetDialogFiltersRequest())
            filters_list = getattr(filters_result, 'filters', filters_result)

            if isinstance(filters_list, list):
                # Try to find by title
                if folder_title:
                    for f in filters_list:
                        if hasattr(f, 'title') and f.title == folder_title:
                            return f.id

                # Use the last filter (most recently added)
                for f in reversed(filters_list):
                    if hasattr(f, 'id'):
                        return f.id

        except Exception as e:
            logger.warning(f"Could not get filter_id from dialog filters: {e}")

        logger.warning("Could not extract filter_id, using 0")
        return 0

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
        if filter_id == 0:
            raise FolderSyncError("Invalid filter_id (0)")

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

        # Try to get existing chats if we have filter_id
        if existing_filter_id and existing_filter_id > 0:
            try:
                chat_ids = await self.get_folder_chats(existing_filter_id)
                if chat_ids:
                    folder_name = await self.get_folder_title_from_filters(existing_filter_id)
                    folder_name = folder_name or f"Folder {existing_filter_id}"
                    return existing_filter_id, chat_ids, folder_name
            except Exception as e:
                logger.warning(f"Could not get existing folder chats: {e}, will rejoin")

        # Join folder (handles both new and already joined cases)
        return await self.join_folder(folder_slug)

    def _get_chat_id(self, entity) -> Optional[int]:
        """
        Extract chat ID from entity.

        Args:
            entity: Telegram entity (Channel, Chat, User)

        Returns:
            Chat ID or None
        """
        if isinstance(entity, Channel):
            # Channel/Supergroup format: -100{id}
            return int(f"-100{entity.id}")
        elif isinstance(entity, Chat):
            # Group format: -{id}
            return -entity.id
        elif isinstance(entity, User):
            return entity.id
        elif hasattr(entity, "id"):
            # Unknown type but has id
            entity_id = entity.id
            # If it looks like a channel/supergroup (large positive number)
            if entity_id > 0 and len(str(entity_id)) >= 10:
                return int(f"-100{entity_id}")
            return entity_id
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
