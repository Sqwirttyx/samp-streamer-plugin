"""Main scheduler for campaign management."""

import asyncio
from datetime import datetime
from typing import Optional

from common.constants import CampaignStatus, WindowType
from common.logger import get_logger
from core.scheduler.cycle_manager import CycleManager, get_cycle_manager
from database import get_db_manager
from database.repositories import CampaignRepository, UserRepository
from redis_client import get_redis_manager
from redis_client.queue import QueueManager

logger = get_logger(__name__)


class Scheduler:
    """
    Main scheduler for managing campaigns.

    Responsibilities:
    - Monitor scheduled campaigns and activate them
    - Handle 16/8 window switching
    - Manage campaign queue
    """

    CHECK_INTERVAL = 60  # seconds

    def __init__(self):
        """Initialize scheduler."""
        self._running = False
        self.cycle_manager: CycleManager = get_cycle_manager()
        self.queue_manager: Optional[QueueManager] = None
        self._last_window: Optional[WindowType] = None

    async def start(self) -> None:
        """Start scheduler."""
        logger.info("Scheduler starting...")

        redis_manager = get_redis_manager()
        await redis_manager.init()

        self.queue_manager = QueueManager(redis_manager.client)
        self._running = True
        self._last_window = self.cycle_manager.get_current_window()

        logger.info(f"Scheduler started. Current window: {self._last_window.value}")

    async def stop(self) -> None:
        """Stop scheduler."""
        logger.info("Scheduler stopping...")
        self._running = False

        redis_manager = get_redis_manager()
        await redis_manager.close()

        logger.info("Scheduler stopped")

    async def run(self) -> None:
        """Main scheduler loop."""
        await self.start()

        try:
            while self._running:
                await self._check_cycle()
                await self._check_scheduled_campaigns()
                await self._check_campaign_health()

                await asyncio.sleep(self.CHECK_INTERVAL)

        except Exception as e:
            logger.error(f"Scheduler error: {e}")

        finally:
            await self.stop()

    async def _check_cycle(self) -> None:
        """Check and handle window cycle changes."""
        current_window = self.cycle_manager.get_current_window()

        if current_window != self._last_window:
            logger.info(f"Window changed: {self._last_window.value} -> {current_window.value}")
            await self._handle_window_change(self._last_window, current_window)
            self._last_window = current_window

    async def _handle_window_change(
        self,
        old_window: WindowType,
        new_window: WindowType,
    ) -> None:
        """
        Handle window change.

        Args:
            old_window: Previous window
            new_window: New window
        """
        db_manager = get_db_manager()

        if new_window == WindowType.ADMIN:
            # Switching to admin window
            logger.info("Switching to admin window - pausing user campaigns")

            # Queue admin campaigns
            async with db_manager.readonly_session() as session:
                campaign_repo = CampaignRepository(session)
                admin_campaigns = await campaign_repo.get_admin_campaigns()

                for campaign in admin_campaigns:
                    await self.queue_manager.add_campaign(
                        campaign.id,
                        campaign.user_id,
                        priority=10,
                        is_admin=True,
                    )

        else:
            # Switching to user window
            logger.info("Switching to user window - resuming user campaigns")

            # Queue user campaigns
            async with db_manager.readonly_session() as session:
                campaign_repo = CampaignRepository(session)
                active_campaigns = await campaign_repo.get_active()

                for campaign in active_campaigns:
                    if not campaign.is_admin_campaign:
                        await self.queue_manager.add_campaign(
                            campaign.id,
                            campaign.user_id,
                            priority=0,
                            is_admin=False,
                        )

    async def _check_scheduled_campaigns(self) -> None:
        """Check for scheduled campaigns to start."""
        db_manager = get_db_manager()

        async with db_manager.session() as session:
            campaign_repo = CampaignRepository(session)
            campaigns = await campaign_repo.get_all(status=CampaignStatus.SCHEDULED)

            for campaign in campaigns:
                # For now, start immediately when scheduled
                # In full implementation, check scheduled time
                if campaign.status == CampaignStatus.SCHEDULED:
                    await campaign_repo.start(campaign.id)

                    # Add to queue
                    is_admin = campaign.is_admin_campaign
                    current_window = self.cycle_manager.get_current_window()

                    # Only queue if in appropriate window
                    if is_admin and current_window == WindowType.ADMIN:
                        await self.queue_manager.add_campaign(
                            campaign.id,
                            campaign.user_id,
                            priority=10,
                            is_admin=True,
                        )
                    elif not is_admin and current_window == WindowType.USER:
                        await self.queue_manager.add_campaign(
                            campaign.id,
                            campaign.user_id,
                            priority=0,
                            is_admin=False,
                        )

                    logger.info(f"Campaign {campaign.id} scheduled -> queued")

    async def _check_campaign_health(self) -> None:
        """Check health of active campaigns."""
        # Get active campaigns from queue
        active_ids = await self.queue_manager.get_active_campaigns()

        if not active_ids:
            return

        db_manager = get_db_manager()

        async with db_manager.readonly_session() as session:
            campaign_repo = CampaignRepository(session)

            for campaign_id_str in active_ids:
                campaign = await campaign_repo.get_with_progress(campaign_id_str)

                if not campaign:
                    # Campaign deleted - remove from active
                    await self.queue_manager.mark_campaign_inactive(campaign_id_str)
                    continue

                # Check if campaign should be stopped
                if campaign.status not in (CampaignStatus.ACTIVE, CampaignStatus.SCHEDULED):
                    await self.queue_manager.mark_campaign_inactive(campaign.id)

    async def add_campaign(
        self,
        campaign_id,
        user_id,
        is_admin: bool = False,
    ) -> bool:
        """
        Add campaign to queue.

        Args:
            campaign_id: Campaign UUID
            user_id: User UUID
            is_admin: Whether this is admin campaign

        Returns:
            True if added
        """
        current_window = self.cycle_manager.get_current_window()

        # Check window compatibility
        if is_admin and current_window != WindowType.ADMIN:
            logger.info(f"Admin campaign {campaign_id} queued for admin window")
        elif not is_admin and current_window != WindowType.USER:
            logger.info(f"User campaign {campaign_id} queued for user window")

        priority = 10 if is_admin else 0

        await self.queue_manager.add_campaign(
            campaign_id,
            user_id,
            priority=priority,
            is_admin=is_admin,
        )

        return True

    async def pause_campaign(self, campaign_id) -> bool:
        """
        Pause campaign.

        Args:
            campaign_id: Campaign UUID

        Returns:
            True if paused
        """
        # Remove from active
        await self.queue_manager.mark_campaign_inactive(campaign_id)

        # Update database
        db_manager = get_db_manager()
        async with db_manager.session() as session:
            campaign_repo = CampaignRepository(session)
            await campaign_repo.pause(campaign_id)

        logger.info(f"Campaign {campaign_id} paused")
        return True

    async def stop_campaign(self, campaign_id) -> bool:
        """
        Stop campaign.

        Args:
            campaign_id: Campaign UUID

        Returns:
            True if stopped
        """
        # Remove from active
        await self.queue_manager.mark_campaign_inactive(campaign_id)

        # Update database
        db_manager = get_db_manager()
        async with db_manager.session() as session:
            campaign_repo = CampaignRepository(session)
            await campaign_repo.stop(campaign_id)

        logger.info(f"Campaign {campaign_id} stopped")
        return True


async def run_scheduler() -> None:
    """Run scheduler process."""
    scheduler = Scheduler()
    await scheduler.run()


def main() -> None:
    """Main entry point."""
    asyncio.run(run_scheduler())


if __name__ == "__main__":
    main()
