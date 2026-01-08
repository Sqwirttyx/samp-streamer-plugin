"""Application constants."""

from enum import Enum


class AccountStatus(str, Enum):
    """Account status values."""

    ACTIVE = "active"
    PAUSED = "paused"
    BANNED = "banned"
    ERROR = "error"


class ProxyType(str, Enum):
    """Proxy type values."""

    SOCKS5 = "socks5"
    HTTP = "http"
    MTPROXY = "mtproxy"


class ProxyStatus(str, Enum):
    """Proxy status values."""

    ACTIVE = "active"
    CHECKING = "checking"
    DEAD = "dead"


class FolderStatus(str, Enum):
    """Folder status values."""

    ACTIVE = "active"
    SYNCING = "syncing"
    ERROR = "error"


class CampaignStatus(str, Enum):
    """Campaign status values."""

    DRAFT = "draft"
    SCHEDULED = "scheduled"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ERROR = "error"


class WindowType(str, Enum):
    """16/8 cycle window type."""

    USER = "user"
    ADMIN = "admin"


# Health score thresholds
HEALTH_SCORE_MIN = 0
HEALTH_SCORE_MAX = 100
HEALTH_SCORE_CRITICAL = 30
HEALTH_SCORE_WARNING = 50
HEALTH_SCORE_GOOD = 70

# FloodWait thresholds (seconds)
FLOOD_WAIT_SHORT = 60
FLOOD_WAIT_MEDIUM = 300
FLOOD_WAIT_LONG = 900

# Retry settings
MAX_FLOOD_WAIT_RETRIES = 3
FLOOD_WAIT_PAUSE_DURATION = 1800  # 30 minutes

# Cache TTL (seconds)
CACHE_TTL_FOLDER_CHATS = 3600  # 1 hour
CACHE_TTL_ACCOUNT_HEALTH = 300  # 5 minutes
CACHE_TTL_USER_SETTINGS = 600  # 10 minutes

# Redis key prefixes
REDIS_PREFIX_QUEUE = "queue"
REDIS_PREFIX_STATUS = "status"
REDIS_PREFIX_LOCK = "lock"
REDIS_PREFIX_CACHE = "cache"
REDIS_PREFIX_COUNTER = "counter"
REDIS_PREFIX_CHANNEL = "channel"

# Notification events
EVENT_ACCOUNT_BANNED = "account_banned"
EVENT_CAMPAIGN_COMPLETED = "campaign_completed"
EVENT_CAMPAIGN_ERROR = "campaign_error"
EVENT_FLOOD_WAIT = "flood_wait"
EVENT_HOURLY_REPORT = "hourly_report"
EVENT_ADMIN_WINDOW_START = "admin_window_start"
EVENT_USER_WINDOW_START = "user_window_start"
