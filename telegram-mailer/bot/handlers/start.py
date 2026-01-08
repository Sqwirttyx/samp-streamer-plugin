"""Start and registration handlers."""

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.config import bot_config
from bot.keyboards.main_menu import get_main_menu
from bot.states import RegistrationState
from database import get_db_manager
from database.repositories import InviteKeyRepository, UserRepository

router = Router(name="start")


@router.message(CommandStart())
async def cmd_start(
    message: Message,
    state: FSMContext,
    db_user=None,
    is_registered: bool = False,
    is_admin: bool = False,
):
    """Handle /start command."""
    await state.clear()

    if is_registered and db_user:
        # User is registered - show main menu
        await message.answer(
            bot_config.WELCOME_MESSAGE,
            reply_markup=get_main_menu(is_admin),
        )
    else:
        # User not registered - ask for invite key
        await message.answer(bot_config.REGISTRATION_REQUIRED)
        await state.set_state(RegistrationState.waiting_invite_key)


@router.message(Command("help"))
async def cmd_help(message: Message):
    """Handle /help command."""
    await message.answer(bot_config.HELP_MESSAGE)


@router.message(RegistrationState.waiting_invite_key)
async def process_invite_key(message: Message, state: FSMContext):
    """Process invite key for registration."""
    invite_key = message.text.strip()

    db_manager = get_db_manager()
    async with db_manager.session() as session:
        invite_repo = InviteKeyRepository(session)
        user_repo = UserRepository(session)

        # Validate invite key
        is_valid = await invite_repo.validate(invite_key)
        if not is_valid:
            await message.answer(bot_config.INVALID_INVITE_KEY)
            return

        # Create user
        user = await user_repo.create_user(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            invite_key=invite_key,
            is_admin=message.from_user.id in bot_config.ADMIN_IDS,
        )

        # Mark invite key as used
        await invite_repo.use_key(invite_key, user.id)

    await state.clear()
    await message.answer(
        bot_config.REGISTRATION_SUCCESS,
        reply_markup=get_main_menu(user.is_admin),
    )


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
