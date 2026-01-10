"""Campaign creation FSM states."""

from aiogram.fsm.state import State, StatesGroup


class CampaignCreateState(StatesGroup):
    """States for campaign creation flow."""

    entering_name = State()
    selecting_account = State()
    selecting_folder = State()
    waiting_message = State()  # User sends message to bot
    setting_intervals = State()
    setting_work_hours = State()
    setting_rest = State()
    confirmation = State()


class CampaignEditState(StatesGroup):
    """States for campaign editing flow."""

    editing_name = State()
    editing_message = State()
    editing_intervals = State()
