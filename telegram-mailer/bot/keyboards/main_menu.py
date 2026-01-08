"""Main menu keyboards."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def get_main_menu(is_admin: bool = False) -> InlineKeyboardMarkup:
    """
    Build main menu keyboard.

    Args:
        is_admin: Whether user is admin

    Returns:
        InlineKeyboardMarkup
    """
    builder = InlineKeyboardBuilder()

    # Row 1
    builder.row(
        InlineKeyboardButton(text="📱 Мои аккаунты", callback_data="menu:accounts"),
        InlineKeyboardButton(text="📁 Мои папки", callback_data="menu:folders"),
    )

    # Row 2
    builder.row(
        InlineKeyboardButton(text="📨 Рассылки", callback_data="menu:campaigns"),
        InlineKeyboardButton(text="🌐 Прокси", callback_data="menu:proxy"),
    )

    # Row 3
    builder.row(
        InlineKeyboardButton(text="📊 Статистика", callback_data="menu:stats"),
        InlineKeyboardButton(text="⚙️ Настройки", callback_data="menu:settings"),
    )

    # Admin row
    if is_admin:
        builder.row(
            InlineKeyboardButton(text="👑 Админ-панель", callback_data="menu:admin"),
        )

    # Help row
    builder.row(
        InlineKeyboardButton(text="❓ Помощь", callback_data="menu:help"),
    )

    return builder.as_markup()


def get_back_button(callback_data: str = "menu:main") -> InlineKeyboardMarkup:
    """
    Build back button keyboard.

    Args:
        callback_data: Callback data for back button

    Returns:
        InlineKeyboardMarkup
    """
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="◀️ Назад", callback_data=callback_data))
    return builder.as_markup()


def get_settings_menu() -> InlineKeyboardMarkup:
    """Build settings menu keyboard."""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text="🕐 Время начала рассылки",
            callback_data="settings:window_start",
        ),
    )
    builder.row(
        InlineKeyboardButton(
            text="📊 Уведомления",
            callback_data="settings:notifications",
        ),
    )
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="menu:main"),
    )

    return builder.as_markup()
