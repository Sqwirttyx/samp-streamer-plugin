"""Cycle manager for 16/8 user/admin windows."""

from datetime import datetime, time, timedelta
from typing import Optional
from uuid import UUID

from common.config import settings
from common.constants import WindowType
from common.logger import get_logger

logger = get_logger(__name__)


class CycleManager:
    """
    Manager for 16/8 cycle logic.

    Handles user window (16h) and admin window (8h) scheduling.

    Default cycle:
    - User window: 08:00 - 00:00 (16 hours)
    - Admin window: 00:00 - 08:00 (8 hours)
    """

    def __init__(
        self,
        user_window_start: str = None,
        user_window_hours: int = None,
        admin_window_hours: int = None,
    ):
        """
        Initialize cycle manager.

        Args:
            user_window_start: User window start time (HH:MM)
            user_window_hours: Duration of user window in hours
            admin_window_hours: Duration of admin window in hours
        """
        self.user_window_start = self._parse_time(
            user_window_start or settings.default_user_window_start
        )
        self.user_window_hours = user_window_hours or settings.user_window_hours
        self.admin_window_hours = admin_window_hours or settings.admin_window_hours

        # Calculate admin window start
        self.admin_window_start = self._add_hours(
            self.user_window_start, self.user_window_hours
        )

    @staticmethod
    def _parse_time(time_str: str) -> time:
        """Parse time string (HH:MM) to time object."""
        parts = time_str.split(":")
        return time(int(parts[0]), int(parts[1]) if len(parts) > 1 else 0)

    @staticmethod
    def _add_hours(t: time, hours: int) -> time:
        """Add hours to time."""
        dt = datetime.combine(datetime.today(), t)
        dt += timedelta(hours=hours)
        return dt.time()

    def get_current_window(self, user_settings: Optional[dict] = None) -> WindowType:
        """
        Get current window type.

        Args:
            user_settings: Optional user-specific settings

        Returns:
            WindowType (USER or ADMIN)
        """
        now = datetime.now().time()

        # Get user-specific settings if available
        user_start = self.user_window_start
        if user_settings and "window_start" in user_settings:
            user_start = self._parse_time(user_settings["window_start"])

        admin_start = self._add_hours(user_start, self.user_window_hours)

        # Check if in user window
        if user_start <= admin_start:
            # Normal case: user window doesn't cross midnight
            if user_start <= now < admin_start:
                return WindowType.USER
        else:
            # User window crosses midnight
            if now >= user_start or now < admin_start:
                return WindowType.USER

        return WindowType.ADMIN

    def get_window_end_time(
        self,
        window: WindowType,
        user_settings: Optional[dict] = None,
    ) -> datetime:
        """
        Get end time of current window.

        Args:
            window: Window type
            user_settings: Optional user-specific settings

        Returns:
            Datetime when window ends
        """
        now = datetime.now()
        today = now.date()

        user_start = self.user_window_start
        if user_settings and "window_start" in user_settings:
            user_start = self._parse_time(user_settings["window_start"])

        admin_start = self._add_hours(user_start, self.user_window_hours)

        if window == WindowType.USER:
            end_time = admin_start
        else:
            end_time = user_start

        # Create datetime
        end_dt = datetime.combine(today, end_time)

        # Adjust if end is before now (next day)
        if end_dt <= now:
            end_dt += timedelta(days=1)

        return end_dt

    def get_time_until_switch(
        self,
        user_settings: Optional[dict] = None,
    ) -> timedelta:
        """
        Get time until window switch.

        Args:
            user_settings: Optional user-specific settings

        Returns:
            Timedelta until switch
        """
        current = self.get_current_window(user_settings)
        end_time = self.get_window_end_time(current, user_settings)
        return end_time - datetime.now()

    def should_switch_to_admin(
        self,
        user_settings: Optional[dict] = None,
    ) -> bool:
        """
        Check if should switch to admin window.

        Args:
            user_settings: Optional user-specific settings

        Returns:
            True if should switch to admin window
        """
        return self.get_current_window(user_settings) == WindowType.ADMIN

    def get_schedule_info(
        self,
        user_settings: Optional[dict] = None,
    ) -> dict:
        """
        Get full schedule information.

        Args:
            user_settings: Optional user-specific settings

        Returns:
            Dict with schedule info
        """
        current = self.get_current_window(user_settings)
        switch_time = self.get_window_end_time(current, user_settings)
        time_until = self.get_time_until_switch(user_settings)

        return {
            "current_window": current.value,
            "switch_at": switch_time.isoformat(),
            "time_until_switch_seconds": time_until.total_seconds(),
            "user_window_start": self.user_window_start.strftime("%H:%M"),
            "user_window_hours": self.user_window_hours,
            "admin_window_hours": self.admin_window_hours,
        }

    def is_user_window_active(
        self,
        user_settings: Optional[dict] = None,
    ) -> bool:
        """Check if user window is currently active."""
        return self.get_current_window(user_settings) == WindowType.USER

    def is_admin_window_active(
        self,
        user_settings: Optional[dict] = None,
    ) -> bool:
        """Check if admin window is currently active."""
        return self.get_current_window(user_settings) == WindowType.ADMIN


# Global cycle manager
_cycle_manager: Optional[CycleManager] = None


def get_cycle_manager() -> CycleManager:
    """Get global cycle manager."""
    global _cycle_manager
    if _cycle_manager is None:
        _cycle_manager = CycleManager()
    return _cycle_manager
