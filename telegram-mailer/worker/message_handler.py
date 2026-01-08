"""Message handling utilities for Telethon worker."""

from typing import Any, List, Optional, Tuple, Union

from telethon import TelegramClient
from telethon.tl.types import (
    InputMediaPhoto,
    InputMediaDocument,
    Message,
    MessageEntityBold,
    MessageEntityCode,
    MessageEntityItalic,
    MessageEntityTextUrl,
    MessageMediaDocument,
    MessageMediaPhoto,
)

from common.logger import get_logger

logger = get_logger(__name__)


class MessageHandler:
    """
    Handler for message operations in Telethon.

    Handles message preparation, sending, and media management.
    """

    def __init__(self, client: TelegramClient):
        """
        Initialize message handler.

        Args:
            client: Connected TelegramClient instance
        """
        self.client = client

    async def save_to_favorites(
        self,
        text: Optional[str] = None,
        media: Optional[Any] = None,
        entities: Optional[List] = None,
    ) -> Message:
        """
        Save message to Saved Messages (favorites).

        Args:
            text: Message text
            media: Media file or file_id
            entities: Text formatting entities

        Returns:
            Saved message object
        """
        return await self.client.send_message(
            "me",
            text or "",
            file=media,
            formatting_entities=entities,
        )

    async def get_from_favorites(self, message_id: int) -> Optional[Message]:
        """
        Get message from Saved Messages.

        Args:
            message_id: Message ID

        Returns:
            Message object or None
        """
        try:
            messages = await self.client.get_messages("me", ids=message_id)
            return messages if isinstance(messages, Message) else None
        except Exception as e:
            logger.error(f"Failed to get message from favorites: {e}")
            return None

    def prepare_message(
        self,
        message: Message,
    ) -> Tuple[Optional[str], Optional[Any], Optional[List]]:
        """
        Prepare message components for sending.

        Args:
            message: Source message

        Returns:
            Tuple of (text, media, entities)
        """
        text = message.text or message.message
        media = None
        entities = message.entities

        # Handle media
        if message.media:
            if isinstance(message.media, MessageMediaPhoto):
                media = message.media.photo
            elif isinstance(message.media, MessageMediaDocument):
                media = message.media.document

        return text, media, entities

    async def send_message(
        self,
        chat_id: int,
        text: Optional[str] = None,
        media: Optional[Any] = None,
        entities: Optional[List] = None,
    ) -> Tuple[bool, Optional[str]]:
        """
        Send message to chat.

        This sends as a new message (not forward) to avoid
        "Forwarded from" label.

        Args:
            chat_id: Target chat ID
            text: Message text
            media: Media file
            entities: Formatting entities

        Returns:
            Tuple of (success, error_message)
        """
        try:
            await self.client.send_message(
                chat_id,
                text or "",
                file=media,
                formatting_entities=entities,
            )
            return True, None

        except Exception as e:
            error_type = type(e).__name__
            error_msg = str(e)
            logger.error(f"Failed to send to {chat_id}: {error_type}: {error_msg}")
            return False, f"{error_type}: {error_msg}"

    async def send_from_saved(
        self,
        chat_id: int,
        saved_message_id: int,
        append_text: Optional[str] = None,
    ) -> Tuple[bool, Optional[str]]:
        """
        Send message from Saved Messages to chat.

        Args:
            chat_id: Target chat ID
            saved_message_id: Message ID in Saved Messages
            append_text: Text to append (e.g., admin footer)

        Returns:
            Tuple of (success, error_message)
        """
        # Get original message
        message = await self.get_from_favorites(saved_message_id)
        if not message:
            return False, "Source message not found"

        text, media, entities = self.prepare_message(message)

        # Append footer if provided
        if append_text:
            if text:
                text = f"{text}\n\n{append_text}"
            else:
                text = append_text

        return await self.send_message(chat_id, text, media, entities)

    async def send_with_media_dict(
        self,
        chat_id: int,
        text: Optional[str],
        media_dict: Optional[dict],
    ) -> Tuple[bool, Optional[str]]:
        """
        Send message with media from dict format (from database).

        Args:
            chat_id: Target chat ID
            text: Message text
            media_dict: Media dict with type and file_id

        Returns:
            Tuple of (success, error_message)
        """
        media = None

        if media_dict:
            media_type = media_dict.get("type")
            file_id = media_dict.get("file_id")

            if file_id:
                # For Telegram file_ids, we can send directly
                media = file_id

        return await self.send_message(chat_id, text, media)

    async def test_send_ability(self, chat_id: int) -> Tuple[bool, Optional[str]]:
        """
        Test if we can send messages to chat.

        This doesn't actually send, just checks permissions.

        Args:
            chat_id: Chat ID to test

        Returns:
            Tuple of (can_send, error_reason)
        """
        try:
            entity = await self.client.get_entity(chat_id)

            # Check for ban
            if hasattr(entity, "default_banned_rights"):
                rights = entity.default_banned_rights
                if rights and rights.send_messages:
                    return False, "Sending messages is restricted"

            # Check if kicked/left
            if hasattr(entity, "left") and entity.left:
                return False, "Left the chat"

            if hasattr(entity, "kicked") and entity.kicked:
                return False, "Kicked from chat"

            return True, None

        except Exception as e:
            return False, str(e)

    async def delete_message(self, chat_id: int, message_id: int) -> bool:
        """
        Delete message from chat.

        Args:
            chat_id: Chat ID
            message_id: Message ID

        Returns:
            True if deleted
        """
        try:
            await self.client.delete_messages(chat_id, message_id)
            return True
        except Exception as e:
            logger.error(f"Failed to delete message: {e}")
            return False

    async def edit_message(
        self,
        chat_id: int,
        message_id: int,
        new_text: str,
    ) -> bool:
        """
        Edit message text.

        Args:
            chat_id: Chat ID
            message_id: Message ID
            new_text: New text

        Returns:
            True if edited
        """
        try:
            await self.client.edit_message(chat_id, message_id, new_text)
            return True
        except Exception as e:
            logger.error(f"Failed to edit message: {e}")
            return False
