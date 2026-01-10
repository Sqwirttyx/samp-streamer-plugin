"""Admin panel handlers."""

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.config import bot_config
from bot.middlewares.auth import MASTER_KEY
from bot.states.registration import AdminAuthState
from database import get_db_manager
from database.repositories import (
    AccountRepository,
    CampaignRepository,
    UserRepository,
)

router = Router(name="admin")


def get_admin_menu_kb():
    """Build admin menu keyboard."""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="👥 Пользователи", callback_data="admin:users")
    )
    builder.row(
        InlineKeyboardButton(text="📊 Общая статистика", callback_data="admin:stats")
    )
    builder.row(
        InlineKeyboardButton(text="📨 Админ-рассылки", callback_data="admin:campaigns")
    )
    builder.row(
        InlineKeyboardButton(text="⚙️ Настройки системы", callback_data="admin:settings")
    )
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="menu:main")
    )

    return builder.as_markup()


@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext, is_admin: bool = False):
    """
    Handle /admin command.

    If user is already admin - show admin panel.
    If not - ask for master key.
    """
    if is_admin:
        # Already admin - show panel
        text = """
👑 <b>Админ-панель</b>

Управление системой Telegram Mailer.
"""
        await message.answer(text, reply_markup=get_admin_menu_kb())
    else:
        # Not admin - ask for master key
        await message.answer(
            "🔐 <b>Доступ к админ-панели</b>\n\n"
            "Введите мастер-ключ для получения прав администратора:"
        )
        await state.set_state(AdminAuthState.waiting_master_key)


@router.message(AdminAuthState.waiting_master_key)
async def process_master_key(message: Message, state: FSMContext, db_user=None):
    """Process master key for admin access."""
    entered_key = message.text.strip()

    # Delete message with key for security
    try:
        await message.delete()
    except Exception:
        pass

    if entered_key == MASTER_KEY:
        # Grant admin access
        db_manager = get_db_manager()
        async with db_manager.session() as session:
            repo = UserRepository(session)
            user = await repo.get_by_telegram_id(message.from_user.id)
            if user:
                user.is_admin = True
                await session.flush()

        await state.clear()
        await message.answer(
            "✅ <b>Доступ получен!</b>\n\n"
            "Вы получили права администратора.",
            reply_markup=get_admin_menu_kb(),
        )
    else:
        await state.clear()
        await message.answer(
            "❌ <b>Неверный ключ</b>\n\n"
            "Попробуйте ещё раз командой /admin"
        )


@router.callback_query(F.data == "menu:admin")
async def menu_admin(callback: CallbackQuery, is_admin: bool = False):
    """Handle admin menu."""
    if not is_admin:
        await callback.answer(bot_config.NOT_AUTHORIZED, show_alert=True)
        return

    text = """
👑 <b>Админ-панель</b>

Управление системой Telegram Mailer.
"""

    await callback.message.edit_text(
        text,
        reply_markup=get_admin_menu_kb(),
    )
    await callback.answer()


@router.callback_query(F.data == "admin:users")
async def admin_users(callback: CallbackQuery, is_admin: bool = False):
    """Show users list."""
    if not is_admin:
        await callback.answer(bot_config.NOT_AUTHORIZED, show_alert=True)
        return

    db_manager = get_db_manager()
    async with db_manager.readonly_session() as session:
        user_repo = UserRepository(session)
        users = await user_repo.get_active_users(limit=50)

    lines = [f"👥 <b>Пользователи</b> ({len(users)})\n"]

    for user in users[:20]:
        admin_mark = "👑 " if user.is_admin else ""
        username = f"@{user.username}" if user.username else f"ID:{user.telegram_id}"
        lines.append(f"{admin_mark}{username}")

    text = "\n".join(lines)

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔄 Обновить", callback_data="admin:users")
    )
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="menu:admin")
    )

    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data == "admin:stats")
async def admin_stats(callback: CallbackQuery, is_admin: bool = False):
    """Show system statistics."""
    if not is_admin:
        await callback.answer(bot_config.NOT_AUTHORIZED, show_alert=True)
        return

    db_manager = get_db_manager()
    async with db_manager.readonly_session() as session:
        user_repo = UserRepository(session)
        account_repo = AccountRepository(session)
        campaign_repo = CampaignRepository(session)

        total_users = await user_repo.count()
        total_accounts = await account_repo.count()
        total_campaigns = await campaign_repo.count()

    text = f"""
📊 <b>Системная статистика</b>

👥 Пользователей: {total_users}
📱 Аккаунтов: {total_accounts}
📨 Рассылок: {total_campaigns}
"""

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔄 Обновить", callback_data="admin:stats")
    )
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="menu:admin")
    )

    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data == "admin:campaigns")
async def admin_campaigns(callback: CallbackQuery, is_admin: bool = False):
    """Show admin campaigns management."""
    if not is_admin:
        await callback.answer(bot_config.NOT_AUTHORIZED, show_alert=True)
        return

    db_manager = get_db_manager()
    async with db_manager.readonly_session() as session:
        from sqlalchemy import select
        from database.models import Campaign
        from common.constants import CampaignStatus

        # Get all active campaigns across all users
        result = await session.execute(
            select(Campaign)
            .where(Campaign.status.in_([CampaignStatus.ACTIVE, CampaignStatus.SCHEDULED]))
            .limit(20)
        )
        campaigns = result.scalars().all()

    if not campaigns:
        text = """
📨 <b>Управление рассылками</b>

✅ Нет активных рассылок в системе.
"""
    else:
        lines = [f"📨 <b>Активные рассылки</b> ({len(campaigns)})\n"]
        for c in campaigns:
            status_emoji = "▶️" if c.status == CampaignStatus.ACTIVE else "📅"
            lines.append(f"{status_emoji} {c.name[:20]}")

        text = "\n".join(lines)

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="⏸ Остановить все", callback_data="admin:campaigns:pause_all")
    )
    builder.row(
        InlineKeyboardButton(text="🔄 Обновить", callback_data="admin:campaigns")
    )
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="menu:admin")
    )

    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data == "admin:campaigns:pause_all")
async def admin_pause_all_campaigns(callback: CallbackQuery, is_admin: bool = False):
    """Pause all active campaigns."""
    if not is_admin:
        await callback.answer(bot_config.NOT_AUTHORIZED, show_alert=True)
        return

    db_manager = get_db_manager()
    async with db_manager.session() as session:
        from sqlalchemy import update
        from database.models import Campaign
        from common.constants import CampaignStatus

        result = await session.execute(
            update(Campaign)
            .where(Campaign.status == CampaignStatus.ACTIVE)
            .values(status=CampaignStatus.PAUSED)
        )
        await session.flush()
        paused_count = result.rowcount

    await callback.answer(f"⏸ Остановлено рассылок: {paused_count}")
    await admin_campaigns(callback, is_admin=True)


@router.callback_query(F.data == "admin:settings")
async def admin_settings(callback: CallbackQuery, is_admin: bool = False):
    """Show system settings."""
    if not is_admin:
        await callback.answer(bot_config.NOT_AUTHORIZED, show_alert=True)
        return

    from common.config import settings

    text = f"""
⚙️ <b>Настройки системы</b>

📱 Макс. аккаунтов на пользователя: {settings.max_accounts_per_user}
🌐 Макс. прокси на пользователя: {settings.max_proxies_per_user}
📁 Макс. папок на пользователя: {settings.max_folders_per_user}
📨 Макс. рассылок на пользователя: {settings.max_campaigns_per_user}

⏱ Интервал по умолчанию: {settings.default_interval_min}-{settings.default_interval_max} сек
🕐 Работа: {settings.default_work_hours}ч / Отдых: {settings.default_rest_minutes}мин

🔄 Цикл 16/8:
  • Пользователь: {settings.user_window_hours}ч (с {settings.default_user_window_start})
  • Админ: {settings.admin_window_hours}ч
"""

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="menu:admin")
    )

    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()


@router.message(Command("broadcast"))
async def cmd_broadcast(message: Message, is_admin: bool = False):
    """Broadcast message to all users."""
    if not is_admin:
        await message.answer(bot_config.NOT_AUTHORIZED)
        return

    # Get broadcast text
    text = message.text.replace("/broadcast", "").strip()

    if not text:
        await message.answer(
            "Использование: /broadcast <текст сообщения>\n\n"
            "Сообщение будет отправлено всем пользователям."
        )
        return

    db_manager = get_db_manager()
    async with db_manager.readonly_session() as session:
        user_repo = UserRepository(session)
        users = await user_repo.get_active_users(limit=1000)

    sent = 0
    failed = 0

    for user in users:
        try:
            await message.bot.send_message(
                chat_id=user.telegram_id,
                text=f"📢 <b>Объявление</b>\n\n{text}",
            )
            sent += 1
        except Exception:
            failed += 1

    await message.answer(
        f"📢 Рассылка завершена!\n\n"
        f"✅ Отправлено: {sent}\n"
        f"❌ Ошибок: {failed}"
    )
