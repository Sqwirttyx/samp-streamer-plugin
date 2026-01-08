"""Registration FSM states."""

from aiogram.fsm.state import State, StatesGroup


class RegistrationState(StatesGroup):
    """States for user registration flow."""

    waiting_invite_key = State()
