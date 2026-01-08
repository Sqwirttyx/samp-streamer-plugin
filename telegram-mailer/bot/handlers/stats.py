"""Statistics handlers."""

from uuid import UUID

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.config import bot_config
from database import get_db_manager
from database.repositories import AccountRepository, CampaignRepository, StatsRepository

router = Router(name="stats")


def get_stats_menu_kb():
    """Build stats menu keyboard."""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="📊 За сегодня", callback_data="stats:today")
    )
    builder.row(
        InlineKeyboardButton(text="📈 За неделю", callback_data="stats:week")
    )
    builder.row(
        InlineKeyboardButton(text="📱 По аккаунтам", callback_data="stats:accounts")
    )
    builder.row(
        InlineKeyboardButton(text="📨 По рассылкам", callback_data="stats:campaigns")
    )
    builder.row(
        InlineKeyboardButton(text="❌ Журнал ошибок", callback_data="stats:errors")
    )
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="menu:main")
    )

    return builder.as_markup()


@router.callback_query(F.data == "menu:stats")
async def menu_stats(callback: CallbackQuery, db_user=None, is_registered: bool = False):
    """Handle stats menu."""
    if not is_registered or not db_user:
        await callback.answer(bot_config.NOT_AUTHORIZED, show_alert=True)
        return

    text = """
📊 <b>Статистика</b>

Выберите период или категорию:
"""

    await callback.message.edit_text(
        text,
        reply_markup=get_stats_menu_kb(),
    )
    await callback.answer()


@router.callback_query(F.data == "stats:today")
async def stats_today(callback: CallbackQuery, db_user=None):
    """Show today's statistics."""
    db_manager = get_db_manager()

    # Get all user's accounts stats
    total_sent = 0
    total_errors = 0
    total_flood = 0

    async with db_manager.readonly_session() as session:
        account_repo = AccountRepository(session)
        stats_repo = StatsRepository(session)

        accounts = await account_repo.get_by_user(db_user.id)

        for account in accounts:
            stats = await stats_repo.get_aggregated_account_stats(account.id, hours=24)
            total_sent += stats["total_sent"]
            total_errors += stats["total_errors"]
            total_flood += stats["total_flood_waits"]

    success_rate = (total_sent / (total_sent + total_errors) * 100) if (total_sent + total_errors) > 0 else 0

    text = f"""
📊 <b>Статистика за сегодня</b>

📨 Отправлено: {total_sent}
❌ Ошибок: {total_errors}
⏳ FloodWait: {total_flood}
✅ Успешность: {success_rate:.1f}%
"""

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔄 Обновить", callback_data="stats:today")
    )
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="menu:stats")
    )

    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data == "stats:week")
async def stats_week(callback: CallbackQuery, db_user=None):
    """Show weekly statistics."""
    db_manager = get_db_manager()

    total_sent = 0
    total_errors = 0

    async with db_manager.readonly_session() as session:
        account_repo = AccountRepository(session)
        stats_repo = StatsRepository(session)

        accounts = await account_repo.get_by_user(db_user.id)

        for account in accounts:
            stats = await stats_repo.get_aggregated_account_stats(account.id, hours=168)  # 7 days
            total_sent += stats["total_sent"]
            total_errors += stats["total_errors"]

    text = f"""
📈 <b>Статистика за неделю</b>

📨 Всего отправлено: {total_sent}
❌ Всего ошибок: {total_errors}
📊 Среднее в день: {total_sent // 7}
"""

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔄 Обновить", callback_data="stats:week")
    )
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="menu:stats")
    )

    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data == "stats:accounts")
async def stats_accounts(callback: CallbackQuery, db_user=None):
    """Show per-account statistics."""
    db_manager = get_db_manager()

    async with db_manager.readonly_session() as session:
        account_repo = AccountRepository(session)
        stats_repo = StatsRepository(session)

        accounts = await account_repo.get_by_user(db_user.id)

        lines = ["📱 <b>Статистика по аккаунтам</b>\n"]

        for account in accounts:
            stats = await stats_repo.get_aggregated_account_stats(account.id, hours=24)
            phone = f"***{account.phone_hash[:4]}"
            lines.append(
                f"📱 {phone}: {stats['total_sent']} отпр. / {stats['total_errors']} ошиб."
            )

    text = "\n".join(lines) if len(lines) > 1 else "📱 <b>Нет аккаунтов</b>"

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="menu:stats")
    )

    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data == "stats:campaigns")
async def stats_campaigns(callback: CallbackQuery, db_user=None):
    """Show per-campaign statistics."""
    db_manager = get_db_manager()

    async with db_manager.readonly_session() as session:
        campaign_repo = CampaignRepository(session)
        stats_repo = StatsRepository(session)

        campaigns = await campaign_repo.get_by_user(db_user.id)

        lines = ["📨 <b>Статистика по рассылкам</b>\n"]

        for campaign in campaigns[:10]:  # Limit to 10
            stats = await stats_repo.get_aggregated_campaign_stats(campaign.id, hours=24)
            lines.append(
                f"📨 {campaign.name}: {stats['total_sent']} отпр. / {stats['total_errors']} ошиб."
            )

    text = "\n".join(lines) if len(lines) > 1 else "📨 <b>Нет рассылок</b>"

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="menu:stats")
    )

    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data == "stats:errors")
async def stats_errors(callback: CallbackQuery, db_user=None):
    """Show error log."""
    # In a real implementation, you would fetch error logs from database
    text = """
❌ <b>Журнал ошибок</b>

Последние ошибки будут отображаться здесь.

<i>Функция в разработке</i>
"""

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="menu:stats")
    )

    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()
