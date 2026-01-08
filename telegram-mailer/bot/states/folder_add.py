"""Folder add FSM states."""

from aiogram.fsm.state import State, StatesGroup


class FolderAddState(StatesGroup):
    """States for folder add flow."""

    waiting_link = State()
    waiting_name = State()
    selecting_account = State()
