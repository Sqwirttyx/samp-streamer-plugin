"""Campaign keyboards."""

from typing import Sequence
from uuid import UUID

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from common.constants import CampaignStatus


def get_status_emoji(status: CampaignStatus) -> str:
    """Get emoji for campaign status."""
    return {
        CampaignStatus.DRAFT: "📝",
        CampaignStatus.SCHEDULED: "📅",
        CampaignStatus.ACTIVE: "▶️",
        CampaignStatus.PAUSED: "⏸️",
        CampaignStatus.COMPLETED: "✅",
        CampaignStatus.ERROR: "❌",
    }.get(status, "❓")


def get_campaigns_list_kb(
    campaigns: Sequence,
    page: int = 0,
    per_page: int = 10,
) -> InlineKeyboardMarkup:
    """
    Build campaigns list keyboard.

    Args:
        campaigns: List of Campaign models
        page: Current page number
        per_page: Items per page

    Returns:
        InlineKeyboardMarkup
    """
    builder = InlineKeyboardBuilder()

    # Calculate pagination
    start_idx = page * per_page
    end_idx = start_idx + per_page
    page_campaigns = campaigns[start_idx:end_idx]

    # Campaign buttons
    for campaign in page_campaigns:
        status_emoji = get_status_emoji(campaign.status)
        text = f"{status_emoji} {campaign.name}"
        builder.row(
            InlineKeyboardButton(
                text=text,
                callback_data=f"campaign:{campaign.id}:view",
            )
        )

    # Pagination
    total_pages = (len(campaigns) + per_page - 1) // per_page
    if total_pages > 1:
        pagination_buttons = []
        if page > 0:
            pagination_buttons.append(
                InlineKeyboardButton(
                    text="◀️",
                    callback_data=f"campaigns:page:{page - 1}",
                )
            )
        pagination_buttons.append(
            InlineKeyboardButton(
                text=f"{page + 1}/{total_pages}",
                callback_data="campaigns:page:current",
            )
        )
        if page < total_pages - 1:
            pagination_buttons.append(
                InlineKeyboardButton(
                    text="▶️",
                    callback_data=f"campaigns:page:{page + 1}",
                )
            )
        builder.row(*pagination_buttons)

    # Create campaign button
    builder.row(
        InlineKeyboardButton(
            text="➕ Создать рассылку",
            callback_data="campaign:create",
        )
    )

    # Back button
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="menu:main"),
    )

    return builder.as_markup()


def get_campaign_actions_kb(
    campaign_id: UUID,
    status: CampaignStatus,
) -> InlineKeyboardMarkup:
    """
    Build campaign actions keyboard.

    Args:
        campaign_id: Campaign UUID
        status: Current campaign status

    Returns:
        InlineKeyboardMarkup
    """
    builder = InlineKeyboardBuilder()

    # Status-dependent actions
    if status in (CampaignStatus.DRAFT, CampaignStatus.PAUSED):
        builder.row(
            InlineKeyboardButton(
                text="▶️ Запустить",
                callback_data=f"campaign:{campaign_id}:start",
            )
        )
    elif status == CampaignStatus.ACTIVE:
        builder.row(
            InlineKeyboardButton(
                text="⏸️ Приостановить",
                callback_data=f"campaign:{campaign_id}:pause",
            )
        )
        builder.row(
            InlineKeyboardButton(
                text="⏹️ Остановить",
                callback_data=f"campaign:{campaign_id}:stop",
            )
        )

    # Edit (only for non-active)
    if status != CampaignStatus.ACTIVE:
        builder.row(
            InlineKeyboardButton(
                text="✏️ Редактировать",
                callback_data=f"campaign:{campaign_id}:edit",
            )
        )

    # Statistics
    builder.row(
        InlineKeyboardButton(
            text="📊 Статистика",
            callback_data=f"campaign:{campaign_id}:stats",
        )
    )

    # Delete (only for non-active)
    if status != CampaignStatus.ACTIVE:
        builder.row(
            InlineKeyboardButton(
                text="🗑️ Удалить",
                callback_data=f"campaign:{campaign_id}:delete",
            )
        )

    # Back
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="menu:campaigns"),
    )

    return builder.as_markup()


def get_interval_settings_kb(
    current_min: int,
    current_max: int,
    step: int = 5,
) -> InlineKeyboardMarkup:
    """
    Build interval settings keyboard.

    Args:
        current_min: Current minimum interval
        current_max: Current maximum interval
        step: Adjustment step

    Returns:
        InlineKeyboardMarkup
    """
    builder = InlineKeyboardBuilder()

    # Min interval row
    builder.row(
        InlineKeyboardButton(text="⬇️", callback_data=f"interval:min:decrease"),
        InlineKeyboardButton(text=f"Мин: {current_min}с", callback_data="interval:min:current"),
        InlineKeyboardButton(text="⬆️", callback_data=f"interval:min:increase"),
    )

    # Max interval row
    builder.row(
        InlineKeyboardButton(text="⬇️", callback_data=f"interval:max:decrease"),
        InlineKeyboardButton(text=f"Макс: {current_max}с", callback_data="interval:max:current"),
        InlineKeyboardButton(text="⬆️", callback_data=f"interval:max:increase"),
    )

    # Confirm/Cancel
    builder.row(
        InlineKeyboardButton(text="✅ Подтвердить", callback_data="interval:confirm"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="interval:cancel"),
    )

    return builder.as_markup()


def get_work_rest_settings_kb(
    work_hours: int,
    rest_minutes: int,
) -> InlineKeyboardMarkup:
    """
    Build work/rest settings keyboard.

    Args:
        work_hours: Hours of work before rest
        rest_minutes: Rest duration in minutes

    Returns:
        InlineKeyboardMarkup
    """
    builder = InlineKeyboardBuilder()

    # Work hours row
    builder.row(
        InlineKeyboardButton(text="⬇️", callback_data="work:decrease"),
        InlineKeyboardButton(text=f"Работа: {work_hours}ч", callback_data="work:current"),
        InlineKeyboardButton(text="⬆️", callback_data="work:increase"),
    )

    # Rest minutes row
    builder.row(
        InlineKeyboardButton(text="⬇️", callback_data="rest:decrease"),
        InlineKeyboardButton(text=f"Отдых: {rest_minutes}мин", callback_data="rest:current"),
        InlineKeyboardButton(text="⬆️", callback_data="rest:increase"),
    )

    # Confirm/Cancel
    builder.row(
        InlineKeyboardButton(text="✅ Подтвердить", callback_data="workrest:confirm"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="workrest:cancel"),
    )

    return builder.as_markup()


def get_account_selection_kb(
    accounts: Sequence,
    selected_id: UUID = None,
) -> InlineKeyboardMarkup:
    """Build account selection keyboard for campaign creation."""
    builder = InlineKeyboardBuilder()

    for account in accounts:
        is_selected = str(account.id) == str(selected_id) if selected_id else False
        prefix = "✅ " if is_selected else ""

        phone_display = f"***{account.phone_hash[:4]}"
        text = f"{prefix}📱 {phone_display} | {account.health_score}%"
        builder.row(
            InlineKeyboardButton(
                text=text,
                callback_data=f"campaign:select_account:{account.id}",
            )
        )

    builder.row(
        InlineKeyboardButton(text="❌ Отмена", callback_data="menu:campaigns"),
    )

    return builder.as_markup()


def get_folder_selection_kb(
    folders: Sequence,
    selected_id: UUID = None,
) -> InlineKeyboardMarkup:
    """Build folder selection keyboard for campaign creation."""
    builder = InlineKeyboardBuilder()

    for folder in folders:
        is_selected = str(folder.id) == str(selected_id) if selected_id else False
        prefix = "✅ " if is_selected else ""

        text = f"{prefix}📁 {folder.name} ({folder.chat_count} чатов)"
        builder.row(
            InlineKeyboardButton(
                text=text,
                callback_data=f"campaign:select_folder:{folder.id}",
            )
        )

    builder.row(
        InlineKeyboardButton(text="❌ Отмена", callback_data="menu:campaigns"),
    )

    return builder.as_markup()
