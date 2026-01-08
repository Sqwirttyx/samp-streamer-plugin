"""Worker main entry point."""

import asyncio
import signal
from typing import Optional
from uuid import UUID

from common.logger import get_logger
from database import get_db_manager, init_db
from database.repositories import AccountRepository, CampaignRepository, FolderRepository
from redis_client import get_redis_manager
from redis_client.locks import LockManager
from redis_client.queue import QueueManager
from worker.sender import Sender

logger = get_logger(__name__)


class Worker:
    """
    Main worker class that processes campaigns.

    Pulls campaigns from queue and runs senders.
    """

    def __init__(self):
        """Initialize worker."""
        self._running = False
        self._current_sender: Optional[Sender] = None
        self.queue_manager: Optional[QueueManager] = None
        self.lock_manager: Optional[LockManager] = None

    async def start(self) -> None:
        """Start worker."""
        logger.info("Worker starting...")

        # Initialize database
        await init_db()

        # Initialize Redis
        redis_manager = get_redis_manager()
        await redis_manager.init()

        self.queue_manager = QueueManager(redis_manager.client)
        self.lock_manager = LockManager(redis_manager.client)

        self._running = True

        # Setup signal handlers
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, self._handle_signal)

        logger.info("Worker started")

    async def stop(self) -> None:
        """Stop worker."""
        logger.info("Worker stopping...")
        self._running = False

        if self._current_sender:
            await self._current_sender.stop()

        redis_manager = get_redis_manager()
        await redis_manager.close()

        logger.info("Worker stopped")

    def _handle_signal(self) -> None:
        """Handle shutdown signal."""
        logger.info("Shutdown signal received")
        self._running = False

    async def run(self) -> None:
        """Main worker loop."""
        await self.start()

        try:
            while self._running:
                # Try to get next campaign
                task = await self.queue_manager.get_next_campaign()

                if not task:
                    # No campaigns - wait and retry
                    await asyncio.sleep(5)
                    continue

                # Process campaign
                await self.process_campaign(UUID(task.campaign_id))

        except Exception as e:
            logger.error(f"Worker error: {e}")

        finally:
            await self.stop()

    async def process_campaign(self, campaign_id: UUID) -> None:
        """
        Process single campaign.

        Args:
            campaign_id: Campaign UUID
        """
        logger.info(f"Processing campaign {campaign_id}")

        # Get campaign details
        db_manager = get_db_manager()

        async with db_manager.readonly_session() as session:
            campaign_repo = CampaignRepository(session)
            campaign = await campaign_repo.get_with_progress(campaign_id)

            if not campaign:
                logger.error(f"Campaign {campaign_id} not found")
                return

            account_repo = AccountRepository(session)
            account = await account_repo.get_by_id(campaign.account_id)

            folder_repo = FolderRepository(session)
            folder = await folder_repo.get_by_id(campaign.folder_id)

        if not account or not folder:
            logger.error(f"Account or folder not found for campaign {campaign_id}")
            return

        # Acquire lock on account
        async with self.lock_manager.account_lock(account.id) as acquired:
            if not acquired:
                logger.warning(f"Could not acquire lock for account {account.id}")
                # Re-queue campaign
                await self.queue_manager.add_campaign(campaign_id, campaign.user_id)
                return

            # Build proxy config
            proxy = None
            if account.proxy:
                proxy = {
                    "type": account.proxy.type.value,
                    "host": account.proxy.host,
                    "port": account.proxy.port,
                    "username": account.proxy.username,
                    "password": account.proxy.password,
                }

            # Create sender
            self._current_sender = Sender(
                account_id=account.id,
                user_id=campaign.user_id,
                proxy=proxy,
                interval_min=campaign.interval_min,
                interval_max=campaign.interval_max,
                work_hours=campaign.work_hours,
                rest_minutes=campaign.rest_minutes,
            )

            # Get chat IDs
            chat_ids = folder.chat_ids or []
            if not chat_ids:
                logger.error(f"No chats in folder {folder.id}")
                return

            # Define callbacks
            async def on_progress(index: int, result):
                # Update progress in database
                async with db_manager.session() as session:
                    repo = CampaignRepository(session)
                    await repo.update_progress(campaign_id, index)

            async def on_complete(stats: dict):
                logger.info(f"Campaign {campaign_id} completed: {stats}")

            # Mark campaign as active
            async with db_manager.session() as session:
                repo = CampaignRepository(session)
                await repo.start(campaign_id)

            # Run campaign
            try:
                await self.queue_manager.mark_campaign_active(campaign_id)

                stats = await self._current_sender.run_campaign(
                    chat_ids=chat_ids,
                    message_text=campaign.message_text,
                    message_media=campaign.message_media,
                    on_progress=on_progress,
                    on_complete=on_complete,
                )

                # Mark campaign as completed
                async with db_manager.session() as session:
                    repo = CampaignRepository(session)
                    await repo.stop(campaign_id)

            except Exception as e:
                logger.error(f"Campaign {campaign_id} error: {e}")

                # Mark campaign as error
                async with db_manager.session() as session:
                    repo = CampaignRepository(session)
                    await repo.mark_error(campaign_id)

            finally:
                await self.queue_manager.mark_campaign_inactive(campaign_id)
                self._current_sender = None


async def run_worker() -> None:
    """Run worker process."""
    worker = Worker()
    await worker.run()


def main() -> None:
    """Main entry point."""
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
