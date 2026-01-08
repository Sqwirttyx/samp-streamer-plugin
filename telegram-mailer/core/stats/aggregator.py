"""Statistics aggregation for historical data."""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Optional
from uuid import UUID

from common.logger import get_logger
from database import get_db_manager
from database.repositories import StatsRepository

logger = get_logger(__name__)


@dataclass
class PeriodStats:
    """Aggregated stats for a time period."""

    total_sent: int = 0
    total_success: int = 0
    total_failed: int = 0
    flood_waits: int = 0
    unique_accounts: int = 0
    unique_campaigns: int = 0

    @property
    def success_rate(self) -> float:
        """Calculate success rate percentage."""
        if self.total_sent == 0:
            return 0.0
        return (self.total_success / self.total_sent) * 100

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "total_sent": self.total_sent,
            "total_success": self.total_success,
            "total_failed": self.total_failed,
            "success_rate": round(self.success_rate, 2),
            "flood_waits": self.flood_waits,
            "unique_accounts": self.unique_accounts,
            "unique_campaigns": self.unique_campaigns,
        }


class StatsAggregator:
    """
    Aggregator for historical statistics.

    Provides aggregated statistics over various time periods.
    """

    async def get_today_stats(
        self,
        user_id: Optional[UUID] = None,
        account_id: Optional[UUID] = None,
    ) -> PeriodStats:
        """
        Get statistics for today.

        Args:
            user_id: Filter by user (optional)
            account_id: Filter by account (optional)

        Returns:
            Aggregated stats for today
        """
        today = date.today()
        return await self.get_period_stats(
            start_date=today,
            end_date=today,
            user_id=user_id,
            account_id=account_id,
        )

    async def get_week_stats(
        self,
        user_id: Optional[UUID] = None,
        account_id: Optional[UUID] = None,
    ) -> PeriodStats:
        """
        Get statistics for last 7 days.

        Args:
            user_id: Filter by user (optional)
            account_id: Filter by account (optional)

        Returns:
            Aggregated stats for last 7 days
        """
        today = date.today()
        week_ago = today - timedelta(days=7)
        return await self.get_period_stats(
            start_date=week_ago,
            end_date=today,
            user_id=user_id,
            account_id=account_id,
        )

    async def get_month_stats(
        self,
        user_id: Optional[UUID] = None,
        account_id: Optional[UUID] = None,
    ) -> PeriodStats:
        """
        Get statistics for last 30 days.

        Args:
            user_id: Filter by user (optional)
            account_id: Filter by account (optional)

        Returns:
            Aggregated stats for last 30 days
        """
        today = date.today()
        month_ago = today - timedelta(days=30)
        return await self.get_period_stats(
            start_date=month_ago,
            end_date=today,
            user_id=user_id,
            account_id=account_id,
        )

    async def get_period_stats(
        self,
        start_date: date,
        end_date: date,
        user_id: Optional[UUID] = None,
        account_id: Optional[UUID] = None,
    ) -> PeriodStats:
        """
        Get statistics for a custom period.

        Args:
            start_date: Start date
            end_date: End date
            user_id: Filter by user (optional)
            account_id: Filter by account (optional)

        Returns:
            Aggregated stats for the period
        """
        db_manager = get_db_manager()

        async with db_manager.readonly_session() as session:
            repo = StatsRepository(session)

            result = await repo.get_period_stats(
                start_date=start_date,
                end_date=end_date,
                user_id=user_id,
                account_id=account_id,
            )

        return PeriodStats(
            total_sent=result.get("total_sent", 0),
            total_success=result.get("total_success", 0),
            total_failed=result.get("total_failed", 0),
            flood_waits=result.get("flood_waits", 0),
            unique_accounts=result.get("unique_accounts", 0),
            unique_campaigns=result.get("unique_campaigns", 0),
        )

    async def get_hourly_breakdown(
        self,
        target_date: date,
        user_id: Optional[UUID] = None,
        account_id: Optional[UUID] = None,
    ) -> list[dict]:
        """
        Get hourly breakdown for a specific date.

        Args:
            target_date: Date to get breakdown for
            user_id: Filter by user (optional)
            account_id: Filter by account (optional)

        Returns:
            List of hourly stats
        """
        db_manager = get_db_manager()

        async with db_manager.readonly_session() as session:
            repo = StatsRepository(session)

            records = await repo.get_hourly_stats(
                target_date=target_date,
                user_id=user_id,
                account_id=account_id,
            )

        # Fill in missing hours
        hourly = {}
        for record in records:
            hour = record.hour
            hourly[hour] = {
                "hour": hour,
                "sent": record.messages_sent,
                "success": record.messages_success,
                "failed": record.messages_failed,
                "flood_waits": record.flood_waits,
            }

        # Fill missing hours with zeros
        result = []
        for h in range(24):
            if h in hourly:
                result.append(hourly[h])
            else:
                result.append({
                    "hour": h,
                    "sent": 0,
                    "success": 0,
                    "failed": 0,
                    "flood_waits": 0,
                })

        return result

    async def get_daily_breakdown(
        self,
        start_date: date,
        end_date: date,
        user_id: Optional[UUID] = None,
    ) -> list[dict]:
        """
        Get daily breakdown for a date range.

        Args:
            start_date: Start date
            end_date: End date
            user_id: Filter by user (optional)

        Returns:
            List of daily stats
        """
        db_manager = get_db_manager()

        async with db_manager.readonly_session() as session:
            repo = StatsRepository(session)

            records = await repo.get_daily_stats(
                start_date=start_date,
                end_date=end_date,
                user_id=user_id,
            )

        return [
            {
                "date": record["date"].isoformat(),
                "sent": record["sent"],
                "success": record["success"],
                "failed": record["failed"],
                "success_rate": (
                    round(record["success"] / record["sent"] * 100, 2)
                    if record["sent"] > 0
                    else 0
                ),
            }
            for record in records
        ]

    async def get_account_ranking(
        self,
        user_id: UUID,
        period_days: int = 7,
        limit: int = 10,
    ) -> list[dict]:
        """
        Get account ranking by performance.

        Args:
            user_id: User UUID
            period_days: Period to calculate ranking for
            limit: Maximum accounts to return

        Returns:
            List of accounts sorted by performance
        """
        db_manager = get_db_manager()
        end_date = date.today()
        start_date = end_date - timedelta(days=period_days)

        async with db_manager.readonly_session() as session:
            repo = StatsRepository(session)

            return await repo.get_account_stats_ranking(
                user_id=user_id,
                start_date=start_date,
                end_date=end_date,
                limit=limit,
            )

    async def get_campaign_stats(
        self,
        campaign_id: UUID,
    ) -> dict:
        """
        Get statistics for a specific campaign.

        Args:
            campaign_id: Campaign UUID

        Returns:
            Campaign statistics
        """
        db_manager = get_db_manager()

        async with db_manager.readonly_session() as session:
            repo = StatsRepository(session)
            return await repo.get_campaign_stats(campaign_id)
