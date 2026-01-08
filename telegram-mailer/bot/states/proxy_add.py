"""Proxy add FSM states."""

from aiogram.fsm.state import State, StatesGroup


class ProxyAddState(StatesGroup):
    """States for proxy add flow."""

    waiting_data = State()  # format: type://user:pass@host:port
