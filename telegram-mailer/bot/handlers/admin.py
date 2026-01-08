"""Admin panel handlers."""

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.config import bot_config
from database import get_db_manager
from database.repositories import (
    AccountRepository,
    CampaignRepository,
    InviteKeyRepository,
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
        InlineKeyboardButton(text="🔑 Инвайт-ключи", callback_data="admin:invites")
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


@router.command(Command("admin"))
async def cmd_admin(message: Message, is_admin: bool = False):
    """Handle /admin command."""
    if not is_admin:
        await message.answer(bot_config.NOT_AUTHORIZED)
        return

    text = """
👑 <b>Админ-панель</b>

Управление системой Telegram Mailer.
"""

    await message.answer(text, reply_markup=get_admin_menu_kb())


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


@router.callback_query(F.data == "admin:invites")
async def admin_invites(callback: CallbackQuery, is_admin: bool = False, db_user=None):
    """Show invite keys management."""
    if not is_admin:
        await callback.answer(bot_config.NOT_AUTHORIZED, show_alert=True)
        return

    db_manager = get_db_manager()
    async with db_manager.readonly_session() as session:
        invite_repo = InviteKeyRepository(session)
        keys = await invite_repo.get_unused(db_user.id)

    lines = ["🔑 <b>Активные инвайт-ключи</b>\n"]

    for key in keys[:10]:
        lines.append(f"<code>{key.key}</code> ({key.remaining_uses} исп.)")

    if not keys:
        lines.append("<i>Нет активных ключей</i>")

    text = "\n".join(lines)

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="➕ Создать 1 ключ", callback_data="admin:invite:create:1")
    )
    builder.row(
        InlineKeyboardButton(text="➕ Создать 5 ключей", callback_data="admin:invite:create:5")
    )
    builder.row(
        InlineKeyboardButton(text="➕ Создать 10 ключей", callback_data="admin:invite:create:10")
    )
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="menu:admin")
    )

    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("admin:invite:create:"))
async def admin_create_invites(callback: CallbackQuery, is_admin: bool = False, db_user=None):
    """Create invite keys."""
    if not is_admin:
        await callback.answer(bot_config.NOT_AUTHORIZED, show_alert=True)
        return

    count = int(callback.data.split(":")[-1])

    db_manager = get_db_manager()
    async with db_manager.session() as session:
        invite_repo = InviteKeyRepository(session)
        keys = await invite_repo.create_batch(
            created_by=db_user.id,
            count=count,
            max_uses=1,
            expires_in_days=30,
        )

    lines = [f"✅ <b>Создано {count} ключей:</b>\n"]
    for key in keys:
        lines.append(f"<code>{key.key}</code>")

    await callback.message.answer("\n".join(lines))
    await callback.answer(f"✅ Создано {count} ключей")

    # Refresh invites list
    await admin_invites(callback, is_admin, db_user)


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
    """Show admin campaigns settings."""
    if not is_admin:
        await callback.answer(bot_config.NOT_AUTHORIZED, show_alert=True)
        return

    text = """
📨 <b>Админ-рассылки</b>

Здесь вы можете настроить рассылки, которые будут отправляться
в 8-часовом админском окне.

<i>Функция в разработке</i>
"""

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="menu:admin")
    )

    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()


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


@router.message(Command("generate_key"))
async def cmd_generate_key(message: Message, is_admin: bool = False, db_user=None):
    """Generate invite keys via command."""
    if not is_admin:
        await message.answer(bot_config.NOT_AUTHORIZED)
        return

    # Parse count from command
    parts = message.text.split()
    count = 1
    if len(parts) > 1:
        try:
            count = min(50, max(1, int(parts[1])))
        except ValueError:
            pass

    db_manager = get_db_manager()
    async with db_manager.session() as session:
        invite_repo = InviteKeyRepository(session)
        keys = await invite_repo.create_batch(
            created_by=db_user.id,
            count=count,
            max_uses=1,
            expires_in_days=30,
        )

    lines = [f"✅ <b>Создано {count} ключей:</b>\n"]
    for key in keys:
        lines.append(f"<code>{key.key}</code>")

    await message.answer("\n".join(lines))


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
