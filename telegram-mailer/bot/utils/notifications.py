"""Notification management for bot."""

from typing import Optional
from uuid import UUID

from aiogram import Bot

from common.constants import (
    EVENT_ACCOUNT_BANNED,
    EVENT_ADMIN_WINDOW_START,
    EVENT_CAMPAIGN_COMPLETED,
    EVENT_CAMPAIGN_ERROR,
    EVENT_FLOOD_WAIT,
    EVENT_HOURLY_REPORT,
    EVENT_USER_WINDOW_START,
)
from common.logger import get_logger

logger = get_logger(__name__)


class NotificationManager:
    """
    Manager for sending notifications to users.

    Handles various events and sends appropriate messages to users.
    """

    def __init__(self, bot: Bot):
        """
        Initialize notification manager.

        Args:
            bot: Aiogram Bot instance
        """
        self.bot = bot

    async def send_notification(
        self,
        telegram_id: int,
        text: str,
        parse_mode: str = "HTML",
    ) -> bool:
        """
        Send notification to user.

        Args:
            telegram_id: User's Telegram ID
            text: Notification text
            parse_mode: Parse mode for message

        Returns:
            True if sent successfully
        """
        try:
            await self.bot.send_message(
                chat_id=telegram_id,
                text=text,
                parse_mode=parse_mode,
            )
            return True
        except Exception as e:
            logger.error(f"Failed to send notification to {telegram_id}: {e}")
            return False

    async def notify_account_banned(
        self,
        telegram_id: int,
        phone_hash: str,
        account_id: UUID,
    ) -> bool:
        """
        Notify user about account ban (spam block).

        Args:
            telegram_id: User's Telegram ID
            phone_hash: Account phone hash
            account_id: Account UUID

        Returns:
            True if sent
        """
        text = f"""
⚠️ <b>Внимание! Спамблок!</b>

Аккаунт <b>***{phone_hash[:4]}</b> получил спамблок от Telegram.

Рассылки с этого аккаунта приостановлены.
Рекомендуется не использовать аккаунт некоторое время.
"""
        return await self.send_notification(telegram_id, text)

    async def notify_campaign_completed(
        self,
        telegram_id: int,
        campaign_name: str,
        sent_count: int,
        error_count: int,
    ) -> bool:
        """
        Notify user about campaign completion.

        Args:
            telegram_id: User's Telegram ID
            campaign_name: Campaign name
            sent_count: Number of messages sent
            error_count: Number of errors

        Returns:
            True if sent
        """
        text = f"""
✅ <b>Рассылка завершена!</b>

📨 Рассылка: <b>{campaign_name}</b>
📊 Отправлено: {sent_count}
❌ Ошибок: {error_count}
"""
        return await self.send_notification(telegram_id, text)

    async def notify_campaign_error(
        self,
        telegram_id: int,
        campaign_name: str,
        error: str,
    ) -> bool:
        """
        Notify user about campaign error.

        Args:
            telegram_id: User's Telegram ID
            campaign_name: Campaign name
            error: Error message

        Returns:
            True if sent
        """
        text = f"""
❌ <b>Ошибка в рассылке!</b>

📨 Рассылка: <b>{campaign_name}</b>
⚠️ Ошибка: {error}

Рассылка приостановлена.
"""
        return await self.send_notification(telegram_id, text)

    async def notify_flood_wait(
        self,
        telegram_id: int,
        phone_hash: str,
        seconds: int,
    ) -> bool:
        """
        Notify user about FloodWait.

        Args:
            telegram_id: User's Telegram ID
            phone_hash: Account phone hash
            seconds: Wait duration in seconds

        Returns:
            True if sent
        """
        minutes = seconds // 60

        text = f"""
⏳ <b>FloodWait</b>

Аккаунт <b>***{phone_hash[:4]}</b> получил ограничение от Telegram.

Ожидание: {minutes} мин.
Рассылка автоматически продолжится после ожидания.
"""
        return await self.send_notification(telegram_id, text)

    async def notify_hourly_report(
        self,
        telegram_id: int,
        sent_count: int,
        error_count: int,
        active_campaigns: int,
    ) -> bool:
        """
        Send hourly statistics report.

        Args:
            telegram_id: User's Telegram ID
            sent_count: Messages sent in last hour
            error_count: Errors in last hour
            active_campaigns: Number of active campaigns

        Returns:
            True if sent
        """
        success_rate = (sent_count / (sent_count + error_count) * 100) if (sent_count + error_count) > 0 else 0

        text = f"""
📊 <b>Отчёт за час</b>

📨 Отправлено: {sent_count}
❌ Ошибок: {error_count}
✅ Успешность: {success_rate:.1f}%
🔄 Активных рассылок: {active_campaigns}
"""
        return await self.send_notification(telegram_id, text)

    async def notify_window_start(
        self,
        telegram_id: int,
        window_type: str,
        hours: int,
    ) -> bool:
        """
        Notify user about window cycle change.

        Args:
            telegram_id: User's Telegram ID
            window_type: "user" or "admin"
            hours: Duration of window

        Returns:
            True if sent
        """
        if window_type == "admin":
            text = f"""
🔄 <b>Началось админское окно</b>

Следующие {hours}ч будут использоваться для админских рассылок.
Ваши рассылки временно приостановлены.
"""
        else:
            text = f"""
🔄 <b>Началось ваше окно</b>

Следующие {hours}ч доступны для ваших рассылок.
Активные рассылки возобновлены.
"""
        return await self.send_notification(telegram_id, text)

    async def notify_by_event(
        self,
        telegram_id: int,
        event: str,
        data: dict,
    ) -> bool:
        """
        Send notification based on event type.

        Args:
            telegram_id: User's Telegram ID
            event: Event type constant
            data: Event data dictionary

        Returns:
            True if sent
        """
        handlers = {
            EVENT_ACCOUNT_BANNED: lambda: self.notify_account_banned(
                telegram_id,
                data.get("phone_hash", ""),
                data.get("account_id"),
            ),
            EVENT_CAMPAIGN_COMPLETED: lambda: self.notify_campaign_completed(
                telegram_id,
                data.get("campaign_name", ""),
                data.get("sent_count", 0),
                data.get("error_count", 0),
            ),
            EVENT_CAMPAIGN_ERROR: lambda: self.notify_campaign_error(
                telegram_id,
                data.get("campaign_name", ""),
                data.get("error", "Unknown error"),
            ),
            EVENT_FLOOD_WAIT: lambda: self.notify_flood_wait(
                telegram_id,
                data.get("phone_hash", ""),
                data.get("seconds", 0),
            ),
            EVENT_HOURLY_REPORT: lambda: self.notify_hourly_report(
                telegram_id,
                data.get("sent_count", 0),
                data.get("error_count", 0),
                data.get("active_campaigns", 0),
            ),
            EVENT_ADMIN_WINDOW_START: lambda: self.notify_window_start(
                telegram_id, "admin", data.get("hours", 8)
            ),
            EVENT_USER_WINDOW_START: lambda: self.notify_window_start(
                telegram_id, "user", data.get("hours", 16)
            ),
        }

        handler = handlers.get(event)
        if handler:
            return await handler()

        logger.warning(f"Unknown notification event: {event}")
        return False
