"""Admin message management FSM states."""

from aiogram.fsm.state import State, StatesGroup


class AdminMessageState(StatesGroup):
    """States for admin message management flow."""

    adding_name = State()
    adding_text = State()
    adding_media = State()
    adding_footer = State()
    editing_text = State()
    editing_footer = State()
