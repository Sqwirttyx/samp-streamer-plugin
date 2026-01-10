"""Repository for AdminMessage model."""

import random
from datetime import datetime
from typing import Optional, Sequence
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.admin_message import AdminMessage
from database.repositories.base import BaseRepository


class AdminMessageRepository(BaseRepository[AdminMessage]):
    """Repository for AdminMessage CRUD operations."""

    def __init__(self, session: AsyncSession):
        super().__init__(AdminMessage, session)

    async def get_active(self) -> Sequence[AdminMessage]:
        """
        Get all active admin messages.

        Returns:
            List of active AdminMessage
        """
        result = await self.session.execute(
            select(AdminMessage)
            .where(AdminMessage.is_active == True)
            .order_by(AdminMessage.priority.desc())
        )
        return result.scalars().all()

    async def get_random_active(self) -> Optional[AdminMessage]:
        """
        Get random active admin message weighted by priority.

        Returns:
            Random AdminMessage or None
        """
        messages = await self.get_active()
        if not messages:
            return None

        # Weight by priority
        weighted = []
        for msg in messages:
            weighted.extend([msg] * msg.priority)

        return random.choice(weighted)

    async def create(
        self,
        name: str,
        message_text: Optional[str] = None,
        message_media: Optional[dict] = None,
        priority: int = 1,
        footer_text: Optional[str] = None,
        target_folders: Optional[dict] = None,
    ) -> AdminMessage:
        """
        Create new admin message template.

        Args:
            name: Template name
            message_text: Message text
            message_media: Media dict
            priority: Priority level
            footer_text: Optional footer
            target_folders: Optional targeting

        Returns:
            Created AdminMessage
        """
        message = AdminMessage(
            name=name,
            message_text=message_text,
            message_media=message_media,
            priority=priority,
            footer_text=footer_text,
            target_folders=target_folders,
            is_active=True,
            usage_count=0,
        )
        self.session.add(message)
        await self.session.flush()
        return message

    async def update_message(
        self,
        message_id: UUID,
        name: Optional[str] = None,
        message_text: Optional[str] = None,
        message_media: Optional[dict] = None,
        priority: Optional[int] = None,
        footer_text: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> Optional[AdminMessage]:
        """
        Update admin message.

        Args:
            message_id: Message UUID
            **kwargs: Fields to update

        Returns:
            Updated AdminMessage or None
        """
        message = await self.get_by_id(message_id)
        if not message:
            return None

        if name is not None:
            message.name = name
        if message_text is not None:
            message.message_text = message_text
        if message_media is not None:
            message.message_media = message_media
        if priority is not None:
            message.priority = priority
        if footer_text is not None:
            message.footer_text = footer_text
        if is_active is not None:
            message.is_active = is_active

        await self.session.flush()
        return message

    async def toggle_active(self, message_id: UUID) -> Optional[AdminMessage]:
        """
        Toggle active status.

        Args:
            message_id: Message UUID

        Returns:
            Updated AdminMessage or None
        """
        message = await self.get_by_id(message_id)
        if not message:
            return None

        message.is_active = not message.is_active
        await self.session.flush()
        return message

    async def record_usage(self, message_id: UUID) -> None:
        """
        Record template usage.

        Args:
            message_id: Message UUID
        """
        await self.session.execute(
            update(AdminMessage)
            .where(AdminMessage.id == message_id)
            .values(
                usage_count=AdminMessage.usage_count + 1,
                last_used_at=datetime.utcnow(),
            )
        )

    async def count_active(self) -> int:
        """
        Count active templates.

        Returns:
            Number of active templates
        """
        result = await self.session.execute(
            select(func.count())
            .select_from(AdminMessage)
            .where(AdminMessage.is_active == True)
        )
        return result.scalar() or 0

    async def get_stats(self) -> dict:
        """
        Get admin messages statistics.

        Returns:
            Stats dict
        """
        total_result = await self.session.execute(
            select(func.count()).select_from(AdminMessage)
        )
        active_result = await self.session.execute(
            select(func.count())
            .select_from(AdminMessage)
            .where(AdminMessage.is_active == True)
        )
        usage_result = await self.session.execute(
            select(func.sum(AdminMessage.usage_count))
            .select_from(AdminMessage)
        )

        return {
            "total": total_result.scalar() or 0,
            "active": active_result.scalar() or 0,
            "total_usage": usage_result.scalar() or 0,
        }
