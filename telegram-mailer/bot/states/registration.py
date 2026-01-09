"""Admin FSM states."""

from aiogram.fsm.state import State, StatesGroup


class AdminAuthState(StatesGroup):
    """States for admin authentication flow."""

    waiting_master_key = State()
