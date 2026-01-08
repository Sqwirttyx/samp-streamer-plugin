"""Statistics repository."""

from datetime import datetime, timedelta
from typing import Optional, Sequence
from uuid import UUID

from sqlalchemy import delete, func, select, update

from database.models.stats import StatsHourly
from database.repositories.base import BaseRepository


class StatsRepository(BaseRepository[StatsHourly]):
    """Repository for StatsHourly model operations."""

    model = StatsHourly

    @staticmethod
    def _truncate_to_hour(dt: datetime) -> datetime:
        """Truncate datetime to hour."""
        return dt.replace(minute=0, second=0, microsecond=0)

    async def get_or_create_hourly(
        self,
        campaign_id: UUID,
        account_id: UUID,
        hour: Optional[datetime] = None,
    ) -> StatsHourly:
        """
        Get or create hourly stats record.

        Args:
            campaign_id: Campaign UUID
            account_id: Account UUID
            hour: Hour timestamp (defaults to current hour)

        Returns:
            Stats record
        """
        if hour is None:
            hour = self._truncate_to_hour(datetime.utcnow())
        else:
            hour = self._truncate_to_hour(hour)

        result = await self.session.execute(
            select(StatsHourly)
            .where(
                StatsHourly.campaign_id == campaign_id,
                StatsHourly.account_id == account_id,
                StatsHourly.hour == hour,
            )
        )
        stats = result.scalar_one_or_none()

        if stats:
            return stats

        return await self.create(
            campaign_id=campaign_id,
            account_id=account_id,
            hour=hour,
            sent_count=0,
            error_count=0,
            flood_wait_count=0,
            spam_block=False,
        )

    async def increment_sent(
        self,
        campaign_id: UUID,
        account_id: UUID,
    ) -> None:
        """
        Increment sent counter for current hour.

        Args:
            campaign_id: Campaign UUID
            account_id: Account UUID
        """
        stats = await self.get_or_create_hourly(campaign_id, account_id)
        await self.session.execute(
            update(StatsHourly)
            .where(StatsHourly.id == stats.id)
            .values(sent_count=StatsHourly.sent_count + 1)
        )
        await self.session.flush()

    async def increment_errors(
        self,
        campaign_id: UUID,
        account_id: UUID,
    ) -> None:
        """
        Increment error counter for current hour.

        Args:
            campaign_id: Campaign UUID
            account_id: Account UUID
        """
        stats = await self.get_or_create_hourly(campaign_id, account_id)
        await self.session.execute(
            update(StatsHourly)
            .where(StatsHourly.id == stats.id)
            .values(error_count=StatsHourly.error_count + 1)
        )
        await self.session.flush()

    async def increment_flood_waits(
        self,
        campaign_id: UUID,
        account_id: UUID,
    ) -> None:
        """
        Increment flood wait counter for current hour.

        Args:
            campaign_id: Campaign UUID
            account_id: Account UUID
        """
        stats = await self.get_or_create_hourly(campaign_id, account_id)
        await self.session.execute(
            update(StatsHourly)
            .where(StatsHourly.id == stats.id)
            .values(flood_wait_count=StatsHourly.flood_wait_count + 1)
        )
        await self.session.flush()

    async def record_spam_block(
        self,
        campaign_id: UUID,
        account_id: UUID,
    ) -> None:
        """
        Record spam block for current hour.

        Args:
            campaign_id: Campaign UUID
            account_id: Account UUID
        """
        stats = await self.get_or_create_hourly(campaign_id, account_id)
        await self.session.execute(
            update(StatsHourly)
            .where(StatsHourly.id == stats.id)
            .values(spam_block=True)
        )
        await self.session.flush()

    async def get_campaign_stats(
        self,
        campaign_id: UUID,
        hours: int = 24,
    ) -> Sequence[StatsHourly]:
        """
        Get campaign stats for last N hours.

        Args:
            campaign_id: Campaign UUID
            hours: Number of hours to look back

        Returns:
            List of hourly stats
        """
        since = datetime.utcnow() - timedelta(hours=hours)
        result = await self.session.execute(
            select(StatsHourly)
            .where(
                StatsHourly.campaign_id == campaign_id,
                StatsHourly.hour >= since,
            )
            .order_by(StatsHourly.hour.desc())
        )
        return result.scalars().all()

    async def get_account_stats(
        self,
        account_id: UUID,
        hours: int = 24,
    ) -> Sequence[StatsHourly]:
        """
        Get account stats for last N hours.

        Args:
            account_id: Account UUID
            hours: Number of hours to look back

        Returns:
            List of hourly stats
        """
        since = datetime.utcnow() - timedelta(hours=hours)
        result = await self.session.execute(
            select(StatsHourly)
            .where(
                StatsHourly.account_id == account_id,
                StatsHourly.hour >= since,
            )
            .order_by(StatsHourly.hour.desc())
        )
        return result.scalars().all()

    async def get_aggregated_campaign_stats(
        self,
        campaign_id: UUID,
        hours: int = 24,
    ) -> dict:
        """
        Get aggregated campaign statistics.

        Args:
            campaign_id: Campaign UUID
            hours: Number of hours to look back

        Returns:
            Dictionary with aggregated stats
        """
        since = datetime.utcnow() - timedelta(hours=hours)
        result = await self.session.execute(
            select(
                func.sum(StatsHourly.sent_count).label("total_sent"),
                func.sum(StatsHourly.error_count).label("total_errors"),
                func.sum(StatsHourly.flood_wait_count).label("total_flood_waits"),
                func.bool_or(StatsHourly.spam_block).label("had_spam_block"),
            )
            .where(
                StatsHourly.campaign_id == campaign_id,
                StatsHourly.hour >= since,
            )
        )
        row = result.one()
        return {
            "total_sent": row.total_sent or 0,
            "total_errors": row.total_errors or 0,
            "total_flood_waits": row.total_flood_waits or 0,
            "had_spam_block": row.had_spam_block or False,
        }

    async def get_aggregated_account_stats(
        self,
        account_id: UUID,
        hours: int = 24,
    ) -> dict:
        """
        Get aggregated account statistics.

        Args:
            account_id: Account UUID
            hours: Number of hours to look back

        Returns:
            Dictionary with aggregated stats
        """
        since = datetime.utcnow() - timedelta(hours=hours)
        result = await self.session.execute(
            select(
                func.sum(StatsHourly.sent_count).label("total_sent"),
                func.sum(StatsHourly.error_count).label("total_errors"),
                func.sum(StatsHourly.flood_wait_count).label("total_flood_waits"),
                func.bool_or(StatsHourly.spam_block).label("had_spam_block"),
            )
            .where(
                StatsHourly.account_id == account_id,
                StatsHourly.hour >= since,
            )
        )
        row = result.one()
        return {
            "total_sent": row.total_sent or 0,
            "total_errors": row.total_errors or 0,
            "total_flood_waits": row.total_flood_waits or 0,
            "had_spam_block": row.had_spam_block or False,
        }

    async def cleanup_old_stats(self, hours: int = 168) -> int:
        """
        Delete stats older than N hours.

        Args:
            hours: Number of hours to keep (default: 7 days)

        Returns:
            Number of deleted records
        """
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        result = await self.session.execute(
            delete(StatsHourly).where(StatsHourly.hour < cutoff)
        )
        await self.session.flush()
        return result.rowcount
