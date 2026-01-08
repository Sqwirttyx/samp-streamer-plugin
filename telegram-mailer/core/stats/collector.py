"""Statistics collector for real-time metrics."""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from uuid import UUID

from common.logger import get_logger

logger = get_logger(__name__)


@dataclass
class SendStats:
    """Statistics for a sending session."""

    total_sent: int = 0
    total_success: int = 0
    total_failed: int = 0
    total_skipped: int = 0

    flood_waits: int = 0
    total_flood_wait_seconds: int = 0

    errors_by_type: dict = field(default_factory=dict)

    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

    @property
    def success_rate(self) -> float:
        """Calculate success rate percentage."""
        if self.total_sent == 0:
            return 0.0
        return (self.total_success / self.total_sent) * 100

    @property
    def duration_seconds(self) -> float:
        """Get duration in seconds."""
        if not self.start_time:
            return 0.0
        end = self.end_time or datetime.now()
        return (end - self.start_time).total_seconds()

    @property
    def sends_per_minute(self) -> float:
        """Calculate sends per minute."""
        duration_minutes = self.duration_seconds / 60
        if duration_minutes == 0:
            return 0.0
        return self.total_sent / duration_minutes

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "total_sent": self.total_sent,
            "total_success": self.total_success,
            "total_failed": self.total_failed,
            "total_skipped": self.total_skipped,
            "success_rate": round(self.success_rate, 2),
            "flood_waits": self.flood_waits,
            "total_flood_wait_seconds": self.total_flood_wait_seconds,
            "errors_by_type": self.errors_by_type,
            "duration_seconds": round(self.duration_seconds, 2),
            "sends_per_minute": round(self.sends_per_minute, 2),
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
        }


class StatsCollector:
    """
    Collector for sending statistics.

    Collects real-time stats during campaign execution.
    """

    def __init__(
        self,
        account_id: UUID,
        campaign_id: Optional[UUID] = None,
    ):
        """
        Initialize stats collector.

        Args:
            account_id: Account UUID
            campaign_id: Campaign UUID (optional)
        """
        self.account_id = account_id
        self.campaign_id = campaign_id
        self.stats = SendStats()
        self._lock = asyncio.Lock()

    def start(self) -> None:
        """Mark session start."""
        self.stats.start_time = datetime.now()
        logger.info(
            f"Stats collection started for account {self.account_id}"
        )

    def stop(self) -> None:
        """Mark session end."""
        self.stats.end_time = datetime.now()
        logger.info(
            f"Stats collection stopped for account {self.account_id}, "
            f"stats: {self.stats.to_dict()}"
        )

    async def record_success(self) -> None:
        """Record successful send."""
        async with self._lock:
            self.stats.total_sent += 1
            self.stats.total_success += 1

    async def record_failure(self, error_type: str = "unknown") -> None:
        """
        Record failed send.

        Args:
            error_type: Type of error
        """
        async with self._lock:
            self.stats.total_sent += 1
            self.stats.total_failed += 1

            # Track error types
            if error_type not in self.stats.errors_by_type:
                self.stats.errors_by_type[error_type] = 0
            self.stats.errors_by_type[error_type] += 1

    async def record_skip(self, reason: str = "unknown") -> None:
        """
        Record skipped send.

        Args:
            reason: Reason for skip
        """
        async with self._lock:
            self.stats.total_skipped += 1

    async def record_flood_wait(self, wait_seconds: int) -> None:
        """
        Record FloodWait occurrence.

        Args:
            wait_seconds: Wait duration in seconds
        """
        async with self._lock:
            self.stats.flood_waits += 1
            self.stats.total_flood_wait_seconds += wait_seconds

    def record_success_sync(self) -> None:
        """Record successful send (sync version)."""
        self.stats.total_sent += 1
        self.stats.total_success += 1

    def record_failure_sync(self, error_type: str = "unknown") -> None:
        """Record failed send (sync version)."""
        self.stats.total_sent += 1
        self.stats.total_failed += 1

        if error_type not in self.stats.errors_by_type:
            self.stats.errors_by_type[error_type] = 0
        self.stats.errors_by_type[error_type] += 1

    def get_stats(self) -> SendStats:
        """Get current statistics."""
        return self.stats

    def get_summary(self) -> dict:
        """Get statistics summary."""
        return {
            "account_id": str(self.account_id),
            "campaign_id": str(self.campaign_id) if self.campaign_id else None,
            **self.stats.to_dict(),
        }

    def reset(self) -> None:
        """Reset statistics."""
        self.stats = SendStats()


class MultiAccountStatsCollector:
    """
    Collector for multiple accounts.

    Aggregates stats across multiple sending accounts.
    """

    def __init__(self):
        """Initialize multi-account collector."""
        self._collectors: dict[UUID, StatsCollector] = {}
        self._lock = asyncio.Lock()

    async def get_collector(
        self,
        account_id: UUID,
        campaign_id: Optional[UUID] = None,
    ) -> StatsCollector:
        """
        Get or create collector for account.

        Args:
            account_id: Account UUID
            campaign_id: Campaign UUID (optional)

        Returns:
            StatsCollector for the account
        """
        async with self._lock:
            if account_id not in self._collectors:
                self._collectors[account_id] = StatsCollector(
                    account_id=account_id,
                    campaign_id=campaign_id,
                )
            return self._collectors[account_id]

    async def remove_collector(self, account_id: UUID) -> Optional[SendStats]:
        """
        Remove collector and return final stats.

        Args:
            account_id: Account UUID

        Returns:
            Final stats if collector existed
        """
        async with self._lock:
            if account_id in self._collectors:
                collector = self._collectors.pop(account_id)
                return collector.get_stats()
        return None

    def get_all_stats(self) -> dict[str, dict]:
        """Get stats for all accounts."""
        return {
            str(account_id): collector.get_summary()
            for account_id, collector in self._collectors.items()
        }

    def get_aggregate_stats(self) -> dict:
        """Get aggregated stats across all accounts."""
        total = SendStats()

        for collector in self._collectors.values():
            stats = collector.get_stats()
            total.total_sent += stats.total_sent
            total.total_success += stats.total_success
            total.total_failed += stats.total_failed
            total.total_skipped += stats.total_skipped
            total.flood_waits += stats.flood_waits
            total.total_flood_wait_seconds += stats.total_flood_wait_seconds

            for error_type, count in stats.errors_by_type.items():
                if error_type not in total.errors_by_type:
                    total.errors_by_type[error_type] = 0
                total.errors_by_type[error_type] += count

        return {
            "account_count": len(self._collectors),
            **total.to_dict(),
        }
