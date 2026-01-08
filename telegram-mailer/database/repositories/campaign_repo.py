"""Campaign repository."""

from datetime import datetime
from typing import Optional, Sequence
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

from common.constants import CampaignStatus
from database.models.campaign import Campaign, CampaignProgress
from database.repositories.base import BaseRepository


class CampaignRepository(BaseRepository[Campaign]):
    """Repository for Campaign model operations."""

    model = Campaign

    async def get_by_user(
        self,
        user_id: UUID,
        status: Optional[CampaignStatus] = None,
        offset: int = 0,
        limit: int = 100,
    ) -> Sequence[Campaign]:
        """
        Get campaigns by user ID.

        Args:
            user_id: User UUID
            status: Filter by status (optional)
            offset: Pagination offset
            limit: Pagination limit

        Returns:
            List of campaigns
        """
        query = select(Campaign).where(Campaign.user_id == user_id)

        if status:
            query = query.where(Campaign.status == status)

        query = query.offset(offset).limit(limit)
        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_with_progress(self, campaign_id: UUID) -> Optional[Campaign]:
        """
        Get campaign with progress data.

        Args:
            campaign_id: Campaign UUID

        Returns:
            Campaign with progress or None
        """
        result = await self.session.execute(
            select(Campaign)
            .options(selectinload(Campaign.progress))
            .where(Campaign.id == campaign_id)
        )
        return result.scalar_one_or_none()

    async def get_active(self) -> Sequence[Campaign]:
        """
        Get all active campaigns.

        Returns:
            List of active campaigns
        """
        result = await self.session.execute(
            select(Campaign)
            .options(selectinload(Campaign.progress))
            .where(Campaign.status == CampaignStatus.ACTIVE)
        )
        return result.scalars().all()

    async def get_active_by_user(self, user_id: UUID) -> Sequence[Campaign]:
        """
        Get active campaigns for user.

        Args:
            user_id: User UUID

        Returns:
            List of active campaigns
        """
        return await self.get_by_user(user_id, status=CampaignStatus.ACTIVE)

    async def get_admin_campaigns(self) -> Sequence[Campaign]:
        """
        Get all admin campaigns.

        Returns:
            List of admin campaigns
        """
        result = await self.session.execute(
            select(Campaign)
            .where(
                Campaign.is_admin_campaign == True,
                Campaign.status == CampaignStatus.ACTIVE,
            )
        )
        return result.scalars().all()

    async def update_status(
        self,
        campaign_id: UUID,
        status: CampaignStatus,
    ) -> Optional[Campaign]:
        """
        Update campaign status.

        Args:
            campaign_id: Campaign UUID
            status: New status

        Returns:
            Updated campaign or None
        """
        values = {"status": status}

        if status == CampaignStatus.ACTIVE:
            values["started_at"] = datetime.utcnow()
        elif status in (CampaignStatus.COMPLETED, CampaignStatus.ERROR):
            values["completed_at"] = datetime.utcnow()

        await self.session.execute(
            update(Campaign)
            .where(Campaign.id == campaign_id)
            .values(**values)
        )
        await self.session.flush()
        return await self.get_by_id(campaign_id)

    async def start(self, campaign_id: UUID) -> Optional[Campaign]:
        """
        Start campaign.

        Args:
            campaign_id: Campaign UUID

        Returns:
            Updated campaign or None
        """
        campaign = await self.get_by_id(campaign_id)
        if not campaign or not campaign.can_start:
            return None

        # Create progress record if not exists
        progress = await self.get_progress(campaign_id)
        if not progress:
            await self.create_progress(campaign_id)

        return await self.update_status(campaign_id, CampaignStatus.ACTIVE)

    async def pause(self, campaign_id: UUID) -> Optional[Campaign]:
        """
        Pause campaign.

        Args:
            campaign_id: Campaign UUID

        Returns:
            Updated campaign or None
        """
        campaign = await self.get_by_id(campaign_id)
        if not campaign or not campaign.can_pause:
            return None
        return await self.update_status(campaign_id, CampaignStatus.PAUSED)

    async def stop(self, campaign_id: UUID) -> Optional[Campaign]:
        """
        Stop campaign (mark as completed).

        Args:
            campaign_id: Campaign UUID

        Returns:
            Updated campaign or None
        """
        return await self.update_status(campaign_id, CampaignStatus.COMPLETED)

    async def mark_error(self, campaign_id: UUID) -> Optional[Campaign]:
        """
        Mark campaign as error.

        Args:
            campaign_id: Campaign UUID

        Returns:
            Updated campaign or None
        """
        return await self.update_status(campaign_id, CampaignStatus.ERROR)

    # Progress methods
    async def get_progress(self, campaign_id: UUID) -> Optional[CampaignProgress]:
        """
        Get campaign progress.

        Args:
            campaign_id: Campaign UUID

        Returns:
            Campaign progress or None
        """
        result = await self.session.execute(
            select(CampaignProgress)
            .where(CampaignProgress.campaign_id == campaign_id)
        )
        return result.scalar_one_or_none()

    async def create_progress(self, campaign_id: UUID) -> CampaignProgress:
        """
        Create campaign progress record.

        Args:
            campaign_id: Campaign UUID

        Returns:
            Created progress record
        """
        progress = CampaignProgress(
            campaign_id=campaign_id,
            current_chat_index=0,
            cycle_count=0,
        )
        self.session.add(progress)
        await self.session.flush()
        await self.session.refresh(progress)
        return progress

    async def update_progress(
        self,
        campaign_id: UUID,
        current_chat_index: int,
        cycle_count: Optional[int] = None,
        next_send_at: Optional[datetime] = None,
    ) -> Optional[CampaignProgress]:
        """
        Update campaign progress.

        Args:
            campaign_id: Campaign UUID
            current_chat_index: Current chat index
            cycle_count: Cycle count (optional)
            next_send_at: Next send time (optional)

        Returns:
            Updated progress or None
        """
        values = {
            "current_chat_index": current_chat_index,
            "last_sent_at": datetime.utcnow(),
        }

        if cycle_count is not None:
            values["cycle_count"] = cycle_count

        if next_send_at is not None:
            values["next_send_at"] = next_send_at

        await self.session.execute(
            update(CampaignProgress)
            .where(CampaignProgress.campaign_id == campaign_id)
            .values(**values)
        )
        await self.session.flush()
        return await self.get_progress(campaign_id)

    async def count_by_user(self, user_id: UUID) -> int:
        """
        Count campaigns for user.

        Args:
            user_id: User UUID

        Returns:
            Number of campaigns
        """
        return await self.count(user_id=user_id)

    async def get_by_account(self, account_id: UUID) -> Sequence[Campaign]:
        """
        Get campaigns using specific account.

        Args:
            account_id: Account UUID

        Returns:
            List of campaigns
        """
        result = await self.session.execute(
            select(Campaign).where(Campaign.account_id == account_id)
        )
        return result.scalars().all()
