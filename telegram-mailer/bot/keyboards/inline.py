"""Common inline keyboards."""

from typing import Optional

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def get_pagination_kb(
    current_page: int,
    total_pages: int,
    callback_prefix: str,
) -> InlineKeyboardMarkup:
    """
    Build pagination keyboard.

    Args:
        current_page: Current page (0-indexed)
        total_pages: Total number of pages
        callback_prefix: Prefix for callback data

    Returns:
        InlineKeyboardMarkup
    """
    builder = InlineKeyboardBuilder()
    buttons = []

    # First page
    if current_page > 1:
        buttons.append(
            InlineKeyboardButton(
                text="⏮️",
                callback_data=f"{callback_prefix}:0",
            )
        )

    # Previous page
    if current_page > 0:
        buttons.append(
            InlineKeyboardButton(
                text="◀️",
                callback_data=f"{callback_prefix}:{current_page - 1}",
            )
        )

    # Current page indicator
    buttons.append(
        InlineKeyboardButton(
            text=f"{current_page + 1}/{total_pages}",
            callback_data=f"{callback_prefix}:current",
        )
    )

    # Next page
    if current_page < total_pages - 1:
        buttons.append(
            InlineKeyboardButton(
                text="▶️",
                callback_data=f"{callback_prefix}:{current_page + 1}",
            )
        )

    # Last page
    if current_page < total_pages - 2:
        buttons.append(
            InlineKeyboardButton(
                text="⏭️",
                callback_data=f"{callback_prefix}:{total_pages - 1}",
            )
        )

    builder.row(*buttons)
    return builder.as_markup()


def get_confirm_kb(
    confirm_callback: str,
    cancel_callback: str,
    confirm_text: str = "✅ Подтвердить",
    cancel_text: str = "❌ Отмена",
) -> InlineKeyboardMarkup:
    """
    Build confirmation keyboard.

    Args:
        confirm_callback: Callback data for confirm
        cancel_callback: Callback data for cancel
        confirm_text: Text for confirm button
        cancel_text: Text for cancel button

    Returns:
        InlineKeyboardMarkup
    """
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text=confirm_text, callback_data=confirm_callback),
        InlineKeyboardButton(text=cancel_text, callback_data=cancel_callback),
    )
    return builder.as_markup()


def get_yes_no_kb(
    yes_callback: str,
    no_callback: str,
) -> InlineKeyboardMarkup:
    """
    Build yes/no keyboard.

    Args:
        yes_callback: Callback data for yes
        no_callback: Callback data for no

    Returns:
        InlineKeyboardMarkup
    """
    return get_confirm_kb(
        confirm_callback=yes_callback,
        cancel_callback=no_callback,
        confirm_text="✅ Да",
        cancel_text="❌ Нет",
    )


def get_cancel_kb(callback_data: str = "cancel") -> InlineKeyboardMarkup:
    """Build cancel-only keyboard."""
    builder = InlineKeyboardBuilder()
    builder.add(
        InlineKeyboardButton(text="❌ Отмена", callback_data=callback_data)
    )
    return builder.as_markup()


def get_skip_kb(
    skip_callback: str,
    cancel_callback: Optional[str] = None,
) -> InlineKeyboardMarkup:
    """Build skip keyboard."""
    builder = InlineKeyboardBuilder()
    buttons = [
        InlineKeyboardButton(text="⏭️ Пропустить", callback_data=skip_callback)
    ]
    if cancel_callback:
        buttons.append(
            InlineKeyboardButton(text="❌ Отмена", callback_data=cancel_callback)
        )
    builder.row(*buttons)
    return builder.as_markup()


def get_refresh_kb(
    refresh_callback: str,
    back_callback: str,
) -> InlineKeyboardMarkup:
    """Build refresh keyboard."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔄 Обновить", callback_data=refresh_callback),
        InlineKeyboardButton(text="◀️ Назад", callback_data=back_callback),
    )
    return builder.as_markup()
