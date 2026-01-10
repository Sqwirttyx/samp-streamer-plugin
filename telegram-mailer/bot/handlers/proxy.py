"""Proxy management handlers."""

from uuid import UUID

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.config import bot_config
from bot.keyboards.inline import get_cancel_kb
from bot.states import ProxyAddState
from common.constants import ProxyStatus
from database import get_db_manager
from database.repositories import ProxyRepository

router = Router(name="proxy")


def get_proxies_list_kb(proxies, page=0, per_page=10):
    """Build proxies list keyboard."""
    builder = InlineKeyboardBuilder()

    start_idx = page * per_page
    end_idx = start_idx + per_page
    page_proxies = proxies[start_idx:end_idx]

    for proxy in page_proxies:
        status_emoji = {
            ProxyStatus.ACTIVE: "✅",
            ProxyStatus.CHECKING: "🔄",
            ProxyStatus.DEAD: "❌",
        }.get(proxy.status, "❓")

        text = f"🌐 {proxy.type.value} | {proxy.host}:{proxy.port} | {status_emoji}"
        builder.row(
            InlineKeyboardButton(
                text=text,
                callback_data=f"proxy:{proxy.id}:view",
            )
        )

    # Pagination
    total_pages = (len(proxies) + per_page - 1) // per_page
    if total_pages > 1:
        pagination_buttons = []
        if page > 0:
            pagination_buttons.append(
                InlineKeyboardButton(text="◀️", callback_data=f"proxies:page:{page - 1}")
            )
        pagination_buttons.append(
            InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="proxies:page:current")
        )
        if page < total_pages - 1:
            pagination_buttons.append(
                InlineKeyboardButton(text="▶️", callback_data=f"proxies:page:{page + 1}")
            )
        builder.row(*pagination_buttons)

    builder.row(
        InlineKeyboardButton(text="➕ Добавить прокси", callback_data="proxy:add")
    )
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="menu:main")
    )

    return builder.as_markup()


def get_proxy_actions_kb(proxy_id: UUID):
    """Build proxy actions keyboard."""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="🔄 Проверить", callback_data=f"proxy:{proxy_id}:check")
    )
    builder.row(
        InlineKeyboardButton(text="🗑️ Удалить", callback_data=f"proxy:{proxy_id}:delete")
    )
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="menu:proxy")
    )

    return builder.as_markup()


@router.callback_query(F.data == "menu:proxy")
async def menu_proxy(callback: CallbackQuery, db_user=None, is_registered: bool = False):
    """Handle proxy menu."""
    if not is_registered or not db_user:
        await callback.answer(bot_config.NOT_AUTHORIZED, show_alert=True)
        return

    db_manager = get_db_manager()
    async with db_manager.readonly_session() as session:
        repo = ProxyRepository(session)
        proxies = await repo.get_by_user(db_user.id)

    active_count = sum(1 for p in proxies if p.status == ProxyStatus.ACTIVE)

    text = f"""
🌐 <b>Мои прокси</b>

Всего: {len(proxies)}
Активных: {active_count}
"""

    await callback.message.edit_text(
        text,
        reply_markup=get_proxies_list_kb(proxies),
    )
    await callback.answer()


@router.callback_query(F.data == "proxy:add")
async def proxy_add(callback: CallbackQuery, state: FSMContext):
    """Start proxy addition flow."""
    text = """
🌐 <b>Добавление прокси</b>

Отправьте данные прокси в формате:

<code>type://user:pass@host:port</code>

или без авторизации:

<code>type://host:port</code>

Поддерживаемые типы: socks5, http, mtproxy

Пример:
<code>socks5://user:password@192.168.1.1:1080</code>
"""
    await callback.message.edit_text(
        text,
        reply_markup=get_cancel_kb("menu:proxy"),
    )
    await state.set_state(ProxyAddState.waiting_data)
    await callback.answer()


@router.message(ProxyAddState.waiting_data)
async def process_proxy_data(message: Message, state: FSMContext, db_user=None):
    """Process proxy data input."""
    proxy_string = message.text.strip()

    try:
        proxy_data = ProxyRepository.parse_proxy_string(proxy_string)
    except ValueError as e:
        await message.answer(f"❌ Ошибка: {e}\n\nПопробуйте ещё раз.")
        return

    db_manager = get_db_manager()
    async with db_manager.session() as session:
        repo = ProxyRepository(session)
        proxy = await repo.create_proxy(
            user_id=db_user.id,
            proxy_type=proxy_data["type"],
            host=proxy_data["host"],
            port=proxy_data["port"],
            username=proxy_data.get("username"),
            password=proxy_data.get("password"),
        )

    await state.clear()
    await message.answer(
        f"✅ Прокси добавлен!\n\n{proxy.type.value}://{proxy.host}:{proxy.port}",
        reply_markup=get_proxy_actions_kb(proxy.id),
    )


@router.callback_query(F.data.startswith("proxy:") & F.data.endswith(":view"))
async def proxy_view(callback: CallbackQuery, db_user=None):
    """View proxy details."""
    proxy_id = UUID(callback.data.split(":")[1])

    db_manager = get_db_manager()
    async with db_manager.readonly_session() as session:
        repo = ProxyRepository(session)
        proxy = await repo.get_by_id(proxy_id)

    if not proxy or proxy.user_id != db_user.id:
        await callback.answer("Прокси не найден", show_alert=True)
        return

    status_text = {
        ProxyStatus.ACTIVE: "✅ Активен",
        ProxyStatus.CHECKING: "🔄 Проверяется...",
        ProxyStatus.DEAD: "❌ Недоступен",
    }.get(proxy.status, "❓ Неизвестно")

    text = f"""
🌐 <b>Прокси</b>

📋 Тип: {proxy.type.value}
🏠 Хост: {proxy.host}
🔌 Порт: {proxy.port}
👤 Логин: {proxy.username or 'нет'}
📊 Статус: {status_text}
"""

    if proxy.last_check:
        text += f"🕐 Последняя проверка: {proxy.last_check.strftime('%d.%m.%Y %H:%M')}"

    await callback.message.edit_text(
        text,
        reply_markup=get_proxy_actions_kb(proxy.id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("proxy:") & F.data.endswith(":check"))
async def proxy_check(callback: CallbackQuery, db_user=None):
    """Check proxy availability."""
    proxy_id = UUID(callback.data.split(":")[1])

    # Mark as checking
    db_manager = get_db_manager()
    async with db_manager.session() as session:
        repo = ProxyRepository(session)
        await repo.update_status(proxy_id, ProxyStatus.CHECKING)

    await callback.answer("🔄 Проверяю прокси...")

    # Real proxy check
    from services.proxy_service import ProxyService

    proxy_service = ProxyService()
    is_working, message = await proxy_service.check_proxy(proxy_id, db_user.id)

    if is_working:
        await callback.answer("✅ Прокси работает!")
    else:
        await callback.answer(f"❌ {message}", show_alert=True)

    await proxy_view(callback, db_user)


@router.callback_query(F.data.startswith("proxy:") & F.data.endswith(":delete"))
async def proxy_delete(callback: CallbackQuery, db_user=None):
    """Delete proxy."""
    proxy_id = UUID(callback.data.split(":")[1])

    db_manager = get_db_manager()
    async with db_manager.session() as session:
        repo = ProxyRepository(session)
        await repo.delete(proxy_id)

    await callback.answer("🗑️ Прокси удалён")
    await menu_proxy(callback, db_user, is_registered=True)
