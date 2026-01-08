"""Statistics reporting and formatting."""

from datetime import date, timedelta
from typing import Optional
from uuid import UUID

from core.stats.aggregator import StatsAggregator, PeriodStats
from common.logger import get_logger

logger = get_logger(__name__)


class StatsReporter:
    """
    Reporter for formatted statistics.

    Generates human-readable reports from statistics.
    """

    def __init__(self):
        """Initialize reporter."""
        self.aggregator = StatsAggregator()

    async def generate_daily_report(
        self,
        user_id: Optional[UUID] = None,
        target_date: Optional[date] = None,
    ) -> str:
        """
        Generate daily report.

        Args:
            user_id: Filter by user (optional)
            target_date: Date for report (default: today)

        Returns:
            Formatted report string
        """
        target_date = target_date or date.today()

        stats = await self.aggregator.get_period_stats(
            start_date=target_date,
            end_date=target_date,
            user_id=user_id,
        )

        hourly = await self.aggregator.get_hourly_breakdown(
            target_date=target_date,
            user_id=user_id,
        )

        # Find peak hour
        peak_hour = max(hourly, key=lambda x: x["sent"])

        report = f"""📊 <b>Отчёт за {target_date.strftime('%d.%m.%Y')}</b>

📤 Всего отправлено: <b>{stats.total_sent:,}</b>
✅ Успешно: <b>{stats.total_success:,}</b>
❌ Ошибок: <b>{stats.total_failed:,}</b>
📈 Успешность: <b>{stats.success_rate:.1f}%</b>

⏰ Пиковый час: <b>{peak_hour['hour']:02d}:00</b> ({peak_hour['sent']} сообщений)
⚠️ FloodWait: <b>{stats.flood_waits}</b>

📱 Аккаунтов: <b>{stats.unique_accounts}</b>
📋 Кампаний: <b>{stats.unique_campaigns}</b>"""

        return report

    async def generate_weekly_report(
        self,
        user_id: Optional[UUID] = None,
    ) -> str:
        """
        Generate weekly report.

        Args:
            user_id: Filter by user (optional)

        Returns:
            Formatted report string
        """
        stats = await self.aggregator.get_week_stats(user_id=user_id)

        end_date = date.today()
        start_date = end_date - timedelta(days=7)

        daily = await self.aggregator.get_daily_breakdown(
            start_date=start_date,
            end_date=end_date,
            user_id=user_id,
        )

        # Find best and worst days
        best_day = max(daily, key=lambda x: x["sent"]) if daily else None
        worst_day = min(daily, key=lambda x: x["sent"]) if daily else None

        # Calculate average per day
        avg_per_day = stats.total_sent / 7 if stats.total_sent > 0 else 0

        report = f"""📊 <b>Отчёт за неделю</b>
{start_date.strftime('%d.%m')} - {end_date.strftime('%d.%m.%Y')}

📤 Всего отправлено: <b>{stats.total_sent:,}</b>
✅ Успешно: <b>{stats.total_success:,}</b>
❌ Ошибок: <b>{stats.total_failed:,}</b>
📈 Успешность: <b>{stats.success_rate:.1f}%</b>

📊 В среднем в день: <b>{avg_per_day:,.0f}</b>"""

        if best_day:
            report += f"\n🏆 Лучший день: <b>{best_day['date']}</b> ({best_day['sent']:,})"

        if worst_day:
            report += f"\n📉 Худший день: <b>{worst_day['date']}</b> ({worst_day['sent']:,})"

        report += f"""

⚠️ FloodWait: <b>{stats.flood_waits}</b>
📱 Аккаунтов: <b>{stats.unique_accounts}</b>
📋 Кампаний: <b>{stats.unique_campaigns}</b>"""

        return report

    async def generate_account_report(
        self,
        account_id: UUID,
        period_days: int = 7,
    ) -> str:
        """
        Generate report for specific account.

        Args:
            account_id: Account UUID
            period_days: Period for report

        Returns:
            Formatted report string
        """
        end_date = date.today()
        start_date = end_date - timedelta(days=period_days)

        stats = await self.aggregator.get_period_stats(
            start_date=start_date,
            end_date=end_date,
            account_id=account_id,
        )

        avg_per_day = stats.total_sent / period_days if stats.total_sent > 0 else 0

        report = f"""📱 <b>Статистика аккаунта</b>
Период: {start_date.strftime('%d.%m')} - {end_date.strftime('%d.%m.%Y')}

📤 Отправлено: <b>{stats.total_sent:,}</b>
✅ Успешно: <b>{stats.total_success:,}</b>
❌ Ошибок: <b>{stats.total_failed:,}</b>
📈 Успешность: <b>{stats.success_rate:.1f}%</b>

📊 В среднем в день: <b>{avg_per_day:,.0f}</b>
⚠️ FloodWait: <b>{stats.flood_waits}</b>"""

        return report

    async def generate_campaign_report(
        self,
        campaign_id: UUID,
    ) -> str:
        """
        Generate report for specific campaign.

        Args:
            campaign_id: Campaign UUID

        Returns:
            Formatted report string
        """
        stats = await self.aggregator.get_campaign_stats(campaign_id)

        total = stats.get("total_chats", 0)
        sent = stats.get("sent", 0)
        success = stats.get("success", 0)
        failed = stats.get("failed", 0)
        pending = stats.get("pending", 0)

        progress = (sent / total * 100) if total > 0 else 0
        success_rate = (success / sent * 100) if sent > 0 else 0

        # Progress bar
        bar_length = 10
        filled = int(bar_length * progress / 100)
        bar = "▓" * filled + "░" * (bar_length - filled)

        report = f"""📋 <b>Статистика кампании</b>

Прогресс: {bar} {progress:.1f}%

📊 Всего чатов: <b>{total:,}</b>
📤 Отправлено: <b>{sent:,}</b>
✅ Успешно: <b>{success:,}</b>
❌ Ошибок: <b>{failed:,}</b>
⏳ Ожидает: <b>{pending:,}</b>

📈 Успешность: <b>{success_rate:.1f}%</b>
⚠️ FloodWait: <b>{stats.get('flood_waits', 0)}</b>"""

        return report

    async def generate_ranking_report(
        self,
        user_id: UUID,
        period_days: int = 7,
    ) -> str:
        """
        Generate account ranking report.

        Args:
            user_id: User UUID
            period_days: Period for ranking

        Returns:
            Formatted report string
        """
        ranking = await self.aggregator.get_account_ranking(
            user_id=user_id,
            period_days=period_days,
            limit=5,
        )

        if not ranking:
            return "📊 <b>Рейтинг аккаунтов</b>\n\nНет данных за выбранный период."

        report = f"""📊 <b>Рейтинг аккаунтов</b>
Период: последние {period_days} дней

"""
        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]

        for i, account in enumerate(ranking):
            medal = medals[i] if i < len(medals) else f"{i+1}."
            phone = account.get("phone_masked", "***")
            sent = account.get("sent", 0)
            success_rate = account.get("success_rate", 0)

            report += f"{medal} {phone}: <b>{sent:,}</b> ({success_rate:.1f}%)\n"

        return report

    def format_stats_compact(self, stats: PeriodStats) -> str:
        """
        Format stats in compact form.

        Args:
            stats: Period stats

        Returns:
            Compact formatted string
        """
        return (
            f"📤 {stats.total_sent:,} | "
            f"✅ {stats.total_success:,} | "
            f"❌ {stats.total_failed:,} | "
            f"📈 {stats.success_rate:.1f}%"
        )

    def format_progress(
        self,
        current: int,
        total: int,
        bar_length: int = 10,
    ) -> str:
        """
        Format progress bar.

        Args:
            current: Current value
            total: Total value
            bar_length: Length of progress bar

        Returns:
            Formatted progress string
        """
        if total == 0:
            return "░" * bar_length + " 0%"

        progress = current / total
        filled = int(bar_length * progress)
        bar = "▓" * filled + "░" * (bar_length - filled)
        percentage = progress * 100

        return f"{bar} {percentage:.1f}%"
