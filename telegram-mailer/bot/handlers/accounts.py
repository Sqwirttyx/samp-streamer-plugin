"""Account management handlers."""

from uuid import UUID

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.config import bot_config
from bot.keyboards.accounts_kb import (
    get_account_actions_kb,
    get_account_confirm_kb,
    get_accounts_list_kb,
    get_proxy_selection_kb,
)
from bot.keyboards.inline import get_cancel_kb
from bot.states import AccountUploadState
from common.constants import AccountStatus
from database import get_db_manager
from database.repositories import AccountRepository, ProxyRepository

router = Router(name="accounts")


@router.callback_query(F.data == "menu:accounts")
async def menu_accounts(callback: CallbackQuery, db_user=None, is_registered: bool = False):
    """Handle accounts menu."""
    if not is_registered or not db_user:
        await callback.answer(bot_config.NOT_AUTHORIZED, show_alert=True)
        return

    db_manager = get_db_manager()
    async with db_manager.readonly_session() as session:
        repo = AccountRepository(session)
        accounts = await repo.get_by_user(db_user.id)

    text = f"""
📱 <b>Мои аккаунты</b>

Всего аккаунтов: {len(accounts)}
"""

    await callback.message.edit_text(
        text,
        reply_markup=get_accounts_list_kb(accounts),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("accounts:page:"))
async def accounts_page(callback: CallbackQuery, db_user=None):
    """Handle accounts pagination."""
    page_str = callback.data.split(":")[-1]
    if page_str == "current":
        await callback.answer()
        return

    page = int(page_str)

    db_manager = get_db_manager()
    async with db_manager.readonly_session() as session:
        repo = AccountRepository(session)
        accounts = await repo.get_by_user(db_user.id)

    text = f"""
📱 <b>Мои аккаунты</b>

Всего аккаунтов: {len(accounts)}
"""

    await callback.message.edit_text(
        text,
        reply_markup=get_accounts_list_kb(accounts, page=page),
    )
    await callback.answer()


@router.callback_query(F.data == "account:add")
async def account_add(callback: CallbackQuery, state: FSMContext):
    """Start account addition flow."""
    text = """
📱 <b>Добавление аккаунта</b>

Отправьте файл сессии Telethon (.session).

Файл должен быть валидной сессией Telethon.
"""
    await callback.message.edit_text(
        text,
        reply_markup=get_cancel_kb("menu:accounts"),
    )
    await state.set_state(AccountUploadState.waiting_session_file)
    await callback.answer()


@router.message(AccountUploadState.waiting_session_file, F.document)
async def process_session_file(message: Message, state: FSMContext, db_user=None):
    """Process uploaded session file."""
    document = message.document

    # Validate file extension
    if not document.file_name.endswith(".session"):
        await message.answer(
            "❌ Неверный формат файла. Отправьте файл с расширением .session"
        )
        return

    # Download file
    from aiogram import Bot

    bot: Bot = message.bot
    file = await bot.get_file(document.file_id)
    file_content = await bot.download_file(file.file_path)
    session_data = file_content.read()

    # Validate session
    from storage.session_storage import SessionStorage

    if not SessionStorage._validate_session_data(session_data):
        await message.answer(
            "❌ Невалидный файл сессии. Убедитесь, что это рабочая сессия Telethon."
        )
        return

    # Store session data in state
    await state.update_data(session_data=session_data, filename=document.file_name)

    # Ask for proxy selection
    db_manager = get_db_manager()
    async with db_manager.readonly_session() as session:
        proxy_repo = ProxyRepository(session)
        proxies = await proxy_repo.get_active_by_user(db_user.id)

    if proxies:
        text = """
🌐 <b>Выбор прокси</b>

Выберите прокси для этого аккаунта или продолжите без прокси.
"""
        from bot.keyboards.accounts_kb import get_proxy_selection_kb

        # Generate temp account_id for callback
        import uuid

        temp_id = str(uuid.uuid4())
        await state.update_data(temp_account_id=temp_id)

        await message.answer(
            text,
            reply_markup=get_proxy_selection_kb(proxies, temp_id),
        )
        await state.set_state(AccountUploadState.waiting_proxy_selection)
    else:
        # No proxies - save directly
        await save_account(message, state, db_user, None)


@router.callback_query(
    AccountUploadState.waiting_proxy_selection,
    F.data.startswith("account:") & F.data.contains(":set_proxy:"),
)
async def process_proxy_selection(callback: CallbackQuery, state: FSMContext, db_user=None):
    """Process proxy selection for new account."""
    parts = callback.data.split(":")
    proxy_id_str = parts[-1]

    proxy_id = None if proxy_id_str == "none" else UUID(proxy_id_str)

    await save_account(callback.message, state, db_user, proxy_id)
    await callback.answer()


async def save_account(message: Message, state: FSMContext, db_user, proxy_id):
    """Save the new account."""
    data = await state.get_data()
    session_data = data.get("session_data")

    if not session_data:
        await message.answer("❌ Ошибка: данные сессии не найдены")
        await state.clear()
        return

    import uuid

    from storage.session_storage import SessionStorage, get_session_storage

    account_id = uuid.uuid4()
    storage = get_session_storage()

    # Save encrypted session
    try:
        session_path = await storage.save_session(
            user_id=db_user.id,
            account_id=account_id,
            session_file=session_data,
        )
    except Exception as e:
        await message.answer(f"❌ Ошибка сохранения сессии: {e}")
        await state.clear()
        return

    # Create phone hash (placeholder - in real implementation extract from session)
    phone_hash = SessionStorage.hash_phone(str(account_id)[:12])

    # Create account record
    db_manager = get_db_manager()
    async with db_manager.session() as session:
        repo = AccountRepository(session)
        account = await repo.create(
            id=account_id,
            user_id=db_user.id,
            phone_hash=phone_hash,
            session_path=str(session_path),
            proxy_id=proxy_id,
            status=AccountStatus.ACTIVE,
            health_score=100,
        )

    await state.clear()
    await message.answer(
        f"✅ Аккаунт успешно добавлен!\n\nID: {account.id}",
        reply_markup=get_account_actions_kb(account.id, account.status),
    )


@router.callback_query(F.data.startswith("account:") & F.data.endswith(":view"))
async def account_view(callback: CallbackQuery, db_user=None):
    """View account details."""
    account_id = UUID(callback.data.split(":")[1])

    db_manager = get_db_manager()
    async with db_manager.readonly_session() as session:
        repo = AccountRepository(session)
        account = await repo.get_by_id(account_id)

    if not account or account.user_id != db_user.id:
        await callback.answer("Аккаунт не найден", show_alert=True)
        return

    status_text = {
        AccountStatus.ACTIVE: "✅ Активен",
        AccountStatus.PAUSED: "⏸️ Приостановлен",
        AccountStatus.BANNED: "🚫 Заблокирован",
        AccountStatus.ERROR: "❌ Ошибка",
    }.get(account.status, "❓ Неизвестно")

    text = f"""
📱 <b>Аккаунт</b>

📞 Телефон: ***{account.phone_hash[:4]}
📊 Статус: {status_text}
💚 Здоровье: {account.health_score}%
📨 Отправлено: {account.total_sent}
❌ Ошибок: {account.total_errors}
"""

    if account.flood_wait_until:
        text += f"\n⏳ FloodWait до: {account.flood_wait_until}"

    await callback.message.edit_text(
        text,
        reply_markup=get_account_actions_kb(account.id, account.status),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("account:") & F.data.endswith(":pause"))
async def account_pause(callback: CallbackQuery, db_user=None):
    """Pause account."""
    account_id = UUID(callback.data.split(":")[1])

    db_manager = get_db_manager()
    async with db_manager.session() as session:
        repo = AccountRepository(session)
        account = await repo.update_status(account_id, AccountStatus.PAUSED)

    if account:
        await callback.answer("⏸️ Аккаунт приостановлен")
        # Refresh view
        await account_view(callback, db_user)
    else:
        await callback.answer("Ошибка", show_alert=True)


@router.callback_query(F.data.startswith("account:") & F.data.endswith(":resume"))
async def account_resume(callback: CallbackQuery, db_user=None):
    """Resume account."""
    account_id = UUID(callback.data.split(":")[1])

    db_manager = get_db_manager()
    async with db_manager.session() as session:
        repo = AccountRepository(session)
        account = await repo.update_status(account_id, AccountStatus.ACTIVE)

    if account:
        await callback.answer("▶️ Аккаунт возобновлён")
        await account_view(callback, db_user)
    else:
        await callback.answer("Ошибка", show_alert=True)


@router.callback_query(F.data.startswith("account:") & F.data.endswith(":delete"))
async def account_delete_confirm(callback: CallbackQuery):
    """Show account deletion confirmation."""
    account_id = UUID(callback.data.split(":")[1])

    text = """
🗑️ <b>Удаление аккаунта</b>

Вы уверены, что хотите удалить этот аккаунт?

Это действие нельзя отменить!
"""
    await callback.message.edit_text(
        text,
        reply_markup=get_account_confirm_kb(account_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("account:") & F.data.endswith(":confirm_delete"))
async def account_delete(callback: CallbackQuery, db_user=None):
    """Delete account."""
    account_id = UUID(callback.data.split(":")[1])

    # Delete session file
    from storage.session_storage import get_session_storage

    storage = get_session_storage()
    await storage.delete_session(db_user.id, account_id)

    # Delete from database
    db_manager = get_db_manager()
    async with db_manager.session() as session:
        repo = AccountRepository(session)
        await repo.delete(account_id)

    await callback.answer("🗑️ Аккаунт удалён")

    # Return to accounts list
    await menu_accounts(callback, db_user, is_registered=True)


@router.callback_query(F.data.startswith("account:") & F.data.endswith(":check"))
async def account_check_health(callback: CallbackQuery, db_user=None):
    """Check account health/validity."""
    account_id = UUID(callback.data.split(":")[1])

    await callback.answer("🔄 Проверяю аккаунт...")

    from services.account_service import AccountService

    service = AccountService()
    try:
        is_valid, message = await service.validate_account(account_id, db_user.id)

        if is_valid:
            await callback.answer("✅ Аккаунт работает!", show_alert=True)
        else:
            await callback.answer(f"❌ {message}", show_alert=True)

        # Refresh view
        await account_view(callback, db_user)

    except Exception as e:
        await callback.answer(f"❌ Ошибка: {str(e)[:100]}", show_alert=True)


@router.callback_query(F.data.startswith("account:") & F.data.endswith(":change_proxy"))
async def account_change_proxy(callback: CallbackQuery, db_user=None):
    """Show proxy selection for account."""
    account_id = UUID(callback.data.split(":")[1])

    db_manager = get_db_manager()
    async with db_manager.readonly_session() as session:
        proxy_repo = ProxyRepository(session)
        proxies = await proxy_repo.get_active_by_user(db_user.id)

        account_repo = AccountRepository(session)
        account = await account_repo.get_by_id(account_id)

    if not account or account.user_id != db_user.id:
        await callback.answer("Аккаунт не найден", show_alert=True)
        return

    text = "🌐 <b>Выберите прокси для аккаунта:</b>"

    await callback.message.edit_text(
        text,
        reply_markup=get_proxy_selection_kb(proxies, account_id, account.proxy_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("account:") & F.data.contains(":set_proxy:"))
async def account_set_proxy(callback: CallbackQuery, db_user=None):
    """Set proxy for account."""
    parts = callback.data.split(":")
    account_id = UUID(parts[1])
    proxy_id_str = parts[3]

    proxy_id = None if proxy_id_str == "none" else UUID(proxy_id_str)

    db_manager = get_db_manager()
    async with db_manager.session() as session:
        repo = AccountRepository(session)
        await repo.bind_proxy(account_id, proxy_id)

    if proxy_id:
        await callback.answer("✅ Прокси привязан")
    else:
        await callback.answer("✅ Прокси отвязан")

    await account_view(callback, db_user)


@router.callback_query(F.data.startswith("account:") & F.data.endswith(":campaigns"))
async def account_campaigns(callback: CallbackQuery, db_user=None):
    """View campaigns for this account."""
    account_id = UUID(callback.data.split(":")[1])

    from aiogram.types import InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    from database.repositories import CampaignRepository

    db_manager = get_db_manager()
    async with db_manager.readonly_session() as session:
        repo = CampaignRepository(session)
        campaigns = await repo.get_by_account(account_id)

    if not campaigns:
        await callback.answer("У этого аккаунта нет рассылок", show_alert=True)
        return

    builder = InlineKeyboardBuilder()
    for campaign in campaigns[:10]:  # Limit to 10
        status_emoji = {
            "draft": "📝",
            "active": "▶️",
            "paused": "⏸️",
            "completed": "✅",
            "error": "❌",
        }.get(campaign.status.value, "❓")

        builder.row(
            InlineKeyboardButton(
                text=f"{status_emoji} {campaign.name}",
                callback_data=f"campaign:{campaign.id}:view",
            )
        )

    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data=f"account:{account_id}:view")
    )

    await callback.message.edit_text(
        f"📨 <b>Рассылки аккаунта</b>\n\nВсего: {len(campaigns)}",
        reply_markup=builder.as_markup(),
    )
    await callback.answer()
