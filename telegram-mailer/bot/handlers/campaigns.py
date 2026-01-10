"""Campaign management handlers."""

from uuid import UUID

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.config import bot_config
from bot.keyboards.campaigns_kb import (
    get_account_selection_kb,
    get_campaign_actions_kb,
    get_campaigns_list_kb,
    get_folder_selection_kb,
    get_interval_settings_kb,
    get_work_rest_settings_kb,
)
from bot.keyboards.inline import get_cancel_kb, get_confirm_kb
from bot.states import CampaignCreateState, CampaignEditState
from common.constants import CampaignStatus
from database import get_db_manager
from database.repositories import AccountRepository, CampaignRepository, FolderRepository

router = Router(name="campaigns")


@router.callback_query(F.data == "menu:campaigns")
async def menu_campaigns(callback: CallbackQuery, db_user=None, is_registered: bool = False):
    """Handle campaigns menu."""
    if not is_registered or not db_user:
        await callback.answer(bot_config.NOT_AUTHORIZED, show_alert=True)
        return

    db_manager = get_db_manager()
    async with db_manager.readonly_session() as session:
        repo = CampaignRepository(session)
        campaigns = await repo.get_by_user(db_user.id)

    active_count = sum(1 for c in campaigns if c.status == CampaignStatus.ACTIVE)

    text = f"""
📨 <b>Мои рассылки</b>

Всего: {len(campaigns)}
Активных: {active_count}
"""

    await callback.message.edit_text(
        text,
        reply_markup=get_campaigns_list_kb(campaigns),
    )
    await callback.answer()


@router.callback_query(F.data == "campaign:create")
async def campaign_create(callback: CallbackQuery, state: FSMContext):
    """Start campaign creation flow."""
    text = """
📨 <b>Создание рассылки</b>

Введите название для рассылки:
"""
    await callback.message.edit_text(
        text,
        reply_markup=get_cancel_kb("menu:campaigns"),
    )
    await state.set_state(CampaignCreateState.entering_name)
    await callback.answer()


@router.message(CampaignCreateState.entering_name)
async def process_campaign_name(message: Message, state: FSMContext, db_user=None):
    """Process campaign name."""
    name = message.text.strip()[:255]
    await state.update_data(name=name)

    # Get user's accounts (all accounts, not just active)
    db_manager = get_db_manager()
    async with db_manager.readonly_session() as session:
        repo = AccountRepository(session)
        accounts = await repo.get_by_user(db_user.id)

    if not accounts:
        await message.answer(
            "❌ У вас нет аккаунтов.\n\nСначала добавьте аккаунт в разделе 'Мои аккаунты'.",
            reply_markup=get_cancel_kb("menu:campaigns"),
        )
        await state.clear()
        return

    text = """
📱 <b>Выбор аккаунта</b>

Выберите аккаунт для рассылки:
"""
    await message.answer(
        text,
        reply_markup=get_account_selection_kb(accounts),
    )
    await state.set_state(CampaignCreateState.selecting_account)


@router.callback_query(
    CampaignCreateState.selecting_account,
    F.data.startswith("campaign:select_account:"),
)
async def process_account_selection(callback: CallbackQuery, state: FSMContext, db_user=None):
    """Process account selection."""
    account_id = UUID(callback.data.split(":")[-1])
    await state.update_data(account_id=str(account_id))

    # Get user's folders
    db_manager = get_db_manager()
    async with db_manager.readonly_session() as session:
        repo = FolderRepository(session)
        folders = await repo.get_synced(db_user.id)

    if not folders:
        await callback.message.edit_text(
            "❌ У вас нет синхронизированных папок.\n\nСначала добавьте и синхронизируйте папку.",
            reply_markup=get_cancel_kb("menu:campaigns"),
        )
        await state.clear()
        await callback.answer()
        return

    text = """
📁 <b>Выбор папки</b>

Выберите папку с чатами для рассылки:
"""
    await callback.message.edit_text(
        text,
        reply_markup=get_folder_selection_kb(folders),
    )
    await state.set_state(CampaignCreateState.selecting_folder)
    await callback.answer()


@router.callback_query(
    CampaignCreateState.selecting_folder,
    F.data.startswith("campaign:select_folder:"),
)
async def process_folder_selection(callback: CallbackQuery, state: FSMContext):
    """Process folder selection."""
    folder_id = UUID(callback.data.split(":")[-1])
    await state.update_data(folder_id=str(folder_id))

    text = """
💬 <b>Сообщение для рассылки</b>

Отправьте сообщение, которое будет рассылаться.

Вы можете отправить:
• Текст
• Фото с подписью
• Видео с подписью
• Документ с подписью
"""
    await callback.message.edit_text(
        text,
        reply_markup=get_cancel_kb("menu:campaigns"),
    )
    await state.set_state(CampaignCreateState.waiting_message)
    await callback.answer()


@router.message(CampaignCreateState.waiting_message)
async def process_campaign_message(message: Message, state: FSMContext):
    """Process campaign message."""
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

    await state.update_data(
        message_text=message_text,
        message_media=message_media,
    )

    # Set default intervals
    from common.config import settings

    await state.update_data(
        interval_min=settings.default_interval_min,
        interval_max=settings.default_interval_max,
    )

    data = await state.get_data()

    text = """
⏱ <b>Настройка интервалов</b>

Настройте интервал между сообщениями:
"""
    await message.answer(
        text,
        reply_markup=get_interval_settings_kb(
            data["interval_min"],
            data["interval_max"],
        ),
    )
    await state.set_state(CampaignCreateState.setting_intervals)


@router.callback_query(
    CampaignCreateState.setting_intervals,
    F.data.startswith("interval:"),
)
async def process_interval_setting(callback: CallbackQuery, state: FSMContext):
    """Process interval adjustment."""
    parts = callback.data.split(":")
    action = parts[1]
    direction = parts[2] if len(parts) > 2 else None

    data = await state.get_data()
    interval_min = data.get("interval_min", 25)
    interval_max = data.get("interval_max", 45)

    step = 5

    if action == "min":
        if direction == "increase":
            interval_min = min(interval_min + step, interval_max - step)
        elif direction == "decrease":
            interval_min = max(5, interval_min - step)
    elif action == "max":
        if direction == "increase":
            interval_max = min(300, interval_max + step)
        elif direction == "decrease":
            interval_max = max(interval_min + step, interval_max - step)
    elif action == "confirm":
        await state.update_data(interval_min=interval_min, interval_max=interval_max)

        # Move to work/rest settings
        from common.config import settings

        await state.update_data(
            work_hours=settings.default_work_hours,
            rest_minutes=settings.default_rest_minutes,
        )

        data = await state.get_data()
        text = """
🕐 <b>Настройка режима работы</b>

Настройте время работы и отдыха:
"""
        await callback.message.edit_text(
            text,
            reply_markup=get_work_rest_settings_kb(
                data["work_hours"],
                data["rest_minutes"],
            ),
        )
        await state.set_state(CampaignCreateState.setting_work_hours)
        await callback.answer()
        return
    elif action == "cancel":
        await state.clear()
        await callback.message.edit_text(
            "❌ Создание рассылки отменено.",
            reply_markup=get_cancel_kb("menu:campaigns"),
        )
        await callback.answer()
        return

    await state.update_data(interval_min=interval_min, interval_max=interval_max)

    text = """
⏱ <b>Настройка интервалов</b>

Настройте интервал между сообщениями:
"""
    await callback.message.edit_text(
        text,
        reply_markup=get_interval_settings_kb(interval_min, interval_max),
    )
    await callback.answer()


@router.callback_query(
    CampaignCreateState.setting_work_hours,
    F.data.startswith(("work:", "rest:", "workrest:")),
)
async def process_work_rest_setting(callback: CallbackQuery, state: FSMContext, db_user=None):
    """Process work/rest adjustment."""
    parts = callback.data.split(":")
    action = parts[0]
    direction = parts[1] if len(parts) > 1 else None

    data = await state.get_data()
    work_hours = data.get("work_hours", 4)
    rest_minutes = data.get("rest_minutes", 30)

    if action == "work":
        if direction == "increase":
            work_hours = min(12, work_hours + 1)
        elif direction == "decrease":
            work_hours = max(1, work_hours - 1)
    elif action == "rest":
        if direction == "increase":
            rest_minutes = min(120, rest_minutes + 10)
        elif direction == "decrease":
            rest_minutes = max(10, rest_minutes - 10)
    elif action == "workrest":
        if direction == "confirm":
            await state.update_data(work_hours=work_hours, rest_minutes=rest_minutes)

            # Create campaign
            data = await state.get_data()

            db_manager = get_db_manager()
            async with db_manager.session() as session:
                repo = CampaignRepository(session)
                campaign = await repo.create(
                    user_id=db_user.id,
                    account_id=UUID(data["account_id"]),
                    folder_id=UUID(data["folder_id"]),
                    name=data["name"],
                    message_text=data.get("message_text"),
                    message_media=data.get("message_media"),
                    interval_min=data["interval_min"],
                    interval_max=data["interval_max"],
                    work_hours=work_hours,
                    rest_minutes=rest_minutes,
                    status=CampaignStatus.DRAFT,
                )

            await state.clear()
            await callback.message.edit_text(
                f"✅ Рассылка '{campaign.name}' создана!\n\nТеперь вы можете запустить её.",
                reply_markup=get_campaign_actions_kb(campaign.id, campaign.status),
            )
            await callback.answer()
            return
        elif direction == "cancel":
            await state.clear()
            await callback.message.edit_text(
                "❌ Создание рассылки отменено.",
                reply_markup=get_cancel_kb("menu:campaigns"),
            )
            await callback.answer()
            return

    await state.update_data(work_hours=work_hours, rest_minutes=rest_minutes)

    text = """
🕐 <b>Настройка режима работы</b>

Настройте время работы и отдыха:
"""
    await callback.message.edit_text(
        text,
        reply_markup=get_work_rest_settings_kb(work_hours, rest_minutes),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("campaign:") & F.data.endswith(":view"))
async def campaign_view(callback: CallbackQuery, db_user=None):
    """View campaign details."""
    campaign_id = UUID(callback.data.split(":")[1])

    db_manager = get_db_manager()
    async with db_manager.readonly_session() as session:
        repo = CampaignRepository(session)
        campaign = await repo.get_with_progress(campaign_id)

    if not campaign or campaign.user_id != db_user.id:
        await callback.answer("Рассылка не найдена", show_alert=True)
        return

    status_text = {
        CampaignStatus.DRAFT: "📝 Черновик",
        CampaignStatus.SCHEDULED: "📅 Запланирована",
        CampaignStatus.ACTIVE: "▶️ Активна",
        CampaignStatus.PAUSED: "⏸️ Приостановлена",
        CampaignStatus.COMPLETED: "✅ Завершена",
        CampaignStatus.ERROR: "❌ Ошибка",
    }.get(campaign.status, "❓ Неизвестно")

    text = f"""
📨 <b>{campaign.name}</b>

📊 Статус: {status_text}
⏱ Интервал: {campaign.interval_min}-{campaign.interval_max} сек
🕐 Работа/Отдых: {campaign.work_hours}ч / {campaign.rest_minutes}мин
"""

    if campaign.progress:
        text += f"""
📈 Прогресс: чат {campaign.progress.current_chat_index + 1}
🔄 Циклов: {campaign.progress.cycle_count}
"""

    if campaign.started_at:
        text += f"\n▶️ Запущена: {campaign.started_at.strftime('%d.%m.%Y %H:%M')}"

    await callback.message.edit_text(
        text,
        reply_markup=get_campaign_actions_kb(campaign.id, campaign.status),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("campaign:") & F.data.endswith(":start"))
async def campaign_start(callback: CallbackQuery, db_user=None):
    """Start campaign."""
    campaign_id = UUID(callback.data.split(":")[1])

    db_manager = get_db_manager()
    async with db_manager.session() as session:
        repo = CampaignRepository(session)
        campaign = await repo.start(campaign_id)

    if campaign:
        await callback.answer("▶️ Рассылка запущена!")
        await campaign_view(callback, db_user)
    else:
        await callback.answer("❌ Не удалось запустить рассылку", show_alert=True)


@router.callback_query(F.data.startswith("campaign:") & F.data.endswith(":pause"))
async def campaign_pause(callback: CallbackQuery, db_user=None):
    """Pause campaign."""
    campaign_id = UUID(callback.data.split(":")[1])

    db_manager = get_db_manager()
    async with db_manager.session() as session:
        repo = CampaignRepository(session)
        campaign = await repo.pause(campaign_id)

    if campaign:
        await callback.answer("⏸️ Рассылка приостановлена")
        await campaign_view(callback, db_user)
    else:
        await callback.answer("Ошибка", show_alert=True)


@router.callback_query(F.data.startswith("campaign:") & F.data.endswith(":stop"))
async def campaign_stop(callback: CallbackQuery, db_user=None):
    """Stop campaign."""
    campaign_id = UUID(callback.data.split(":")[1])

    db_manager = get_db_manager()
    async with db_manager.session() as session:
        repo = CampaignRepository(session)
        campaign = await repo.stop(campaign_id)

    if campaign:
        await callback.answer("⏹️ Рассылка остановлена")
        await campaign_view(callback, db_user)
    else:
        await callback.answer("Ошибка", show_alert=True)


@router.callback_query(F.data.startswith("campaign:") & F.data.endswith(":delete"))
async def campaign_delete(callback: CallbackQuery, db_user=None):
    """Delete campaign."""
    campaign_id = UUID(callback.data.split(":")[1])

    db_manager = get_db_manager()
    async with db_manager.session() as session:
        repo = CampaignRepository(session)
        await repo.delete(campaign_id)

    await callback.answer("🗑️ Рассылка удалена")
    await menu_campaigns(callback, db_user, is_registered=True)


@router.callback_query(F.data.startswith("campaigns:page:"))
async def campaigns_page(callback: CallbackQuery, db_user=None):
    """Handle campaigns pagination."""
    page_str = callback.data.split(":")[-1]
    if page_str == "current":
        await callback.answer()
        return

    page = int(page_str)

    db_manager = get_db_manager()
    async with db_manager.readonly_session() as session:
        repo = CampaignRepository(session)
        campaigns = await repo.get_by_user(db_user.id)

    active_count = sum(1 for c in campaigns if c.status == CampaignStatus.ACTIVE)

    text = f"""
📨 <b>Мои рассылки</b>

Всего: {len(campaigns)}
Активных: {active_count}
"""

    await callback.message.edit_text(
        text,
        reply_markup=get_campaigns_list_kb(campaigns, page=page),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("campaign:") & F.data.endswith(":edit"))
async def campaign_edit(callback: CallbackQuery, db_user=None):
    """Edit campaign - show edit options."""
    campaign_id = UUID(callback.data.split(":")[1])

    db_manager = get_db_manager()
    async with db_manager.readonly_session() as session:
        repo = CampaignRepository(session)
        campaign = await repo.get_by_id(campaign_id)

    if not campaign or campaign.user_id != db_user.id:
        await callback.answer("Рассылка не найдена", show_alert=True)
        return

    # Cannot edit active campaigns
    if campaign.status == CampaignStatus.ACTIVE:
        await callback.answer("❌ Нельзя редактировать активную рассылку", show_alert=True)
        return

    from aiogram.types import InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="📝 Изменить название",
            callback_data=f"campaign:{campaign_id}:edit_name",
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="💬 Изменить сообщение",
            callback_data=f"campaign:{campaign_id}:edit_message",
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="⏱ Изменить интервалы",
            callback_data=f"campaign:{campaign_id}:edit_intervals",
        )
    )
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data=f"campaign:{campaign_id}:view")
    )

    text = f"""
✏️ <b>Редактирование рассылки</b>

📨 {campaign.name}

Выберите, что хотите изменить:
"""
    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("campaign:") & F.data.endswith(":stats"))
async def campaign_stats(callback: CallbackQuery, db_user=None):
    """View campaign statistics."""
    campaign_id = UUID(callback.data.split(":")[1])

    db_manager = get_db_manager()
    async with db_manager.readonly_session() as session:
        from database.repositories import StatsRepository

        stats_repo = StatsRepository(session)
        stats = await stats_repo.get_aggregated_campaign_stats(campaign_id, hours=24)

    text = f"""
📊 <b>Статистика за 24 часа</b>

📨 Отправлено: {stats['total_sent']}
❌ Ошибок: {stats['total_errors']}
⏳ FloodWait: {stats['total_flood_waits']}
🚫 Спамблок: {'Да' if stats['had_spam_block'] else 'Нет'}
"""

    from aiogram.types import InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data=f"campaign:{campaign_id}:view")
    )

    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("campaign:") & F.data.endswith(":edit_name"))
async def campaign_edit_name_start(callback: CallbackQuery, state: FSMContext, db_user=None):
    """Start campaign name editing."""
    campaign_id = UUID(callback.data.split(":")[1])

    db_manager = get_db_manager()
    async with db_manager.readonly_session() as session:
        repo = CampaignRepository(session)
        campaign = await repo.get_by_id(campaign_id)

    if not campaign or campaign.user_id != db_user.id:
        await callback.answer("Рассылка не найдена", show_alert=True)
        return

    await state.update_data(edit_campaign_id=str(campaign_id))

    text = f"""
📝 <b>Изменение названия</b>

Текущее название: {campaign.name}

Введите новое название:
"""
    await callback.message.edit_text(
        text,
        reply_markup=get_cancel_kb(f"campaign:{campaign_id}:edit"),
    )
    await state.set_state(CampaignEditState.editing_name)
    await callback.answer()


@router.message(CampaignEditState.editing_name)
async def campaign_edit_name_process(message: Message, state: FSMContext, db_user=None):
    """Process new campaign name."""
    data = await state.get_data()
    campaign_id = UUID(data.get("edit_campaign_id"))
    new_name = message.text.strip()[:255]

    db_manager = get_db_manager()
    async with db_manager.session() as session:
        repo = CampaignRepository(session)
        campaign = await repo.get_by_id(campaign_id)
        if campaign and campaign.user_id == db_user.id:
            campaign.name = new_name
            await session.flush()

    await state.clear()
    await message.answer(
        f"✅ Название изменено на: {new_name}",
        reply_markup=get_campaign_actions_kb(campaign_id, campaign.status),
    )


@router.callback_query(F.data.startswith("campaign:") & F.data.endswith(":edit_message"))
async def campaign_edit_message_start(callback: CallbackQuery, state: FSMContext, db_user=None):
    """Start campaign message editing."""
    campaign_id = UUID(callback.data.split(":")[1])

    db_manager = get_db_manager()
    async with db_manager.readonly_session() as session:
        repo = CampaignRepository(session)
        campaign = await repo.get_by_id(campaign_id)

    if not campaign or campaign.user_id != db_user.id:
        await callback.answer("Рассылка не найдена", show_alert=True)
        return

    await state.update_data(edit_campaign_id=str(campaign_id))

    current_text = campaign.message_text or "(без текста)"
    text = f"""
💬 <b>Изменение сообщения</b>

Текущее сообщение:
<code>{current_text[:500]}</code>

Отправьте новое сообщение (текст, фото или видео):
"""
    await callback.message.edit_text(
        text,
        reply_markup=get_cancel_kb(f"campaign:{campaign_id}:edit"),
    )
    await state.set_state(CampaignEditState.editing_message)
    await callback.answer()


@router.message(CampaignEditState.editing_message)
async def campaign_edit_message_process(message: Message, state: FSMContext, db_user=None):
    """Process new campaign message."""
    data = await state.get_data()
    campaign_id = UUID(data.get("edit_campaign_id"))

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

    db_manager = get_db_manager()
    async with db_manager.session() as session:
        repo = CampaignRepository(session)
        campaign = await repo.get_by_id(campaign_id)
        if campaign and campaign.user_id == db_user.id:
            campaign.message_text = message_text
            campaign.message_media = message_media
            await session.flush()

    await state.clear()
    await message.answer(
        "✅ Сообщение успешно обновлено!",
        reply_markup=get_campaign_actions_kb(campaign_id, campaign.status),
    )


@router.callback_query(F.data.startswith("campaign:") & F.data.endswith(":edit_intervals"))
async def campaign_edit_intervals_start(callback: CallbackQuery, state: FSMContext, db_user=None):
    """Start campaign intervals editing."""
    campaign_id = UUID(callback.data.split(":")[1])

    db_manager = get_db_manager()
    async with db_manager.readonly_session() as session:
        repo = CampaignRepository(session)
        campaign = await repo.get_by_id(campaign_id)

    if not campaign or campaign.user_id != db_user.id:
        await callback.answer("Рассылка не найдена", show_alert=True)
        return

    await state.update_data(
        edit_campaign_id=str(campaign_id),
        interval_min=campaign.interval_min,
        interval_max=campaign.interval_max,
    )

    text = """
⏱ <b>Изменение интервалов</b>

Настройте интервал между сообщениями:
"""
    await callback.message.edit_text(
        text,
        reply_markup=get_interval_settings_kb(campaign.interval_min, campaign.interval_max),
    )
    await state.set_state(CampaignEditState.editing_intervals)
    await callback.answer()


@router.callback_query(
    CampaignEditState.editing_intervals,
    F.data.startswith("interval:"),
)
async def campaign_edit_intervals_process(callback: CallbackQuery, state: FSMContext, db_user=None):
    """Process interval adjustment during editing."""
    parts = callback.data.split(":")
    action = parts[1]
    direction = parts[2] if len(parts) > 2 else None

    data = await state.get_data()
    campaign_id = UUID(data.get("edit_campaign_id"))
    interval_min = data.get("interval_min", 25)
    interval_max = data.get("interval_max", 45)

    step = 5

    if action == "min":
        if direction == "increase":
            interval_min = min(interval_min + step, interval_max - step)
        elif direction == "decrease":
            interval_min = max(5, interval_min - step)
    elif action == "max":
        if direction == "increase":
            interval_max = min(300, interval_max + step)
        elif direction == "decrease":
            interval_max = max(interval_min + step, interval_max - step)
    elif action == "confirm":
        # Save to database
        db_manager = get_db_manager()
        async with db_manager.session() as session:
            repo = CampaignRepository(session)
            campaign = await repo.get_by_id(campaign_id)
            if campaign and campaign.user_id == db_user.id:
                campaign.interval_min = interval_min
                campaign.interval_max = interval_max
                await session.flush()

        await state.clear()
        await callback.message.edit_text(
            f"✅ Интервалы обновлены: {interval_min}-{interval_max} сек",
            reply_markup=get_campaign_actions_kb(campaign_id, campaign.status),
        )
        await callback.answer()
        return
    elif action == "cancel":
        await state.clear()
        await callback.message.edit_text(
            "❌ Редактирование отменено",
            reply_markup=get_campaign_actions_kb(campaign_id, CampaignStatus.DRAFT),
        )
        await callback.answer()
        return

    await state.update_data(interval_min=interval_min, interval_max=interval_max)

    text = """
⏱ <b>Изменение интервалов</b>

Настройте интервал между сообщениями:
"""
    await callback.message.edit_text(
        text,
        reply_markup=get_interval_settings_kb(interval_min, interval_max),
    )
    await callback.answer()
