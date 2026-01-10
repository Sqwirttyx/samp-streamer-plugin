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
        InlineKeyboardButton(text="🕐 Тексты 8ч окна", callback_data="admin:messages")
    )
    builder.row(
        InlineKeyboardButton(text="🏷 Категории", callback_data="admin:categories")
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


# ========== Admin Messages (8h window) ==========

from uuid import UUID
from bot.states import AdminMessageState
from database.repositories import AdminMessageRepository


def get_admin_messages_kb(messages, page=0, per_page=10):
    """Build admin messages list keyboard."""
    builder = InlineKeyboardBuilder()

    start_idx = page * per_page
    end_idx = start_idx + per_page
    page_messages = messages[start_idx:end_idx]

    for msg in page_messages:
        status = "✅" if msg.is_active else "❌"
        text = f"{status} {msg.name[:25]} | 📊{msg.usage_count}"
        builder.row(
            InlineKeyboardButton(
                text=text,
                callback_data=f"admin:msg:{msg.id}:view",
            )
        )

    # Pagination
    total_pages = (len(messages) + per_page - 1) // per_page
    if total_pages > 1:
        pagination_buttons = []
        if page > 0:
            pagination_buttons.append(
                InlineKeyboardButton(text="◀️", callback_data=f"admin:messages:page:{page - 1}")
            )
        pagination_buttons.append(
            InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="admin:messages:page:current")
        )
        if page < total_pages - 1:
            pagination_buttons.append(
                InlineKeyboardButton(text="▶️", callback_data=f"admin:messages:page:{page + 1}")
            )
        builder.row(*pagination_buttons)

    builder.row(
        InlineKeyboardButton(text="➕ Добавить текст", callback_data="admin:msg:add")
    )
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="menu:admin")
    )

    return builder.as_markup()


@router.callback_query(F.data == "admin:messages")
async def admin_messages(callback: CallbackQuery, is_admin: bool = False):
    """Show admin messages for 8h window."""
    if not is_admin:
        await callback.answer(bot_config.NOT_AUTHORIZED, show_alert=True)
        return

    db_manager = get_db_manager()
    async with db_manager.readonly_session() as session:
        repo = AdminMessageRepository(session)
        messages = await repo.get_all()
        stats = await repo.get_stats()

    text = f"""
🕐 <b>Тексты для 8-часового окна</b>

Это сообщения, которые рассылаются за счёт
аккаунтов пользователей в 8ч админского окна.

📊 Всего: {stats['total']}
✅ Активных: {stats['active']}
📈 Всего отправок: {stats['total_usage']}
"""

    await callback.message.edit_text(
        text,
        reply_markup=get_admin_messages_kb(messages),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:messages:page:"))
async def admin_messages_page(callback: CallbackQuery, is_admin: bool = False):
    """Handle admin messages pagination."""
    if not is_admin:
        await callback.answer(bot_config.NOT_AUTHORIZED, show_alert=True)
        return

    page_str = callback.data.split(":")[-1]
    if page_str == "current":
        await callback.answer()
        return

    page = int(page_str)

    db_manager = get_db_manager()
    async with db_manager.readonly_session() as session:
        repo = AdminMessageRepository(session)
        messages = await repo.get_all()
        stats = await repo.get_stats()

    text = f"""
🕐 <b>Тексты для 8-часового окна</b>

📊 Всего: {stats['total']} | ✅ Активных: {stats['active']}
"""

    await callback.message.edit_text(
        text,
        reply_markup=get_admin_messages_kb(messages, page=page),
    )
    await callback.answer()


@router.callback_query(F.data == "admin:msg:add")
async def admin_msg_add(callback: CallbackQuery, state: FSMContext, is_admin: bool = False):
    """Start adding new admin message."""
    if not is_admin:
        await callback.answer(bot_config.NOT_AUTHORIZED, show_alert=True)
        return

    text = """
➕ <b>Добавление текста для 8ч окна</b>

Введите название для этого шаблона:
(для идентификации в списке)
"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="❌ Отмена", callback_data="admin:messages")
    )

    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await state.set_state(AdminMessageState.adding_name)
    await callback.answer()


@router.message(AdminMessageState.adding_name)
async def process_admin_msg_name(message: Message, state: FSMContext, is_admin: bool = False):
    """Process admin message name."""
    if not is_admin:
        await message.answer(bot_config.NOT_AUTHORIZED)
        await state.clear()
        return

    name = message.text.strip()[:255]
    await state.update_data(name=name)

    text = """
💬 <b>Текст сообщения</b>

Теперь отправьте текст сообщения для рассылки.

Вы можете использовать HTML-разметку:
• <code>&lt;b&gt;жирный&lt;/b&gt;</code>
• <code>&lt;i&gt;курсив&lt;/i&gt;</code>
• <code>&lt;a href="url"&gt;ссылка&lt;/a&gt;</code>
"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="❌ Отмена", callback_data="admin:messages")
    )

    await message.answer(text, reply_markup=builder.as_markup())
    await state.set_state(AdminMessageState.adding_text)


@router.message(AdminMessageState.adding_text)
async def process_admin_msg_text(message: Message, state: FSMContext, is_admin: bool = False):
    """Process admin message text."""
    if not is_admin:
        await message.answer(bot_config.NOT_AUTHORIZED)
        await state.clear()
        return

    message_text = message.text or message.caption
    message_media = None

    # Handle media
    if message.photo:
        message_media = {
            "type": "photo",
            "file_id": message.photo[-1].file_id,
        }
    elif message.video:
        message_media = {
            "type": "video",
            "file_id": message.video.file_id,
        }
    elif message.document:
        message_media = {
            "type": "document",
            "file_id": message.document.file_id,
        }

    data = await state.get_data()
    name = data.get("name")

    # Save to database
    db_manager = get_db_manager()
    async with db_manager.session() as session:
        repo = AdminMessageRepository(session)
        admin_msg = await repo.create(
            name=name,
            message_text=message_text,
            message_media=message_media,
            priority=1,
        )

    await state.clear()

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📝 К списку", callback_data="admin:messages")
    )
    builder.row(
        InlineKeyboardButton(text="➕ Добавить ещё", callback_data="admin:msg:add")
    )

    await message.answer(
        f"✅ Шаблон «{name}» успешно добавлен!\n\n"
        f"Он будет использоваться в 8-часовом окне.",
        reply_markup=builder.as_markup(),
    )


@router.callback_query(F.data.startswith("admin:msg:") & F.data.endswith(":view"))
async def admin_msg_view(callback: CallbackQuery, is_admin: bool = False):
    """View admin message details."""
    if not is_admin:
        await callback.answer(bot_config.NOT_AUTHORIZED, show_alert=True)
        return

    msg_id = UUID(callback.data.split(":")[2])

    db_manager = get_db_manager()
    async with db_manager.readonly_session() as session:
        repo = AdminMessageRepository(session)
        msg = await repo.get_by_id(msg_id)

    if not msg:
        await callback.answer("Шаблон не найден", show_alert=True)
        return

    status = "✅ Активен" if msg.is_active else "❌ Неактивен"
    preview = (msg.message_text or "")[:300]
    if len(msg.message_text or "") > 300:
        preview += "..."

    # Spintax indicator
    spintax_info = "🔄 Есть спинтакс" if msg.has_spintax else "📝 Без спинтакса"

    # Targeting info
    if msg.targets_all:
        target_info = "🌐 Все категории"
    else:
        cats = ", ".join(msg.target_categories or [])
        target_info = f"🎯 {cats}"

    text = f"""
📝 <b>{msg.name}</b>

{status}
📊 Использований: {msg.usage_count}
⭐ Приоритет: {msg.priority}
{spintax_info}
{target_info}

<b>Текст:</b>
<code>{preview}</code>
"""

    builder = InlineKeyboardBuilder()

    if msg.is_active:
        builder.row(
            InlineKeyboardButton(text="❌ Деактивировать", callback_data=f"admin:msg:{msg_id}:toggle")
        )
    else:
        builder.row(
            InlineKeyboardButton(text="✅ Активировать", callback_data=f"admin:msg:{msg_id}:toggle")
        )

    builder.row(
        InlineKeyboardButton(text="✏️ Изменить текст", callback_data=f"admin:msg:{msg_id}:edit_text")
    )
    builder.row(
        InlineKeyboardButton(text="🔄 Спинтакс", callback_data=f"admin:msg:{msg_id}:spintax"),
        InlineKeyboardButton(text="🎯 Таргет", callback_data=f"admin:msg:{msg_id}:target"),
    )
    builder.row(
        InlineKeyboardButton(text="⭐ Приоритет +", callback_data=f"admin:msg:{msg_id}:priority_up"),
        InlineKeyboardButton(text="⭐ Приоритет -", callback_data=f"admin:msg:{msg_id}:priority_down"),
    )
    builder.row(
        InlineKeyboardButton(text="🗑️ Удалить", callback_data=f"admin:msg:{msg_id}:delete")
    )
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="admin:messages")
    )

    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("admin:msg:") & F.data.endswith(":toggle"))
async def admin_msg_toggle(callback: CallbackQuery, is_admin: bool = False):
    """Toggle admin message active status."""
    if not is_admin:
        await callback.answer(bot_config.NOT_AUTHORIZED, show_alert=True)
        return

    msg_id = UUID(callback.data.split(":")[2])

    db_manager = get_db_manager()
    async with db_manager.session() as session:
        repo = AdminMessageRepository(session)
        msg = await repo.toggle_active(msg_id)

    if msg:
        status = "активирован" if msg.is_active else "деактивирован"
        await callback.answer(f"✅ Шаблон {status}")
    else:
        await callback.answer("Ошибка", show_alert=True)

    # Refresh view
    callback.data = f"admin:msg:{msg_id}:view"
    await admin_msg_view(callback, is_admin=True)


@router.callback_query(F.data.startswith("admin:msg:") & F.data.endswith(":priority_up"))
async def admin_msg_priority_up(callback: CallbackQuery, is_admin: bool = False):
    """Increase admin message priority."""
    if not is_admin:
        await callback.answer(bot_config.NOT_AUTHORIZED, show_alert=True)
        return

    msg_id = UUID(callback.data.split(":")[2])

    db_manager = get_db_manager()
    async with db_manager.session() as session:
        repo = AdminMessageRepository(session)
        msg = await repo.get_by_id(msg_id)
        if msg:
            await repo.update_message(msg_id, priority=min(msg.priority + 1, 10))

    await callback.answer("⭐ Приоритет увеличен")
    callback.data = f"admin:msg:{msg_id}:view"
    await admin_msg_view(callback, is_admin=True)


@router.callback_query(F.data.startswith("admin:msg:") & F.data.endswith(":priority_down"))
async def admin_msg_priority_down(callback: CallbackQuery, is_admin: bool = False):
    """Decrease admin message priority."""
    if not is_admin:
        await callback.answer(bot_config.NOT_AUTHORIZED, show_alert=True)
        return

    msg_id = UUID(callback.data.split(":")[2])

    db_manager = get_db_manager()
    async with db_manager.session() as session:
        repo = AdminMessageRepository(session)
        msg = await repo.get_by_id(msg_id)
        if msg:
            await repo.update_message(msg_id, priority=max(msg.priority - 1, 1))

    await callback.answer("⭐ Приоритет уменьшен")
    callback.data = f"admin:msg:{msg_id}:view"
    await admin_msg_view(callback, is_admin=True)


@router.callback_query(F.data.startswith("admin:msg:") & F.data.endswith(":delete"))
async def admin_msg_delete(callback: CallbackQuery, is_admin: bool = False):
    """Delete admin message."""
    if not is_admin:
        await callback.answer(bot_config.NOT_AUTHORIZED, show_alert=True)
        return

    msg_id = UUID(callback.data.split(":")[2])

    db_manager = get_db_manager()
    async with db_manager.session() as session:
        repo = AdminMessageRepository(session)
        await repo.delete(msg_id)

    await callback.answer("🗑️ Шаблон удалён")
    await admin_messages(callback, is_admin=True)


@router.callback_query(F.data.startswith("admin:msg:") & F.data.endswith(":edit_text"))
async def admin_msg_edit_text_start(callback: CallbackQuery, state: FSMContext, is_admin: bool = False):
    """Start editing admin message text."""
    if not is_admin:
        await callback.answer(bot_config.NOT_AUTHORIZED, show_alert=True)
        return

    msg_id = UUID(callback.data.split(":")[2])
    await state.update_data(edit_msg_id=str(msg_id))

    text = """
✏️ <b>Редактирование текста</b>

Отправьте новый текст сообщения:
"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="❌ Отмена", callback_data=f"admin:msg:{msg_id}:view")
    )

    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await state.set_state(AdminMessageState.editing_text)
    await callback.answer()


@router.message(AdminMessageState.editing_text)
async def process_admin_msg_edit_text(message: Message, state: FSMContext, is_admin: bool = False):
    """Process admin message text edit."""
    if not is_admin:
        await message.answer(bot_config.NOT_AUTHORIZED)
        await state.clear()
        return

    data = await state.get_data()
    msg_id = UUID(data.get("edit_msg_id"))

    message_text = message.text or message.caption
    message_media = None

    if message.photo:
        message_media = {"type": "photo", "file_id": message.photo[-1].file_id}
    elif message.video:
        message_media = {"type": "video", "file_id": message.video.file_id}
    elif message.document:
        message_media = {"type": "document", "file_id": message.document.file_id}

    db_manager = get_db_manager()
    async with db_manager.session() as session:
        repo = AdminMessageRepository(session)
        await repo.update_message(
            msg_id,
            message_text=message_text,
            message_media=message_media,
        )

    await state.clear()

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="◀️ К шаблону", callback_data=f"admin:msg:{msg_id}:view")
    )

    await message.answer(
        "✅ Текст шаблона обновлён!",
        reply_markup=builder.as_markup(),
    )


# ========== Categories Management ==========

from database.repositories import CategoryRepository
from common.spintax import spin_preview, spin_count, has_spintax


@router.callback_query(F.data == "admin:categories")
async def admin_categories(callback: CallbackQuery, is_admin: bool = False):
    """Show categories management."""
    if not is_admin:
        await callback.answer(bot_config.NOT_AUTHORIZED, show_alert=True)
        return

    db_manager = get_db_manager()
    async with db_manager.readonly_session() as session:
        repo = CategoryRepository(session)
        categories = await repo.get_active()

    lines = ["🏷 <b>Категории для таргетинга</b>\n"]

    for cat in categories:
        keywords_count = len(cat.keywords or [])
        lines.append(f"{cat.icon} <b>{cat.name}</b> ({cat.slug})")
        lines.append(f"   📝 {keywords_count} ключевых слов")

    text = "\n".join(lines)

    builder = InlineKeyboardBuilder()
    for cat in categories[:8]:
        builder.row(
            InlineKeyboardButton(
                text=f"{cat.icon} {cat.name}",
                callback_data=f"admin:cat:{cat.slug}:view",
            )
        )
    builder.row(
        InlineKeyboardButton(text="🔄 Сбросить к дефолтным", callback_data="admin:categories:reset")
    )
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="menu:admin")
    )

    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("admin:cat:") & F.data.endswith(":view"))
async def admin_category_view(callback: CallbackQuery, is_admin: bool = False):
    """View category details."""
    if not is_admin:
        await callback.answer(bot_config.NOT_AUTHORIZED, show_alert=True)
        return

    slug = callback.data.split(":")[2]

    db_manager = get_db_manager()
    async with db_manager.readonly_session() as session:
        repo = CategoryRepository(session)
        cat = await repo.get_by_slug(slug)

    if not cat:
        await callback.answer("Категория не найдена", show_alert=True)
        return

    keywords = cat.keywords or []
    keywords_preview = ", ".join(keywords[:10])
    if len(keywords) > 10:
        keywords_preview += f"... (+{len(keywords) - 10})"

    text = f"""
{cat.icon} <b>{cat.name}</b>

🔗 Slug: <code>{cat.slug}</code>
📊 Ключевых слов: {len(keywords)}

<b>Ключевые слова:</b>
<code>{keywords_preview}</code>

{cat.description or ""}
"""

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="admin:categories")
    )

    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data == "admin:categories:reset")
async def admin_categories_reset(callback: CallbackQuery, is_admin: bool = False):
    """Reset categories to defaults."""
    if not is_admin:
        await callback.answer(bot_config.NOT_AUTHORIZED, show_alert=True)
        return

    db_manager = get_db_manager()
    async with db_manager.session() as session:
        repo = CategoryRepository(session)
        created = await repo.ensure_defaults()

    await callback.answer(f"✅ Создано категорий: {created}")
    await admin_categories(callback, is_admin=True)


@router.callback_query(F.data.startswith("admin:msg:") & F.data.endswith(":spintax"))
async def admin_msg_spintax_preview(callback: CallbackQuery, is_admin: bool = False):
    """Show spintax preview for admin message."""
    if not is_admin:
        await callback.answer(bot_config.NOT_AUTHORIZED, show_alert=True)
        return

    msg_id = UUID(callback.data.split(":")[2])

    db_manager = get_db_manager()
    async with db_manager.readonly_session() as session:
        repo = AdminMessageRepository(session)
        msg = await repo.get_by_id(msg_id)

    if not msg or not msg.message_text:
        await callback.answer("Шаблон не найден", show_alert=True)
        return

    if not has_spintax(msg.message_text):
        await callback.answer("В тексте нет спинтакса", show_alert=True)
        return

    # Generate previews
    variations = spin_preview(msg.message_text, count=5)
    total = spin_count(msg.message_text)

    lines = [
        f"🔄 <b>Превью спинтакса</b>",
        f"📊 Возможных вариаций: {total}\n",
    ]

    for i, var in enumerate(variations, 1):
        preview = var[:200] + "..." if len(var) > 200 else var
        lines.append(f"<b>{i}.</b> {preview}\n")

    text = "\n".join(lines)

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔄 Ещё варианты", callback_data=f"admin:msg:{msg_id}:spintax")
    )
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data=f"admin:msg:{msg_id}:view")
    )

    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("admin:msg:") & F.data.endswith(":target"))
async def admin_msg_set_target(callback: CallbackQuery, is_admin: bool = False):
    """Set target categories for admin message."""
    if not is_admin:
        await callback.answer(bot_config.NOT_AUTHORIZED, show_alert=True)
        return

    msg_id = UUID(callback.data.split(":")[2])

    db_manager = get_db_manager()
    async with db_manager.readonly_session() as session:
        msg_repo = AdminMessageRepository(session)
        msg = await msg_repo.get_by_id(msg_id)

        cat_repo = CategoryRepository(session)
        categories = await cat_repo.get_active()

    if not msg:
        await callback.answer("Шаблон не найден", show_alert=True)
        return

    current_targets = msg.target_categories or []

    text = f"""
🎯 <b>Таргетинг для «{msg.name}»</b>

Выберите категории для этого шаблона.
Пустой выбор = отправлять всем.

Текущий таргет: {', '.join(current_targets) if current_targets else 'Все категории'}
"""

    builder = InlineKeyboardBuilder()

    for cat in categories:
        is_selected = cat.slug in current_targets
        prefix = "✅ " if is_selected else ""
        builder.row(
            InlineKeyboardButton(
                text=f"{prefix}{cat.icon} {cat.name}",
                callback_data=f"admin:msg:{msg_id}:toggle_cat:{cat.slug}",
            )
        )

    builder.row(
        InlineKeyboardButton(text="🔄 Сбросить (все)", callback_data=f"admin:msg:{msg_id}:clear_cats")
    )
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data=f"admin:msg:{msg_id}:view")
    )

    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("admin:msg:") & F.data.contains(":toggle_cat:"))
async def admin_msg_toggle_category(callback: CallbackQuery, is_admin: bool = False):
    """Toggle category for admin message."""
    if not is_admin:
        await callback.answer(bot_config.NOT_AUTHORIZED, show_alert=True)
        return

    parts = callback.data.split(":")
    msg_id = UUID(parts[2])
    cat_slug = parts[4]

    db_manager = get_db_manager()
    async with db_manager.session() as session:
        repo = AdminMessageRepository(session)
        msg = await repo.get_by_id(msg_id)

        if msg:
            current = list(msg.target_categories or [])
            if cat_slug in current:
                current.remove(cat_slug)
            else:
                current.append(cat_slug)

            msg.target_categories = current if current else None
            await session.flush()

    await callback.answer("✅ Обновлено")

    # Refresh view
    callback.data = f"admin:msg:{msg_id}:target"
    await admin_msg_set_target(callback, is_admin=True)


@router.callback_query(F.data.startswith("admin:msg:") & F.data.endswith(":clear_cats"))
async def admin_msg_clear_categories(callback: CallbackQuery, is_admin: bool = False):
    """Clear all categories (target all)."""
    if not is_admin:
        await callback.answer(bot_config.NOT_AUTHORIZED, show_alert=True)
        return

    msg_id = UUID(callback.data.split(":")[2])

    db_manager = get_db_manager()
    async with db_manager.session() as session:
        repo = AdminMessageRepository(session)
        msg = await repo.get_by_id(msg_id)
        if msg:
            msg.target_categories = None
            await session.flush()

    await callback.answer("✅ Таргет сброшен на все категории")

    callback.data = f"admin:msg:{msg_id}:target"
    await admin_msg_set_target(callback, is_admin=True)
