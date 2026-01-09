"""Start handlers."""

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.config import bot_config
from bot.keyboards.main_menu import get_main_menu

router = Router(name="start")


@router.message(CommandStart())
async def cmd_start(
    message: Message,
    state: FSMContext,
    db_user=None,
    is_admin: bool = False,
):
    """Handle /start command."""
    await state.clear()

    # All users have open access - show main menu
    await message.answer(
        bot_config.WELCOME_MESSAGE,
        reply_markup=get_main_menu(is_admin),
    )


@router.message(Command("help"))
async def cmd_help(message: Message):
    """Handle /help command."""
    await message.answer(bot_config.HELP_MESSAGE)


@router.callback_query(F.data == "menu:main")
async def menu_main(
    callback: CallbackQuery,
    is_admin: bool = False,
):
    """Handle main menu callback."""
    await callback.message.edit_text(
        bot_config.WELCOME_MESSAGE,
        reply_markup=get_main_menu(is_admin),
    )
    await callback.answer()


@router.callback_query(F.data == "menu:help")
async def menu_help(callback: CallbackQuery):
    """Handle help menu callback."""
    from bot.keyboards.main_menu import get_back_button

    await callback.message.edit_text(
        bot_config.HELP_MESSAGE,
        reply_markup=get_back_button(),
    )
    await callback.answer()


@router.callback_query(F.data == "menu:settings")
async def menu_settings(callback: CallbackQuery):
    """Handle settings menu callback."""
    from bot.keyboards.main_menu import get_settings_menu

    text = """
⚙️ <b>Настройки</b>

Здесь вы можете настроить параметры работы бота.
"""
    await callback.message.edit_text(
        text,
        reply_markup=get_settings_menu(),
    )
    await callback.answer()
