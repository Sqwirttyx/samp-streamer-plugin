"""Folder management handlers."""

from uuid import UUID

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.config import bot_config
from bot.keyboards.inline import get_cancel_kb, get_confirm_kb
from bot.keyboards.main_menu import get_back_button
from bot.states import FolderAddState
from common.constants import FolderStatus
from database import get_db_manager
from database.repositories import AccountRepository, FolderRepository

router = Router(name="folders")


def get_folders_list_kb(folders, page=0, per_page=10):
    """Build folders list keyboard."""
    from aiogram.types import InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    builder = InlineKeyboardBuilder()

    start_idx = page * per_page
    end_idx = start_idx + per_page
    page_folders = folders[start_idx:end_idx]

    for folder in page_folders:
        status_emoji = {
            FolderStatus.ACTIVE: "✅",
            FolderStatus.SYNCING: "🔄",
            FolderStatus.ERROR: "❌",
        }.get(folder.status, "❓")

        text = f"📁 {folder.name} | {status_emoji} | {folder.chat_count} чатов"
        builder.row(
            InlineKeyboardButton(
                text=text,
                callback_data=f"folder:{folder.id}:view",
            )
        )

    # Pagination
    total_pages = (len(folders) + per_page - 1) // per_page
    if total_pages > 1:
        pagination_buttons = []
        if page > 0:
            pagination_buttons.append(
                InlineKeyboardButton(text="◀️", callback_data=f"folders:page:{page - 1}")
            )
        pagination_buttons.append(
            InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="folders:page:current")
        )
        if page < total_pages - 1:
            pagination_buttons.append(
                InlineKeyboardButton(text="▶️", callback_data=f"folders:page:{page + 1}")
            )
        builder.row(*pagination_buttons)

    builder.row(
        InlineKeyboardButton(text="➕ Добавить папку", callback_data="folder:add")
    )
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="menu:main")
    )

    return builder.as_markup()


def get_folder_actions_kb(folder_id: UUID, has_account: bool):
    """Build folder actions keyboard."""
    from aiogram.types import InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="🔄 Синхронизировать", callback_data=f"folder:{folder_id}:sync")
    )

    if has_account:
        builder.row(
            InlineKeyboardButton(text="🔗 Отвязать аккаунт", callback_data=f"folder:{folder_id}:unbind")
        )
    else:
        builder.row(
            InlineKeyboardButton(text="🔗 Привязать аккаунт", callback_data=f"folder:{folder_id}:bind")
        )

    builder.row(
        InlineKeyboardButton(text="📋 Список чатов", callback_data=f"folder:{folder_id}:chats")
    )
    builder.row(
        InlineKeyboardButton(text="🗑️ Удалить", callback_data=f"folder:{folder_id}:delete")
    )
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="menu:folders")
    )

    return builder.as_markup()


@router.callback_query(F.data == "menu:folders")
async def menu_folders(callback: CallbackQuery, db_user=None, is_registered: bool = False):
    """Handle folders menu."""
    if not is_registered or not db_user:
        await callback.answer(bot_config.NOT_AUTHORIZED, show_alert=True)
        return

    db_manager = get_db_manager()
    async with db_manager.readonly_session() as session:
        repo = FolderRepository(session)
        folders = await repo.get_by_user(db_user.id)

    text = f"""
📁 <b>Мои папки</b>

Всего папок: {len(folders)}
"""

    await callback.message.edit_text(
        text,
        reply_markup=get_folders_list_kb(folders),
    )
    await callback.answer()


@router.callback_query(F.data == "folder:add")
async def folder_add(callback: CallbackQuery, state: FSMContext):
    """Start folder addition flow."""
    text = """
📁 <b>Добавление папки</b>

Отправьте ссылку на папку Telegram.

Формат: https://t.me/addlist/...
"""
    await callback.message.edit_text(
        text,
        reply_markup=get_cancel_kb("menu:folders"),
    )
    await state.set_state(FolderAddState.waiting_link)
    await callback.answer()


@router.message(FolderAddState.waiting_link)
async def process_folder_link(message: Message, state: FSMContext):
    """Process folder link."""
    link = message.text.strip()

    # Validate link format
    if not link.startswith("https://t.me/addlist/"):
        await message.answer(
            "❌ Неверный формат ссылки. Ссылка должна начинаться с https://t.me/addlist/"
        )
        return

    await state.update_data(folder_link=link)

    text = """
📝 <b>Название папки</b>

Введите название для этой папки:
"""
    await message.answer(text, reply_markup=get_cancel_kb("menu:folders"))
    await state.set_state(FolderAddState.waiting_name)


@router.message(FolderAddState.waiting_name)
async def process_folder_name(message: Message, state: FSMContext, db_user=None):
    """Process folder name and save."""
    name = message.text.strip()[:255]
    data = await state.get_data()
    folder_link = data.get("folder_link")

    db_manager = get_db_manager()
    async with db_manager.session() as session:
        repo = FolderRepository(session)
        folder = await repo.create_folder(
            user_id=db_user.id,
            folder_link=folder_link,
            name=name,
        )

    await state.clear()
    await message.answer(
        f"✅ Папка '{name}' успешно добавлена!\n\nДля синхронизации чатов привяжите аккаунт.",
        reply_markup=get_folder_actions_kb(folder.id, False),
    )


@router.callback_query(F.data.startswith("folder:") & F.data.endswith(":view"))
async def folder_view(callback: CallbackQuery, db_user=None):
    """View folder details."""
    folder_id = UUID(callback.data.split(":")[1])

    db_manager = get_db_manager()
    async with db_manager.readonly_session() as session:
        repo = FolderRepository(session)
        folder = await repo.get_by_id(folder_id)

    if not folder or folder.user_id != db_user.id:
        await callback.answer("Папка не найдена", show_alert=True)
        return

    status_text = {
        FolderStatus.ACTIVE: "✅ Активна",
        FolderStatus.SYNCING: "🔄 Синхронизация...",
        FolderStatus.ERROR: "❌ Ошибка",
    }.get(folder.status, "❓ Неизвестно")

    text = f"""
📁 <b>{folder.name}</b>

🔗 Ссылка: {folder.folder_link}
📊 Статус: {status_text}
💬 Чатов: {folder.chat_count}
"""

    if folder.last_sync:
        text += f"🕐 Последняя синхронизация: {folder.last_sync.strftime('%d.%m.%Y %H:%M')}"

    await callback.message.edit_text(
        text,
        reply_markup=get_folder_actions_kb(folder.id, folder.account_id is not None),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("folder:") & F.data.endswith(":bind"))
async def folder_bind(callback: CallbackQuery, db_user=None):
    """Show account selection for folder binding."""
    folder_id = UUID(callback.data.split(":")[1])

    db_manager = get_db_manager()
    async with db_manager.readonly_session() as session:
        account_repo = AccountRepository(session)
        # Get all user accounts, not just active ones
        accounts = await account_repo.get_by_user(db_user.id)

    if not accounts:
        await callback.answer("Нет доступных аккаунтов. Сначала добавьте аккаунт.", show_alert=True)
        return

    from aiogram.types import InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    builder = InlineKeyboardBuilder()
    for account in accounts:
        # Get status emoji
        status_val = account.status.value if hasattr(account.status, 'value') else str(account.status)
        status_emoji = {
            "warming_up": "🔥",
            "active": "✅",
            "paused": "⏸️",
            "quarantine": "🔒",
            "banned": "🚫",
            "error": "❌",
        }.get(status_val, "❓")

        text = f"📱 {status_emoji} ***{account.phone_hash[:4]} | {account.health_score}%"
        builder.row(
            InlineKeyboardButton(
                text=text,
                callback_data=f"folder:{folder_id}:bind_to:{account.id}",
            )
        )
    builder.row(
        InlineKeyboardButton(text="❌ Отмена", callback_data=f"folder:{folder_id}:view")
    )

    await callback.message.edit_text(
        "🔗 <b>Выберите аккаунт для привязки:</b>",
        reply_markup=builder.as_markup(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("folder:") & F.data.contains(":bind_to:"))
async def folder_bind_to(callback: CallbackQuery, db_user=None):
    """Bind folder to selected account."""
    parts = callback.data.split(":")
    folder_id = UUID(parts[1])
    account_id = UUID(parts[3])

    db_manager = get_db_manager()
    async with db_manager.session() as session:
        repo = FolderRepository(session)
        await repo.bind_to_account(folder_id, account_id)

    await callback.answer("✅ Папка привязана к аккаунту")
    await folder_view(callback, db_user)


@router.callback_query(F.data.startswith("folder:") & F.data.endswith(":unbind"))
async def folder_unbind(callback: CallbackQuery, db_user=None):
    """Unbind folder from account."""
    folder_id = UUID(callback.data.split(":")[1])

    db_manager = get_db_manager()
    async with db_manager.session() as session:
        repo = FolderRepository(session)
        await repo.bind_to_account(folder_id, None)

    await callback.answer("✅ Папка отвязана от аккаунта")
    await folder_view(callback, db_user)


@router.callback_query(F.data.startswith("folder:") & F.data.endswith(":delete"))
async def folder_delete(callback: CallbackQuery, db_user=None):
    """Delete folder."""
    folder_id = UUID(callback.data.split(":")[1])

    db_manager = get_db_manager()
    async with db_manager.session() as session:
        repo = FolderRepository(session)
        await repo.delete(folder_id)

    await callback.answer("🗑️ Папка удалена")
    await menu_folders(callback, db_user, is_registered=True)


@router.callback_query(F.data.startswith("folder:") & F.data.endswith(":sync"))
async def folder_sync(callback: CallbackQuery, db_user=None):
    """Sync folder chats from Telegram."""
    folder_id = UUID(callback.data.split(":")[1])

    db_manager = get_db_manager()
    async with db_manager.readonly_session() as session:
        folder_repo = FolderRepository(session)
        folder = await folder_repo.get_by_id(folder_id)

        if not folder or folder.user_id != db_user.id:
            await callback.answer("Папка не найдена", show_alert=True)
            return

        # Check if folder has bound account
        if not folder.account_id:
            await callback.answer(
                "❌ Сначала привяжите аккаунт к папке для синхронизации",
                show_alert=True,
            )
            return

        account_id = folder.account_id

    await callback.answer("🔄 Синхронизация папки...")

    # Update status to syncing
    async with db_manager.session() as session:
        folder_repo = FolderRepository(session)
        await folder_repo.set_syncing(folder_id)

    try:
        from services.folder_service import FolderService

        service = FolderService()
        chat_count, message = await service.sync_folder(folder_id, db_user.id, account_id)

        if chat_count > 0:
            await callback.message.edit_text(
                f"✅ Синхронизация завершена!\n\nНайдено чатов: {chat_count}",
                reply_markup=get_folder_actions_kb(folder_id, True),
            )
        else:
            # Set error status
            async with db_manager.session() as session:
                folder_repo = FolderRepository(session)
                await folder_repo.set_error(folder_id)

            await callback.message.edit_text(
                f"❌ {message}",
                reply_markup=get_folder_actions_kb(folder_id, True),
            )

    except Exception as e:
        # Set error status
        async with db_manager.session() as session:
            folder_repo = FolderRepository(session)
            await folder_repo.set_error(folder_id)

        await callback.message.edit_text(
            f"❌ Ошибка синхронизации: {str(e)[:200]}",
            reply_markup=get_folder_actions_kb(folder_id, True),
        )


@router.callback_query(F.data.startswith("folder:") & F.data.endswith(":chats"))
async def folder_chats(callback: CallbackQuery, db_user=None):
    """Show list of chats in folder."""
    folder_id = UUID(callback.data.split(":")[1])

    db_manager = get_db_manager()
    async with db_manager.readonly_session() as session:
        repo = FolderRepository(session)
        folder = await repo.get_by_id(folder_id)

    if not folder or folder.user_id != db_user.id:
        await callback.answer("Папка не найдена", show_alert=True)
        return

    chat_ids = folder.chat_ids or []

    if not chat_ids:
        await callback.answer(
            "Папка пуста. Сначала синхронизируйте папку.",
            show_alert=True,
        )
        return

    # Show first 20 chats
    chats_preview = chat_ids[:20]
    text = f"📋 <b>Чаты в папке «{folder.name}»</b>\n\n"
    text += f"Всего чатов: {len(chat_ids)}\n\n"

    for i, chat_id in enumerate(chats_preview, 1):
        text += f"{i}. <code>{chat_id}</code>\n"

    if len(chat_ids) > 20:
        text += f"\n... и ещё {len(chat_ids) - 20} чатов"

    from aiogram.types import InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data=f"folder:{folder_id}:view")
    )

    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("folders:page:"))
async def folders_page(callback: CallbackQuery, db_user=None):
    """Handle folders pagination."""
    page_str = callback.data.split(":")[-1]
    if page_str == "current":
        await callback.answer()
        return

    page = int(page_str)

    db_manager = get_db_manager()
    async with db_manager.readonly_session() as session:
        repo = FolderRepository(session)
        folders = await repo.get_by_user(db_user.id)

    text = f"""
📁 <b>Мои папки</b>

Всего папок: {len(folders)}
"""

    await callback.message.edit_text(
        text,
        reply_markup=get_folders_list_kb(folders, page=page),
    )
    await callback.answer()
