"""Account authorization by code FSM states."""

from aiogram.fsm.state import State, StatesGroup


class AccountAuthState(StatesGroup):
    """States for account authorization by phone code."""

    waiting_phone = State()          # Waiting for phone number
    waiting_code = State()           # Waiting for verification code
    waiting_2fa = State()            # Waiting for 2FA password
    waiting_proxy_selection = State()  # Proxy selection for new account
    confirmation = State()           # Final confirmation
