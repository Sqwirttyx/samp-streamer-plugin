"""Account upload FSM states."""

from aiogram.fsm.state import State, StatesGroup


class AccountUploadState(StatesGroup):
    """States for account upload flow."""

    waiting_session_file = State()
    waiting_proxy_selection = State()
    confirmation = State()
