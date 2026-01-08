"""Database repositories for CRUD operations."""

from database.repositories.base import BaseRepository
from database.repositories.user_repo import UserRepository
from database.repositories.account_repo import AccountRepository
from database.repositories.proxy_repo import ProxyRepository
from database.repositories.folder_repo import FolderRepository
from database.repositories.campaign_repo import CampaignRepository
from database.repositories.stats_repo import StatsRepository
from database.repositories.invite_repo import InviteKeyRepository

__all__ = [
    "BaseRepository",
    "UserRepository",
    "AccountRepository",
    "ProxyRepository",
    "FolderRepository",
    "CampaignRepository",
    "StatsRepository",
    "InviteKeyRepository",
]
