"""Main sender class for Telethon worker."""

import asyncio
import random
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from telethon import TelegramClient
from telethon.errors import (
    ChannelPrivateError,
    ChatWriteForbiddenError,
    FloodWaitError as TelethonFloodWaitError,
    PeerFloodError,
    UserBannedInChannelError,
)

from common.constants import (
    AccountStatus,
    CampaignStatus,
    FLOOD_WAIT_PAUSE_DURATION,
    FLOOD_WAIT_SHORT,
    MAX_FLOOD_WAIT_RETRIES,
)
from common.exceptions import AccountBannedError, FloodWaitError, SpamBlockError
from common.logger import get_logger
from common.spintax import spin, has_spintax
from worker.message_handler import MessageHandler
from worker.session_manager import SessionManager

logger = get_logger(__name__)


class SendResult:
    """Result of a send operation."""

    def __init__(
        self,
        success: bool,
        chat_id: int,
        error: Optional[str] = None,
        flood_wait: int = 0,
        skip: bool = False,
    ):
        self.success = success
        self.chat_id = chat_id
        self.error = error
        self.flood_wait = flood_wait
        self.skip = skip  # Chat should be skipped (banned, private, etc.)


class SenderStats:
    """Statistics for sender."""

    def __init__(self):
        self.sent = 0
        self.errors = 0
        self.flood_waits = 0
        self.skipped = 0
        self.started_at = datetime.utcnow()

    def record_success(self):
        self.sent += 1

    def record_error(self):
        self.errors += 1

    def record_flood_wait(self):
        self.flood_waits += 1

    def record_skip(self):
        self.skipped += 1

    def to_dict(self) -> dict:
        return {
            "sent": self.sent,
            "errors": self.errors,
            "flood_waits": self.flood_waits,
            "skipped": self.skipped,
            "duration": (datetime.utcnow() - self.started_at).total_seconds(),
        }


class Sender:
    """
    Main sender class for campaign message delivery.

    Handles the complete sending workflow including:
    - Session management
    - Message sending
    - FloodWait handling
    - Error recovery
    - Statistics tracking
    """

    def __init__(
        self,
        account_id: UUID,
        user_id: UUID,
        proxy: Optional[dict] = None,
        interval_min: int = 25,
        interval_max: int = 45,
        work_hours: int = 4,
        rest_minutes: int = 30,
    ):
        """
        Initialize sender.

        Args:
            account_id: Account UUID
            user_id: User UUID
            proxy: Proxy configuration
            interval_min: Minimum interval between messages (seconds)
            interval_max: Maximum interval between messages (seconds)
            work_hours: Hours of work before rest
            rest_minutes: Rest duration in minutes
        """
        self.account_id = account_id
        self.user_id = user_id
        self.proxy = proxy
        self.interval_min = interval_min
        self.interval_max = interval_max
        self.work_hours = work_hours
        self.rest_minutes = rest_minutes

        self.client: Optional[TelegramClient] = None
        self.message_handler: Optional[MessageHandler] = None
        self.session_manager = SessionManager()

        self.stats = SenderStats()
        self.consecutive_flood_waits = 0
        self.work_started_at: Optional[datetime] = None
        self._running = False
        self._paused = False

    async def start(self) -> bool:
        """
        Start sender - load session and connect.

        Returns:
            True if started successfully
        """
        try:
            self.client = await self.session_manager.load_session(
                self.user_id,
                self.account_id,
                self.proxy,
            )
            self.message_handler = MessageHandler(self.client)

            # Validate session
            is_valid = await self.session_manager.validate_session(self.client)
            if not is_valid:
                raise AccountBannedError("Session validation failed")

            self._running = True
            self.work_started_at = datetime.utcnow()

            logger.info(f"Sender started for account {self.account_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to start sender: {e}")
            return False

    async def stop(self) -> None:
        """Stop sender and cleanup."""
        self._running = False
        await self.session_manager.close_session(self.account_id)
        logger.info(f"Sender stopped for account {self.account_id}")

    def pause(self) -> None:
        """Pause sending."""
        self._paused = True
        logger.info(f"Sender paused for account {self.account_id}")

    def resume(self) -> None:
        """Resume sending."""
        self._paused = False
        logger.info(f"Sender resumed for account {self.account_id}")

    @property
    def is_running(self) -> bool:
        return self._running and not self._paused

    async def send_to_chat(
        self,
        chat_id: int,
        text: Optional[str] = None,
        media: Optional[dict] = None,
    ) -> SendResult:
        """
        Send message to single chat.

        Args:
            chat_id: Target chat ID
            text: Message text
            media: Media dict

        Returns:
            SendResult
        """
        if not self.message_handler:
            return SendResult(False, chat_id, "Sender not started")

        try:
            success, error = await self.message_handler.send_with_media_dict(
                chat_id, text, media
            )

            if success:
                self.stats.record_success()
                self.consecutive_flood_waits = 0
                return SendResult(True, chat_id)
            else:
                self.stats.record_error()
                return SendResult(False, chat_id, error)

        except TelethonFloodWaitError as e:
            self.stats.record_flood_wait()
            self.consecutive_flood_waits += 1
            return SendResult(False, chat_id, f"FloodWait", flood_wait=e.seconds)

        except PeerFloodError:
            # Spam block - critical error
            self.stats.record_error()
            raise SpamBlockError("Account received spam block")

        except (UserBannedInChannelError, ChatWriteForbiddenError, ChannelPrivateError) as e:
            # Chat-specific errors - skip chat
            self.stats.record_skip()
            return SendResult(False, chat_id, str(e), skip=True)

        except Exception as e:
            self.stats.record_error()
            return SendResult(False, chat_id, str(e))

    async def handle_flood_wait(self, seconds: int) -> None:
        """
        Handle FloodWait error.

        Args:
            seconds: Wait duration
        """
        logger.warning(f"FloodWait: waiting {seconds} seconds")

        # Adapt interval if getting too many flood waits
        if self.consecutive_flood_waits >= MAX_FLOOD_WAIT_RETRIES:
            # Increase base interval
            self.interval_min = min(self.interval_min + 10, 60)
            self.interval_max = min(self.interval_max + 15, 120)
            logger.info(
                f"Adapted intervals to {self.interval_min}-{self.interval_max} "
                f"due to consecutive flood waits"
            )

            # Long pause
            await asyncio.sleep(FLOOD_WAIT_PAUSE_DURATION)
            self.consecutive_flood_waits = 0
        else:
            # Wait as requested
            await asyncio.sleep(seconds)

    def should_rest(self) -> bool:
        """Check if rest is needed."""
        if not self.work_started_at:
            return False

        worked = datetime.utcnow() - self.work_started_at
        return worked >= timedelta(hours=self.work_hours)

    async def rest(self) -> None:
        """Take a rest break."""
        logger.info(f"Taking rest for {self.rest_minutes} minutes")
        await asyncio.sleep(self.rest_minutes * 60)
        self.work_started_at = datetime.utcnow()
        logger.info("Rest completed, resuming work")

    def get_next_interval(self) -> int:
        """
        Calculate next send interval with randomization.

        Returns:
            Interval in seconds
        """
        base = random.randint(self.interval_min, self.interval_max)

        # Add some jitter (±20%)
        jitter = random.uniform(0.8, 1.2)
        return int(base * jitter)

    async def run_campaign(
        self,
        chat_ids: list[int],
        message_text: Optional[str],
        message_media: Optional[dict],
        on_progress: Optional[callable] = None,
        on_complete: Optional[callable] = None,
    ) -> dict:
        """
        Run full campaign sending loop.

        Args:
            chat_ids: List of target chat IDs
            message_text: Message text
            message_media: Message media dict
            on_progress: Callback for progress updates (chat_index, result)
            on_complete: Callback when campaign completes

        Returns:
            Final statistics dict
        """
        if not await self.start():
            return {"error": "Failed to start sender"}

        skipped_chats = set()

        try:
            cycle = 0
            while self._running:
                cycle += 1
                logger.info(f"Starting cycle {cycle} with {len(chat_ids)} chats")

                for i, chat_id in enumerate(chat_ids):
                    if not self._running:
                        break

                    while self._paused:
                        await asyncio.sleep(1)
                        if not self._running:
                            break

                    # Skip previously failed chats
                    if chat_id in skipped_chats:
                        continue

                    # Check if rest needed
                    if self.should_rest():
                        await self.rest()

                    # Apply spintax for unique message variation
                    current_text = message_text
                    if message_text and has_spintax(message_text):
                        current_text = spin(message_text)

                    # Send message
                    result = await self.send_to_chat(
                        chat_id, current_text, message_media
                    )

                    # Handle result
                    if result.flood_wait > 0:
                        await self.handle_flood_wait(result.flood_wait)

                    if result.skip:
                        skipped_chats.add(chat_id)

                    # Progress callback
                    if on_progress:
                        await on_progress(i, result)

                    # Wait before next send
                    if self._running and i < len(chat_ids) - 1:
                        interval = self.get_next_interval()
                        await asyncio.sleep(interval)

                logger.info(f"Cycle {cycle} completed")

                # Brief pause between cycles
                await asyncio.sleep(60)

        except SpamBlockError:
            logger.error("Campaign stopped due to spam block")
            self.stats.record_error()

        except Exception as e:
            logger.error(f"Campaign error: {e}")

        finally:
            await self.stop()

        stats = self.stats.to_dict()

        if on_complete:
            await on_complete(stats)

        return stats

    async def check_spam_block(self) -> bool:
        """
        Check if account has spam block.

        Returns:
            True if spam blocked
        """
        if not self.client:
            return False

        try:
            # Try to send test message to saved messages
            await self.client.send_message("me", "🔄 Health check")
            return False
        except PeerFloodError:
            return True
        except Exception:
            return False

    async def health_check(self) -> dict:
        """
        Perform health check on account.

        Returns:
            Health check result dict
        """
        result = {
            "connected": False,
            "authorized": False,
            "spam_blocked": False,
            "can_send": False,
        }

        if not self.client:
            return result

        try:
            result["connected"] = self.client.is_connected()
            result["authorized"] = await self.client.is_user_authorized()
            result["spam_blocked"] = await self.check_spam_block()
            result["can_send"] = (
                result["connected"]
                and result["authorized"]
                and not result["spam_blocked"]
            )
        except Exception as e:
            logger.error(f"Health check error: {e}")

        return result
