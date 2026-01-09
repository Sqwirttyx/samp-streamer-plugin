"""FSM states for bot handlers."""

from bot.states.registration import AdminAuthState
from bot.states.account_upload import AccountUploadState
from bot.states.account_auth import AccountAuthState
from bot.states.campaign_create import CampaignCreateState
from bot.states.folder_add import FolderAddState
from bot.states.proxy_add import ProxyAddState

__all__ = [
    "AdminAuthState",
    "AccountUploadState",
    "AccountAuthState",
    "CampaignCreateState",
    "FolderAddState",
    "ProxyAddState",
]
