"""SQLAlchemy models for the application."""

from database.models.base import BaseModel, TimestampMixin
from database.models.user import User
from database.models.account import Account
from database.models.proxy import Proxy
from database.models.folder import Folder
from database.models.campaign import Campaign, CampaignProgress
from database.models.stats import StatsHourly
from database.models.invite import InviteKey
from database.models.error_log import ErrorLog

__all__ = [
    "BaseModel",
    "TimestampMixin",
    "User",
    "Account",
    "Proxy",
    "Folder",
    "Campaign",
    "CampaignProgress",
    "StatsHourly",
    "InviteKey",
    "ErrorLog",
]
