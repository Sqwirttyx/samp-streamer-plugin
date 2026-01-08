"""Work/rest cycle management for antispam."""

import asyncio
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Optional

from common.logger import get_logger

logger = get_logger(__name__)


@dataclass
class RestPeriod:
    """Rest period definition."""

    start_time: datetime
    end_time: datetime
    reason: str


class RestManager:
    """
    Manager for work/rest cycles.

    Implements intelligent rest periods to avoid spam detection:
    - Scheduled rest breaks during work
    - Adaptive rest based on health
    - Night rest periods
    """

    # Default work hours
    DEFAULT_WORK_START = time(8, 0)  # 08:00
    DEFAULT_WORK_END = time(23, 0)  # 23:00

    # Rest parameters
    DEFAULT_WORK_DURATION_MINUTES = 45
    DEFAULT_REST_DURATION_MINUTES = 15
    MIN_REST_DURATION_MINUTES = 5
    MAX_REST_DURATION_MINUTES = 60

    def __init__(
        self,
        work_hours: Optional[tuple[time, time]] = None,
        work_duration_minutes: int = DEFAULT_WORK_DURATION_MINUTES,
        rest_duration_minutes: int = DEFAULT_REST_DURATION_MINUTES,
    ):
        """
        Initialize rest manager.

        Args:
            work_hours: Tuple of (start_time, end_time) for work window
            work_duration_minutes: Minutes to work before rest
            rest_duration_minutes: Minutes to rest
        """
        if work_hours:
            self.work_start, self.work_end = work_hours
        else:
            self.work_start = self.DEFAULT_WORK_START
            self.work_end = self.DEFAULT_WORK_END

        self.work_duration = timedelta(minutes=work_duration_minutes)
        self.rest_duration = timedelta(
            minutes=max(
                self.MIN_REST_DURATION_MINUTES,
                min(self.MAX_REST_DURATION_MINUTES, rest_duration_minutes),
            )
        )

        self._last_work_start: Optional[datetime] = None
        self._last_rest_end: Optional[datetime] = None
        self._current_rest: Optional[RestPeriod] = None
        self._forced_rest_until: Optional[datetime] = None

    def start_work_session(self) -> None:
        """Mark start of work session."""
        self._last_work_start = datetime.now()
        self._last_rest_end = datetime.now()
        logger.info("Work session started")

    def is_work_hours(self) -> bool:
        """
        Check if current time is within work hours.

        Returns:
            True if within work hours
        """
        now = datetime.now().time()

        # Handle overnight work (e.g., 22:00 - 06:00)
        if self.work_start > self.work_end:
            return now >= self.work_start or now < self.work_end

        return self.work_start <= now < self.work_end

    def should_rest(self) -> bool:
        """
        Check if it's time to rest.

        Returns:
            True if should take a rest break
        """
        # Check forced rest
        if self._forced_rest_until:
            if datetime.now() < self._forced_rest_until:
                return True
            self._forced_rest_until = None

        # Not work hours = rest
        if not self.is_work_hours():
            return True

        # Check if worked long enough
        if self._last_rest_end:
            work_time = datetime.now() - self._last_rest_end
            if work_time >= self.work_duration:
                return True

        return False

    def get_rest_duration(self, health_score: int = 100) -> timedelta:
        """
        Get rest duration, adjusted for health.

        Args:
            health_score: Account health score

        Returns:
            Rest duration
        """
        base_rest = self.rest_duration

        # Increase rest for poor health
        if health_score < 30:
            return base_rest * 3
        elif health_score < 50:
            return base_rest * 2
        elif health_score < 70:
            return timedelta(seconds=int(base_rest.total_seconds() * 1.5))

        return base_rest

    async def take_rest(self, reason: str = "scheduled", health_score: int = 100) -> None:
        """
        Take a rest period.

        Args:
            reason: Reason for rest
            health_score: Current health score
        """
        rest_duration = self.get_rest_duration(health_score)
        start = datetime.now()
        end = start + rest_duration

        self._current_rest = RestPeriod(
            start_time=start,
            end_time=end,
            reason=reason,
        )

        logger.info(
            f"Starting rest period: {rest_duration.total_seconds():.0f}s, "
            f"reason: {reason}"
        )

        await asyncio.sleep(rest_duration.total_seconds())

        self._last_rest_end = datetime.now()
        self._current_rest = None

        logger.info("Rest period ended")

    def force_rest(self, duration_minutes: int, reason: str = "forced") -> None:
        """
        Force a rest period.

        Args:
            duration_minutes: Rest duration in minutes
            reason: Reason for forced rest
        """
        self._forced_rest_until = datetime.now() + timedelta(minutes=duration_minutes)
        logger.warning(
            f"Forced rest for {duration_minutes} minutes, reason: {reason}"
        )

    def get_time_until_work(self) -> Optional[timedelta]:
        """
        Get time until next work period starts.

        Returns:
            Time until work, or None if in work hours
        """
        if self.is_work_hours():
            return None

        now = datetime.now()
        today_work_start = datetime.combine(now.date(), self.work_start)

        if now.time() < self.work_start:
            # Work starts later today
            return today_work_start - now
        else:
            # Work starts tomorrow
            tomorrow_work_start = today_work_start + timedelta(days=1)
            return tomorrow_work_start - now

    def get_time_until_rest(self) -> Optional[timedelta]:
        """
        Get time until next rest period.

        Returns:
            Time until rest, or None if should rest now
        """
        if self.should_rest():
            return None

        if not self._last_rest_end:
            return None

        next_rest = self._last_rest_end + self.work_duration
        return max(timedelta(0), next_rest - datetime.now())

    async def wait_for_work_hours(self) -> None:
        """Wait until work hours begin."""
        wait_time = self.get_time_until_work()

        if wait_time and wait_time.total_seconds() > 0:
            logger.info(
                f"Waiting {wait_time.total_seconds():.0f}s for work hours"
            )
            await asyncio.sleep(wait_time.total_seconds())

    def is_resting(self) -> bool:
        """Check if currently in rest period."""
        return self._current_rest is not None

    def get_current_rest(self) -> Optional[RestPeriod]:
        """Get current rest period if any."""
        return self._current_rest

    def get_status(self) -> dict:
        """Get current rest manager status."""
        return {
            "is_work_hours": self.is_work_hours(),
            "should_rest": self.should_rest(),
            "is_resting": self.is_resting(),
            "work_start": self.work_start.isoformat(),
            "work_end": self.work_end.isoformat(),
            "work_duration_minutes": self.work_duration.total_seconds() / 60,
            "rest_duration_minutes": self.rest_duration.total_seconds() / 60,
            "time_until_work": (
                self.get_time_until_work().total_seconds()
                if self.get_time_until_work()
                else None
            ),
            "time_until_rest": (
                self.get_time_until_rest().total_seconds()
                if self.get_time_until_rest()
                else None
            ),
            "current_rest": (
                {
                    "start": self._current_rest.start_time.isoformat(),
                    "end": self._current_rest.end_time.isoformat(),
                    "reason": self._current_rest.reason,
                }
                if self._current_rest
                else None
            ),
            "forced_rest_until": (
                self._forced_rest_until.isoformat()
                if self._forced_rest_until
                else None
            ),
        }


class AdaptiveRestManager(RestManager):
    """
    Rest manager with adaptive behavior based on sending patterns.

    Adjusts work/rest cycles based on:
    - Message send rate
    - FloodWait frequency
    - Time of day patterns
    """

    def __init__(self, *args, **kwargs):
        """Initialize adaptive rest manager."""
        super().__init__(*args, **kwargs)
        self._send_count = 0
        self._flood_wait_count = 0
        self._session_start: Optional[datetime] = None

    def record_send(self) -> None:
        """Record successful message send."""
        self._send_count += 1

    def record_flood_wait(self) -> None:
        """Record FloodWait occurrence."""
        self._flood_wait_count += 1

        # Force rest if too many flood waits
        if self._flood_wait_count >= 3:
            self.force_rest(30, reason="multiple_flood_waits")
            self._flood_wait_count = 0

    def get_adaptive_rest_duration(self) -> timedelta:
        """
        Get rest duration adapted to current conditions.

        Returns:
            Adaptive rest duration
        """
        base = self.rest_duration

        # Increase rest during peak hours (12:00 - 14:00, 18:00 - 21:00)
        hour = datetime.now().hour
        if hour in (12, 13, 18, 19, 20):
            base = timedelta(seconds=int(base.total_seconds() * 1.5))

        # Increase rest if high send rate
        if self._session_start:
            session_minutes = (
                datetime.now() - self._session_start
            ).total_seconds() / 60
            if session_minutes > 0:
                rate = self._send_count / session_minutes
                if rate > 3:  # More than 3 per minute
                    base = timedelta(seconds=int(base.total_seconds() * 2))

        return base

    def start_work_session(self) -> None:
        """Mark start of work session."""
        super().start_work_session()
        self._session_start = datetime.now()
        self._send_count = 0
        self._flood_wait_count = 0

    def get_session_stats(self) -> dict:
        """Get current session statistics."""
        session_duration = None
        if self._session_start:
            session_duration = (
                datetime.now() - self._session_start
            ).total_seconds()

        return {
            "session_duration_seconds": session_duration,
            "send_count": self._send_count,
            "flood_wait_count": self._flood_wait_count,
            "sends_per_minute": (
                self._send_count / (session_duration / 60)
                if session_duration and session_duration > 60
                else None
            ),
        }
