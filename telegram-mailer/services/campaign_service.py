"""Campaign service - business logic for campaign management."""

from datetime import time
from typing import Optional
from uuid import UUID

from common.constants import CampaignStatus
from common.exceptions import NotFoundError, ValidationError
from common.logger import get_logger
from database import get_db_manager
from database.models import Campaign
from database.repositories import (
    CampaignRepository,
    AccountRepository,
    FolderRepository,
)
from redis_client import get_redis_manager
from redis_client.queue import QueueManager
from storage import MediaStorage

logger = get_logger(__name__)


class CampaignService:
    """
    Service for campaign management.

    Handles campaign lifecycle, queue management, and execution.
    """

    def __init__(self):
        """Initialize campaign service."""
        self.media_storage = MediaStorage()

    async def get_by_id(
        self,
        campaign_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> Optional[Campaign]:
        """
        Get campaign by ID.

        Args:
            campaign_id: Campaign UUID
            user_id: Owner user ID (optional, for validation)

        Returns:
            Campaign or None
        """
        db_manager = get_db_manager()

        async with db_manager.readonly_session() as session:
            repo = CampaignRepository(session)
            campaign = await repo.get_with_progress(campaign_id)

            if campaign and user_id and campaign.user_id != user_id:
                return None

            return campaign

    async def get_user_campaigns(
        self,
        user_id: UUID,
        status: Optional[CampaignStatus] = None,
    ) -> list[Campaign]:
        """
        Get all campaigns for user.

        Args:
            user_id: User UUID
            status: Filter by status (optional)

        Returns:
            List of campaigns
        """
        db_manager = get_db_manager()

        async with db_manager.readonly_session() as session:
            repo = CampaignRepository(session)
            return await repo.get_by_user(user_id, status=status)

    async def create_campaign(
        self,
        user_id: UUID,
        account_id: UUID,
        folder_id: UUID,
        message_text: str,
        message_media: Optional[dict] = None,
        interval_min: int = 25,
        interval_max: int = 45,
        work_hours: Optional[tuple[time, time]] = None,
        rest_minutes: int = 15,
    ) -> Campaign:
        """
        Create new campaign.

        Args:
            user_id: Owner user ID
            account_id: Account to use
            folder_id: Folder with target chats
            message_text: Message text
            message_media: Media configuration (optional)
            interval_min: Minimum interval between messages
            interval_max: Maximum interval between messages
            work_hours: Work hours tuple (start, end)
            rest_minutes: Rest duration after work period

        Returns:
            Created campaign

        Raises:
            ValidationError: If validation fails
            NotFoundError: If account or folder not found
        """
        # Validate inputs
        if not message_text or len(message_text.strip()) == 0:
            raise ValidationError("Message text is required")

        if interval_min < 10:
            raise ValidationError("Minimum interval must be at least 10 seconds")

        if interval_max <= interval_min:
            raise ValidationError("Maximum interval must be greater than minimum")

        db_manager = get_db_manager()

        async with db_manager.session() as session:
            # Verify account belongs to user
            account_repo = AccountRepository(session)
            account = await account_repo.get_by_id(account_id)

            if not account or account.user_id != user_id:
                raise NotFoundError("Account not found")

            # Verify folder belongs to user and has chats
            folder_repo = FolderRepository(session)
            folder = await folder_repo.get_by_id(folder_id)

            if not folder or folder.user_id != user_id:
                raise NotFoundError("Folder not found")

            if not folder.chat_ids:
                raise ValidationError("Folder has no chats. Please sync first.")

            # Format work hours
            work_hours_dict = None
            if work_hours:
                work_hours_dict = {
                    "start": work_hours[0].isoformat(),
                    "end": work_hours[1].isoformat(),
                }

            # Create campaign
            campaign_repo = CampaignRepository(session)
            campaign = await campaign_repo.create(
                user_id=user_id,
                account_id=account_id,
                folder_id=folder_id,
                message_text=message_text,
                message_media=message_media,
                interval_min=interval_min,
                interval_max=interval_max,
                work_hours=work_hours_dict,
                rest_minutes=rest_minutes,
                total_chats=len(folder.chat_ids),
            )

            logger.info(f"Campaign created: {campaign.id} for user {user_id}")
            return campaign

    async def start_campaign(
        self,
        campaign_id: UUID,
        user_id: UUID,
    ) -> Campaign:
        """
        Start campaign (add to queue).

        Args:
            campaign_id: Campaign UUID
            user_id: Owner user ID

        Returns:
            Updated campaign
        """
        campaign = await self.get_by_id(campaign_id, user_id)
        if not campaign:
            raise NotFoundError("Campaign not found")

        if campaign.status not in (CampaignStatus.DRAFT, CampaignStatus.PAUSED):
            raise ValidationError(
                f"Cannot start campaign with status {campaign.status.value}"
            )

        # Add to Redis queue
        redis_manager = get_redis_manager()
        queue_manager = QueueManager(redis_manager.client)
        await queue_manager.add_campaign(campaign_id, user_id)

        # Update status
        db_manager = get_db_manager()

        async with db_manager.session() as session:
            repo = CampaignRepository(session)
            campaign = await repo.update_status(campaign_id, CampaignStatus.QUEUED)

        logger.info(f"Campaign started: {campaign_id}")
        return campaign

    async def pause_campaign(
        self,
        campaign_id: UUID,
        user_id: UUID,
    ) -> Campaign:
        """
        Pause running campaign.

        Args:
            campaign_id: Campaign UUID
            user_id: Owner user ID

        Returns:
            Updated campaign
        """
        campaign = await self.get_by_id(campaign_id, user_id)
        if not campaign:
            raise NotFoundError("Campaign not found")

        if campaign.status not in (CampaignStatus.ACTIVE, CampaignStatus.QUEUED):
            raise ValidationError(
                f"Cannot pause campaign with status {campaign.status.value}"
            )

        # Remove from queue if queued
        redis_manager = get_redis_manager()
        queue_manager = QueueManager(redis_manager.client)
        await queue_manager.remove_campaign(campaign_id)

        # Update status
        db_manager = get_db_manager()

        async with db_manager.session() as session:
            repo = CampaignRepository(session)
            campaign = await repo.update_status(campaign_id, CampaignStatus.PAUSED)

        logger.info(f"Campaign paused: {campaign_id}")
        return campaign

    async def stop_campaign(
        self,
        campaign_id: UUID,
        user_id: UUID,
    ) -> Campaign:
        """
        Stop campaign completely.

        Args:
            campaign_id: Campaign UUID
            user_id: Owner user ID

        Returns:
            Updated campaign
        """
        campaign = await self.get_by_id(campaign_id, user_id)
        if not campaign:
            raise NotFoundError("Campaign not found")

        # Remove from queue
        redis_manager = get_redis_manager()
        queue_manager = QueueManager(redis_manager.client)
        await queue_manager.remove_campaign(campaign_id)
        await queue_manager.mark_campaign_inactive(campaign_id)

        # Update status
        db_manager = get_db_manager()

        async with db_manager.session() as session:
            repo = CampaignRepository(session)
            campaign = await repo.stop(campaign_id)

        logger.info(f"Campaign stopped: {campaign_id}")
        return campaign

    async def delete_campaign(
        self,
        campaign_id: UUID,
        user_id: UUID,
    ) -> bool:
        """
        Delete campaign.

        Args:
            campaign_id: Campaign UUID
            user_id: Owner user ID

        Returns:
            True if deleted
        """
        campaign = await self.get_by_id(campaign_id, user_id)
        if not campaign:
            raise NotFoundError("Campaign not found")

        # Stop if active
        if campaign.status in (CampaignStatus.ACTIVE, CampaignStatus.QUEUED):
            await self.stop_campaign(campaign_id, user_id)

        # Delete media if exists
        if campaign.message_media:
            media_path = campaign.message_media.get("path")
            if media_path:
                await self.media_storage.delete_media(media_path)

        db_manager = get_db_manager()

        async with db_manager.session() as session:
            repo = CampaignRepository(session)
            result = await repo.delete(campaign_id)

            if result:
                logger.info(f"Campaign deleted: {campaign_id}")

            return result

    async def get_campaign_progress(
        self,
        campaign_id: UUID,
        user_id: UUID,
    ) -> dict:
        """
        Get campaign progress.

        Args:
            campaign_id: Campaign UUID
            user_id: Owner user ID

        Returns:
            Progress dictionary
        """
        campaign = await self.get_by_id(campaign_id, user_id)
        if not campaign:
            raise NotFoundError("Campaign not found")

        progress = campaign.progress
        total = campaign.total_chats or 0

        sent = 0
        success = 0
        failed = 0

        if progress:
            sent = progress.sent_count or 0
            success = progress.success_count or 0
            failed = progress.failed_count or 0

        pending = max(0, total - sent)
        percentage = (sent / total * 100) if total > 0 else 0

        return {
            "campaign_id": str(campaign_id),
            "status": campaign.status.value,
            "total": total,
            "sent": sent,
            "success": success,
            "failed": failed,
            "pending": pending,
            "percentage": round(percentage, 1),
        }

    async def save_media(
        self,
        campaign_id: UUID,
        user_id: UUID,
        media_data: bytes,
        media_type: str,
        filename: str,
    ) -> dict:
        """
        Save media for campaign.

        Args:
            campaign_id: Campaign UUID
            user_id: Owner user ID
            media_data: Media file content
            media_type: Type (photo, video, document)
            filename: Original filename

        Returns:
            Media configuration dict
        """
        campaign = await self.get_by_id(campaign_id, user_id)
        if not campaign:
            raise NotFoundError("Campaign not found")

        # Save media file
        media_path = await self.media_storage.save_media(
            media_data=media_data,
            campaign_id=campaign_id,
            media_type=media_type,
            filename=filename,
        )

        # Build media config
        media_config = {
            "type": media_type,
            "path": media_path,
            "filename": filename,
        }

        # Update campaign
        db_manager = get_db_manager()

        async with db_manager.session() as session:
            repo = CampaignRepository(session)
            campaign = await repo.get_by_id(campaign_id)
            campaign.message_media = media_config
            await session.flush()

        logger.info(f"Media saved for campaign {campaign_id}: {media_type}")
        return media_config

    async def get_active_campaigns(self, user_id: UUID) -> list[Campaign]:
        """
        Get active campaigns for user.

        Args:
            user_id: User UUID

        Returns:
            List of active campaigns
        """
        return await self.get_user_campaigns(user_id, status=CampaignStatus.ACTIVE)

    async def get_queue_position(
        self,
        campaign_id: UUID,
    ) -> Optional[int]:
        """
        Get campaign position in queue.

        Args:
            campaign_id: Campaign UUID

        Returns:
            Queue position (1-based) or None if not in queue
        """
        redis_manager = get_redis_manager()
        queue_manager = QueueManager(redis_manager.client)
        return await queue_manager.get_campaign_position(campaign_id)

    def format_campaign(self, campaign: Campaign) -> str:
        """
        Format campaign for display.

        Args:
            campaign: Campaign model

        Returns:
            Formatted string
        """
        status_emoji = {
            CampaignStatus.DRAFT: "📝",
            CampaignStatus.QUEUED: "⏳",
            CampaignStatus.ACTIVE: "▶️",
            CampaignStatus.PAUSED: "⏸️",
            CampaignStatus.COMPLETED: "✅",
            CampaignStatus.ERROR: "❌",
        }

        emoji = status_emoji.get(campaign.status, "❓")
        total = campaign.total_chats or 0

        progress_text = ""
        if campaign.progress:
            sent = campaign.progress.sent_count or 0
            progress_text = f" ({sent}/{total})"

        return f"{emoji} Кампания #{campaign.id.hex[:8]}{progress_text}"
