"""Account keyboards."""

from typing import Sequence
from uuid import UUID

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from common.constants import AccountStatus


def get_status_emoji(status: AccountStatus) -> str:
    """Get emoji for account status."""
    return {
        AccountStatus.ACTIVE: "✅",
        AccountStatus.PAUSED: "⏸️",
        AccountStatus.BANNED: "🚫",
        AccountStatus.ERROR: "❌",
    }.get(status, "❓")


def get_health_emoji(health_score: int) -> str:
    """Get emoji for health score."""
    if health_score >= 80:
        return "💚"
    elif health_score >= 50:
        return "💛"
    else:
        return "❤️"


def get_accounts_list_kb(
    accounts: Sequence,
    page: int = 0,
    per_page: int = 10,
) -> InlineKeyboardMarkup:
    """
    Build accounts list keyboard.

    Args:
        accounts: List of Account models
        page: Current page number
        per_page: Items per page

    Returns:
        InlineKeyboardMarkup
    """
    builder = InlineKeyboardBuilder()

    # Calculate pagination
    start_idx = page * per_page
    end_idx = start_idx + per_page
    page_accounts = accounts[start_idx:end_idx]

    # Account buttons
    for account in page_accounts:
        status_emoji = get_status_emoji(account.status)
        health_emoji = get_health_emoji(account.health_score)

        # Show masked phone hash
        phone_display = f"***{account.phone_hash[:4]}"

        text = f"📱 {phone_display} | {status_emoji} | {health_emoji} {account.health_score}%"
        builder.row(
            InlineKeyboardButton(
                text=text,
                callback_data=f"account:{account.id}:view",
            )
        )

    # Pagination
    total_pages = (len(accounts) + per_page - 1) // per_page
    if total_pages > 1:
        pagination_buttons = []
        if page > 0:
            pagination_buttons.append(
                InlineKeyboardButton(
                    text="◀️",
                    callback_data=f"accounts:page:{page - 1}",
                )
            )
        pagination_buttons.append(
            InlineKeyboardButton(
                text=f"{page + 1}/{total_pages}",
                callback_data="accounts:page:current",
            )
        )
        if page < total_pages - 1:
            pagination_buttons.append(
                InlineKeyboardButton(
                    text="▶️",
                    callback_data=f"accounts:page:{page + 1}",
                )
            )
        builder.row(*pagination_buttons)

    # Add account buttons
    builder.row(
        InlineKeyboardButton(
            text="📲 Добавить по номеру",
            callback_data="account:add_by_code",
        ),
        InlineKeyboardButton(
            text="📁 Загрузить .session",
            callback_data="account:add",
        ),
    )

    # Back button
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="menu:main"),
    )

    return builder.as_markup()


def get_account_actions_kb(
    account_id: UUID,
    status: AccountStatus,
) -> InlineKeyboardMarkup:
    """
    Build account actions keyboard.

    Args:
        account_id: Account UUID
        status: Current account status

    Returns:
        InlineKeyboardMarkup
    """
    builder = InlineKeyboardBuilder()

    # Status toggle
    if status == AccountStatus.ACTIVE:
        builder.row(
            InlineKeyboardButton(
                text="⏸️ Приостановить",
                callback_data=f"account:{account_id}:pause",
            )
        )
    elif status == AccountStatus.PAUSED:
        builder.row(
            InlineKeyboardButton(
                text="▶️ Возобновить",
                callback_data=f"account:{account_id}:resume",
            )
        )

    # Health check
    builder.row(
        InlineKeyboardButton(
            text="🔄 Проверить здоровье",
            callback_data=f"account:{account_id}:check",
        )
    )

    # Proxy management
    builder.row(
        InlineKeyboardButton(
            text="🌐 Изменить прокси",
            callback_data=f"account:{account_id}:change_proxy",
        )
    )

    # View campaigns
    builder.row(
        InlineKeyboardButton(
            text="📨 Рассылки аккаунта",
            callback_data=f"account:{account_id}:campaigns",
        )
    )

    # Delete
    builder.row(
        InlineKeyboardButton(
            text="🗑️ Удалить",
            callback_data=f"account:{account_id}:delete",
        )
    )

    # Back
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="menu:accounts"),
    )

    return builder.as_markup()


def get_account_confirm_kb(account_id: UUID) -> InlineKeyboardMarkup:
    """Build account deletion confirmation keyboard."""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text="✅ Да, удалить",
            callback_data=f"account:{account_id}:confirm_delete",
        ),
        InlineKeyboardButton(
            text="❌ Отмена",
            callback_data=f"account:{account_id}:view",
        ),
    )

    return builder.as_markup()


def get_proxy_selection_kb(
    proxies: Sequence,
    account_id: UUID,
    current_proxy_id: UUID = None,
) -> InlineKeyboardMarkup:
    """Build proxy selection keyboard for account."""
    builder = InlineKeyboardBuilder()

    for proxy in proxies:
        is_current = str(proxy.id) == str(current_proxy_id) if current_proxy_id else False
        prefix = "✅ " if is_current else ""

        text = f"{prefix}{proxy.type.value} | {proxy.host}:{proxy.port}"
        builder.row(
            InlineKeyboardButton(
                text=text,
                callback_data=f"account:{account_id}:set_proxy:{proxy.id}",
            )
        )

    # No proxy option
    builder.row(
        InlineKeyboardButton(
            text="🚫 Без прокси",
            callback_data=f"account:{account_id}:set_proxy:none",
        )
    )

    # Back
    builder.row(
        InlineKeyboardButton(
            text="◀️ Назад",
            callback_data=f"account:{account_id}:view",
        )
    )

    return builder.as_markup()
