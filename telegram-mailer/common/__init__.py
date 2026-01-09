"""Common utilities and shared components."""

# Don't import settings here to avoid loading config during migrations
# Import settings directly where needed: from common.config import settings
from common.logger import get_logger

__all__ = ["get_logger"]
