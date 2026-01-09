"""Application constants."""

from enum import Enum


class AccountStatus(str, Enum):
    """Account status values."""

    WARMING_UP = "warming_up"  # New account in warming phase
    ACTIVE = "active"
    PAUSED = "paused"
    QUARANTINE = "quarantine"  # Temporary restriction
    BANNED = "banned"
    ERROR = "error"


class TrustLevel(str, Enum):
    """Trust level for accounts."""

    QUARANTINE = "quarantine"  # Score 0-20: Don't use
    WARMING = "warming"        # Score 20-40: Light tasks only
    LOW = "low"                # Score 40-60: Limited use
    MEDIUM = "medium"          # Score 60-80: Normal use
    HIGH = "high"              # Score 80-100: Priority use


class WarmingPhase(str, Enum):
    """Account warming phases."""

    PHASE_1 = "phase_1"  # Days 1-7: Profile setup, subscribe channels
    PHASE_2 = "phase_2"  # Days 8-21: Join groups, add contacts
    PHASE_3 = "phase_3"  # Days 22-42: Light messaging
    PHASE_4 = "phase_4"  # Days 43+: Ready for campaigns


class SendingMode(str, Enum):
    """Sending mode for campaigns."""

    SAFE = "safe"              # Conservative: 30-50 msg/day, 60-180s delay
    NORMAL = "normal"          # Balanced: 100-200 msg/day, 30-60s delay
    AGGRESSIVE = "aggressive"  # Maximum: 7000-9000 msg/day, 3-10s delay


class ProxyType(str, Enum):
    """Proxy type values."""

    SOCKS5 = "socks5"
    HTTP = "http"
    MTPROXY = "mtproxy"


class ProxyQuality(str, Enum):
    """Proxy quality/type for prioritization."""

    MOBILE_RESIDENTIAL = "mobile_residential"  # Best
    RESIDENTIAL = "residential"                # Good
    DATACENTER = "datacenter"                  # Acceptable
    FREE = "free"                              # Avoid


class ProxyStatus(str, Enum):
    """Proxy status values."""

    ACTIVE = "active"
    CHECKING = "checking"
    SUSPICIOUS = "suspicious"
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


# =============================================================================
# TRUST SCORE CONFIGURATION
# =============================================================================

# Trust score thresholds
TRUST_SCORE_QUARANTINE = 20
TRUST_SCORE_WARMING = 40
TRUST_SCORE_LOW = 60
TRUST_SCORE_MEDIUM = 80
TRUST_SCORE_HIGH = 100

# Trust level limits (messages per day, messages per hour, min delay seconds)
TRUST_LIMITS = {
    TrustLevel.QUARANTINE: {
        "messages_per_day": 0,
        "messages_per_hour": 0,
        "min_delay_seconds": 999,
        "can_send": False,
    },
    TrustLevel.WARMING: {
        "messages_per_day": 5,
        "messages_per_hour": 2,
        "min_delay_seconds": 300,
        "can_send": True,
    },
    TrustLevel.LOW: {
        "messages_per_day": 15,
        "messages_per_hour": 5,
        "min_delay_seconds": 120,
        "can_send": True,
    },
    TrustLevel.MEDIUM: {
        "messages_per_day": 30,
        "messages_per_hour": 10,
        "min_delay_seconds": 60,
        "can_send": True,
    },
    TrustLevel.HIGH: {
        "messages_per_day": 50,
        "messages_per_hour": 15,
        "min_delay_seconds": 45,
        "can_send": True,
    },
}

# =============================================================================
# WARMING PHASE CONFIGURATION
# =============================================================================

WARMING_PHASES = {
    WarmingPhase.PHASE_1: {
        "duration_days": 7,
        "min_age_days": 0,
        "daily_activity": {
            "read_posts": (10, 30),
            "react_to_posts": (0, 3),
            "subscribe_channels": (0, 2),
        },
    },
    WarmingPhase.PHASE_2: {
        "duration_days": 14,
        "min_age_days": 7,
        "daily_activity": {
            "read_posts": (20, 50),
            "react_to_posts": (1, 5),
            "join_groups": (0, 1),
            "add_contacts": (0, 2),
        },
    },
    WarmingPhase.PHASE_3: {
        "duration_days": 21,
        "min_age_days": 21,
        "daily_activity": {
            "read_posts": (30, 70),
            "react_to_posts": (2, 8),
            "send_to_contacts": (0, 1),
            "group_messages": (0, 1),
        },
    },
    WarmingPhase.PHASE_4: {
        "duration_days": None,  # Indefinite
        "min_age_days": 42,
        "daily_activity": {
            "read_posts": (10, 30),
            "react_to_posts": (1, 3),
        },
    },
}

# =============================================================================
# SENDING MODE CONFIGURATION
# =============================================================================

SENDING_MODE_CONFIG = {
    SendingMode.SAFE: {
        "min_delay": 60,
        "max_delay": 180,
        "messages_per_day": 50,
        "burst_size": 3,
        "burst_pause": 600,
        "flood_wait_multiplier": 1.2,
        "description": "Conservative mode for maximum safety",
    },
    SendingMode.NORMAL: {
        "min_delay": 30,
        "max_delay": 60,
        "messages_per_day": 200,
        "burst_size": 5,
        "burst_pause": 120,
        "flood_wait_multiplier": 1.15,
        "description": "Balanced mode for regular campaigns",
    },
    SendingMode.AGGRESSIVE: {
        "min_delay": 3,
        "max_delay": 10,
        "messages_per_day": 9000,
        "burst_size": 20,
        "burst_pause": 30,
        "flood_wait_multiplier": 1.1,
        "description": "Maximum throughput (7000-9000 msg/day)",
    },
}

# =============================================================================
# AGGRESSIVE MODE REQUIREMENTS
# =============================================================================

AGGRESSIVE_REQUIREMENTS = {
    "min_age_days": 180,        # Minimum 6 months
    "recommended_age_days": 365,  # Better 1+ year
    "optimal_age_days": 730,    # Best 2+ years
    "premium_required": False,   # Recommended but not required
    "min_trust_score": 60,      # At least MEDIUM trust level
}

# =============================================================================
# HEALTH SCORE THRESHOLDS
# =============================================================================

HEALTH_SCORE_MIN = 0
HEALTH_SCORE_MAX = 100
HEALTH_SCORE_CRITICAL = 30
HEALTH_SCORE_WARNING = 50
HEALTH_SCORE_GOOD = 70

# =============================================================================
# FLOODWAIT CONFIGURATION
# =============================================================================

FLOOD_WAIT_SHORT = 60
FLOOD_WAIT_MEDIUM = 300
FLOOD_WAIT_LONG = 900
FLOOD_WAIT_MAX_ACCEPTABLE = 300  # 5 min - above this, skip and continue

MAX_FLOOD_WAIT_RETRIES = 3
FLOOD_WAIT_PAUSE_DURATION = 1800  # 30 minutes

# =============================================================================
# CACHE TTL (seconds)
# =============================================================================

CACHE_TTL_FOLDER_CHATS = 3600  # 1 hour
CACHE_TTL_ACCOUNT_HEALTH = 300  # 5 minutes
CACHE_TTL_USER_SETTINGS = 600  # 10 minutes

# =============================================================================
# REDIS KEY PREFIXES
# =============================================================================

REDIS_PREFIX_QUEUE = "queue"
REDIS_PREFIX_STATUS = "status"
REDIS_PREFIX_LOCK = "lock"
REDIS_PREFIX_CACHE = "cache"
REDIS_PREFIX_COUNTER = "counter"
REDIS_PREFIX_CHANNEL = "channel"
REDIS_PREFIX_MESSAGES = "messages"  # For tracking daily/hourly message counts

# =============================================================================
# NOTIFICATION EVENTS
# =============================================================================

EVENT_ACCOUNT_BANNED = "account_banned"
EVENT_ACCOUNT_RESTRICTED = "account_restricted"
EVENT_ACCOUNT_QUARANTINE = "account_quarantine"
EVENT_ACCOUNT_WARMING_COMPLETE = "account_warming_complete"
EVENT_CAMPAIGN_COMPLETED = "campaign_completed"
EVENT_CAMPAIGN_ERROR = "campaign_error"
EVENT_FLOOD_WAIT = "flood_wait"
EVENT_HOURLY_REPORT = "hourly_report"
EVENT_DAILY_REPORT = "daily_report"
EVENT_ADMIN_WINDOW_START = "admin_window_start"
EVENT_USER_WINDOW_START = "user_window_start"
EVENT_TRUST_SCORE_CHANGED = "trust_score_changed"

# =============================================================================
# TEXT VARIATION
# =============================================================================

# Zero-width characters for message uniqueness
INVISIBLE_CHARS = [
    '\u200b',  # Zero-width space
    '\u200c',  # Zero-width non-joiner
    '\u200d',  # Zero-width joiner
    '\u2060',  # Word joiner
    '\ufeff',  # Zero-width no-break space
]

# Popular device models for fingerprinting
DEVICE_MODELS = [
    ('Samsung', 'SM-G998B', 'Galaxy S21 Ultra'),
    ('Samsung', 'SM-S908B', 'Galaxy S22 Ultra'),
    ('Samsung', 'SM-A536B', 'Galaxy A53'),
    ('Samsung', 'SM-A546B', 'Galaxy A54'),
    ('Xiaomi', 'Redmi Note 11', 'Redmi Note 11'),
    ('Xiaomi', 'Redmi Note 12', 'Redmi Note 12'),
    ('Xiaomi', '2201117TY', 'Xiaomi 12'),
    ('OnePlus', 'LE2125', 'OnePlus 9 Pro'),
    ('Google', 'Pixel 7', 'Pixel 7'),
    ('Google', 'Pixel 7 Pro', 'Pixel 7 Pro'),
]

ANDROID_VERSIONS = [
    ('12', '31'),
    ('13', '33'),
    ('14', '34'),
]
