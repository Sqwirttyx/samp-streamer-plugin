"""Aggressive sender for maximum throughput campaigns."""

import asyncio
import random
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Optional

from telethon import TelegramClient
from telethon.errors import (
    ChannelPrivateError,
    ChatWriteForbiddenError,
    FloodWaitError,
    PeerFloodError,
    UserBannedInChannelError,
    UserRestrictedError,
    SlowModeWaitError,
)

from common.constants import SendingMode, SENDING_MODE_CONFIG, FLOOD_WAIT_MAX_ACCEPTABLE
from common.logger import get_logger

logger = get_logger(__name__)


@dataclass
class SendStats:
    """Real-time sending statistics."""

    sent: int = 0
    failed: int = 0
    skipped: int = 0
    flood_waits: int = 0
    total_wait_time: float = 0
    start_time: float = field(default_factory=time.time)

    @property
    def elapsed(self) -> float:
        """Elapsed time in seconds."""
        return time.time() - self.start_time

    @property
    def speed_per_minute(self) -> float:
        """Messages sent per minute."""
        if self.elapsed < 60:
            return self.sent * (60 / max(self.elapsed, 1))
        return self.sent / (self.elapsed / 60)

    @property
    def effective_speed(self) -> float:
        """Speed excluding wait time."""
        active_time = self.elapsed - self.total_wait_time
        if active_time < 60:
            return self.sent * (60 / max(active_time, 1))
        return self.sent / (active_time / 60)

    @property
    def success_rate(self) -> float:
        """Success rate percentage."""
        total = self.sent + self.failed
        if total == 0:
            return 100.0
        return (self.sent / total) * 100

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "sent": self.sent,
            "failed": self.failed,
            "skipped": self.skipped,
            "flood_waits": self.flood_waits,
            "total_wait_time": round(self.total_wait_time, 1),
            "elapsed_seconds": round(self.elapsed, 1),
            "speed_per_minute": round(self.speed_per_minute, 1),
            "effective_speed": round(self.effective_speed, 1),
            "success_rate": round(self.success_rate, 1),
        }


class AggressiveSender:
    """
    Aggressive sender for maximum throughput.

    Principle: Send as fast as possible, handle FloodWait when it comes.

    FloodWait is NOT a ban - it's just "wait". Telegram tells how long to wait.

    Math for 8000 msg/day:
        16 hours × 60 min × 8.3 msg/min = 8000 messages
        Delay: ~7 seconds between messages

    Usage:
        sender = AggressiveSender(client, SendingMode.AGGRESSIVE)
        results = await sender.send_campaign(chat_ids, message, progress_callback)
    """

    def __init__(
        self,
        client: TelegramClient,
        mode: SendingMode = SendingMode.AGGRESSIVE,
    ):
        """
        Initialize aggressive sender.

        Args:
            client: Telethon client
            mode: Sending mode (SAFE, NORMAL, AGGRESSIVE)
        """
        self.client = client
        self.mode = mode
        self.config = SENDING_MODE_CONFIG[mode]

        self.stats = SendStats()
        self.current_delay = self.config["min_delay"]
        self.burst_count = 0
        self.consecutive_success = 0
        self._running = False
        self._paused = False

    async def send_campaign(
        self,
        chat_ids: list[int],
        message_text: str,
        media_path: Optional[str] = None,
        text_variator: Optional[Callable[[str], str]] = None,
        progress_callback: Optional[Callable] = None,
        stop_on_restrict: bool = True,
    ) -> dict:
        """
        Run aggressive sending campaign.

        Args:
            chat_ids: List of chat IDs to send to
            message_text: Message template
            media_path: Optional media file path
            text_variator: Optional function to variate text
            progress_callback: Optional callback(current, total, stats)
            stop_on_restrict: Stop if account gets restricted

        Returns:
            Campaign results dictionary
        """
        self.stats = SendStats()
        self._running = True

        results = {
            "total": len(chat_ids),
            "sent": 0,
            "failed": 0,
            "skipped": 0,
            "flood_waits": [],
            "errors": [],
            "stopped_reason": None,
        }

        skipped_chats = set()

        try:
            for i, chat_id in enumerate(chat_ids):
                if not self._running:
                    results["stopped_reason"] = "manually_stopped"
                    break

                while self._paused:
                    await asyncio.sleep(1)
                    if not self._running:
                        break

                # Skip already failed chats
                if chat_id in skipped_chats:
                    continue

                # Variate text if variator provided
                text = text_variator(message_text) if text_variator else message_text

                # Send message
                result = await self._send_with_retry(chat_id, text, media_path)

                # Handle result
                if result["success"]:
                    results["sent"] += 1
                    self.stats.sent += 1
                    self.consecutive_success += 1

                    # Speed up after consecutive successes
                    if self.consecutive_success > 30:
                        self._speed_up()

                elif result.get("skip_chat"):
                    results["skipped"] += 1
                    self.stats.skipped += 1
                    skipped_chats.add(chat_id)

                elif result.get("flood_wait"):
                    results["flood_waits"].append({
                        "chat_id": chat_id,
                        "seconds": result["wait_seconds"],
                    })

                elif result.get("stop_campaign"):
                    results["stopped_reason"] = result.get("error", "account_restricted")
                    if stop_on_restrict:
                        break

                else:
                    results["failed"] += 1
                    self.stats.failed += 1
                    results["errors"].append({
                        "chat_id": chat_id,
                        "error": result.get("error"),
                    })

                # Progress callback
                if progress_callback and (i % 10 == 0 or i == len(chat_ids) - 1):
                    try:
                        await progress_callback(i + 1, len(chat_ids), self.stats)
                    except Exception:
                        pass

                # Smart delay
                if self._running and i < len(chat_ids) - 1:
                    await self._smart_delay()

        except Exception as e:
            logger.error(f"Campaign error: {e}")
            results["stopped_reason"] = f"error: {str(e)}"

        finally:
            self._running = False

        # Final stats
        results["stats"] = self.stats.to_dict()

        return results

    async def _send_with_retry(
        self,
        chat_id: int,
        text: str,
        media_path: Optional[str] = None,
        max_retries: int = 2,
    ) -> dict:
        """
        Send message with FloodWait retry.

        Args:
            chat_id: Target chat ID
            text: Message text
            media_path: Optional media path
            max_retries: Max retry attempts

        Returns:
            Result dictionary
        """
        for attempt in range(max_retries):
            try:
                if media_path:
                    await self.client.send_file(chat_id, media_path, caption=text)
                else:
                    await self.client.send_message(chat_id, text)

                return {"success": True}

            except FloodWaitError as e:
                wait_time = int(e.seconds * self.config["flood_wait_multiplier"])

                self.stats.flood_waits += 1
                self.stats.total_wait_time += wait_time
                self.consecutive_success = 0

                # Slow down
                self._slow_down()

                # If wait too long, skip this message
                if wait_time > FLOOD_WAIT_MAX_ACCEPTABLE:
                    logger.warning(f"FloodWait {wait_time}s too long, skipping chat")
                    return {
                        "success": False,
                        "flood_wait": True,
                        "wait_seconds": wait_time,
                        "error": f"FloodWait too long: {wait_time}s",
                    }

                logger.info(f"FloodWait {wait_time}s, waiting...")
                await asyncio.sleep(wait_time)
                continue

            except SlowModeWaitError as e:
                # Chat has slow mode enabled
                return {
                    "success": False,
                    "skip_chat": True,
                    "error": f"Slow mode: wait {e.seconds}s",
                }

            except (UserBannedInChannelError, ChatWriteForbiddenError):
                return {
                    "success": False,
                    "skip_chat": True,
                    "error": "banned_in_chat",
                }

            except ChannelPrivateError:
                return {
                    "success": False,
                    "skip_chat": True,
                    "error": "chat_private",
                }

            except PeerFloodError:
                # Spam block - serious
                logger.error("PeerFloodError - account may be spam blocked")
                return {
                    "success": False,
                    "stop_campaign": True,
                    "error": "peer_flood_spam_block",
                }

            except UserRestrictedError:
                # Account restricted
                logger.error("UserRestrictedError - account restricted")
                return {
                    "success": False,
                    "stop_campaign": True,
                    "error": "account_restricted",
                }

            except Exception as e:
                logger.error(f"Send error to {chat_id}: {e}")
                return {
                    "success": False,
                    "error": str(e),
                }

        return {"success": False, "error": "max_retries_exceeded"}

    async def _smart_delay(self) -> None:
        """Smart delay between messages with burst support."""
        self.burst_count += 1

        # Burst mode: send multiple fast, then pause
        if self.burst_count >= self.config["burst_size"]:
            await asyncio.sleep(self.config["burst_pause"])
            self.burst_count = 0
        else:
            # Normal delay with randomization (±20%)
            delay = random.uniform(
                self.current_delay * 0.8,
                self.current_delay * 1.2,
            )
            await asyncio.sleep(delay)

    def _speed_up(self) -> None:
        """Speed up after consecutive successes."""
        min_delay = self.config["min_delay"]
        self.current_delay = max(min_delay, self.current_delay * 0.95)

    def _slow_down(self) -> None:
        """Slow down after FloodWait."""
        max_delay = self.config["max_delay"]
        self.current_delay = min(max_delay * 2, self.current_delay * 1.3)

    def stop(self) -> None:
        """Stop the campaign."""
        self._running = False

    def pause(self) -> None:
        """Pause the campaign."""
        self._paused = True

    def resume(self) -> None:
        """Resume the campaign."""
        self._paused = False

    @property
    def is_running(self) -> bool:
        """Check if campaign is running."""
        return self._running

    @property
    def is_paused(self) -> bool:
        """Check if campaign is paused."""
        return self._paused
