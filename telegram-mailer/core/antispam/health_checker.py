"""Account health checking and scoring."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from common.constants import (
    HEALTH_SCORE_CRITICAL,
    HEALTH_SCORE_MAX,
    HEALTH_SCORE_WARNING,
)
from common.logger import get_logger

logger = get_logger(__name__)


@dataclass
class HealthEvent:
    """Single health event."""

    event_type: str
    timestamp: datetime
    impact: int  # Negative for penalties, positive for recovery


class HealthChecker:
    """
    Account health checker and scorer.

    Tracks account health based on:
    - FloodWait occurrences
    - Errors
    - Successful sends
    - Time since last issue
    """

    # Event impacts
    FLOOD_WAIT_PENALTY = -15
    ERROR_PENALTY = -5
    SUCCESS_RECOVERY = 2
    TIME_RECOVERY_PER_HOUR = 3

    # Thresholds
    FLOOD_WAIT_CRITICAL_COUNT = 3
    ERROR_CRITICAL_COUNT = 10

    def __init__(self, initial_score: int = HEALTH_SCORE_MAX):
        """
        Initialize health checker.

        Args:
            initial_score: Starting health score
        """
        self.current_score = initial_score
        self.events: list[HealthEvent] = []
        self.flood_wait_count = 0
        self.error_count = 0
        self.success_count = 0
        self.last_flood_wait: Optional[datetime] = None
        self.last_error: Optional[datetime] = None

    def record_flood_wait(self, wait_seconds: int = 0) -> int:
        """
        Record FloodWait occurrence.

        Args:
            wait_seconds: FloodWait duration

        Returns:
            Updated health score
        """
        now = datetime.now()
        self.flood_wait_count += 1
        self.last_flood_wait = now

        # Penalty increases with wait duration
        base_penalty = self.FLOOD_WAIT_PENALTY
        if wait_seconds > 300:
            base_penalty *= 2
        elif wait_seconds > 60:
            base_penalty = int(base_penalty * 1.5)

        self.events.append(
            HealthEvent(
                event_type="flood_wait",
                timestamp=now,
                impact=base_penalty,
            )
        )

        self.current_score = max(0, self.current_score + base_penalty)

        logger.warning(
            f"FloodWait recorded: {wait_seconds}s, "
            f"score: {self.current_score}, "
            f"count: {self.flood_wait_count}"
        )

        return self.current_score

    def record_error(self, error_type: str = "unknown") -> int:
        """
        Record error occurrence.

        Args:
            error_type: Type of error

        Returns:
            Updated health score
        """
        now = datetime.now()
        self.error_count += 1
        self.last_error = now

        self.events.append(
            HealthEvent(
                event_type=f"error:{error_type}",
                timestamp=now,
                impact=self.ERROR_PENALTY,
            )
        )

        self.current_score = max(0, self.current_score + self.ERROR_PENALTY)

        logger.warning(
            f"Error recorded: {error_type}, "
            f"score: {self.current_score}, "
            f"count: {self.error_count}"
        )

        return self.current_score

    def record_success(self) -> int:
        """
        Record successful send.

        Returns:
            Updated health score
        """
        self.success_count += 1

        # Only recover if below max
        if self.current_score < HEALTH_SCORE_MAX:
            self.current_score = min(
                HEALTH_SCORE_MAX,
                self.current_score + self.SUCCESS_RECOVERY,
            )

        return self.current_score

    def apply_time_recovery(self) -> int:
        """
        Apply time-based health recovery.

        Call this periodically (e.g., hourly).

        Returns:
            Updated health score
        """
        if self.current_score >= HEALTH_SCORE_MAX:
            return self.current_score

        # Check time since last issue
        now = datetime.now()
        last_issue = max(
            self.last_flood_wait or datetime.min,
            self.last_error or datetime.min,
        )

        if last_issue == datetime.min:
            # No issues recorded - full recovery
            self.current_score = HEALTH_SCORE_MAX
            return self.current_score

        hours_since_issue = (now - last_issue).total_seconds() / 3600

        if hours_since_issue >= 1:
            recovery = int(hours_since_issue * self.TIME_RECOVERY_PER_HOUR)
            self.current_score = min(
                HEALTH_SCORE_MAX,
                self.current_score + recovery,
            )

        return self.current_score

    def is_healthy(self) -> bool:
        """Check if account is healthy enough to send."""
        return self.current_score >= HEALTH_SCORE_WARNING

    def is_critical(self) -> bool:
        """Check if account health is critical."""
        return self.current_score <= HEALTH_SCORE_CRITICAL

    def should_pause(self) -> bool:
        """
        Check if sending should be paused.

        Returns:
            True if account should pause sending
        """
        # Pause if health is critical
        if self.is_critical():
            return True

        # Pause if too many consecutive flood waits
        if self.flood_wait_count >= self.FLOOD_WAIT_CRITICAL_COUNT:
            return True

        # Pause if too many consecutive errors
        if self.error_count >= self.ERROR_CRITICAL_COUNT:
            return True

        return False

    def get_recommended_pause_duration(self) -> int:
        """
        Get recommended pause duration in seconds.

        Returns:
            Recommended pause duration
        """
        if self.current_score <= 10:
            return 3600  # 1 hour
        elif self.current_score <= 30:
            return 1800  # 30 minutes
        elif self.current_score <= 50:
            return 900  # 15 minutes
        else:
            return 300  # 5 minutes

    def reset_counters(self) -> None:
        """Reset event counters (call after successful recovery period)."""
        self.flood_wait_count = 0
        self.error_count = 0
        self.success_count = 0

    def reset_full(self) -> None:
        """Full reset to initial state."""
        self.current_score = HEALTH_SCORE_MAX
        self.events.clear()
        self.reset_counters()
        self.last_flood_wait = None
        self.last_error = None

    def get_status(self) -> dict:
        """Get current health status."""
        return {
            "score": self.current_score,
            "is_healthy": self.is_healthy(),
            "is_critical": self.is_critical(),
            "should_pause": self.should_pause(),
            "flood_wait_count": self.flood_wait_count,
            "error_count": self.error_count,
            "success_count": self.success_count,
            "last_flood_wait": (
                self.last_flood_wait.isoformat() if self.last_flood_wait else None
            ),
            "last_error": (
                self.last_error.isoformat() if self.last_error else None
            ),
            "recent_events": len(self.events),
        }

    def get_health_level(self) -> str:
        """
        Get human-readable health level.

        Returns:
            Health level string
        """
        if self.current_score >= 80:
            return "excellent"
        elif self.current_score >= HEALTH_SCORE_WARNING:
            return "good"
        elif self.current_score >= 50:
            return "moderate"
        elif self.current_score >= HEALTH_SCORE_CRITICAL:
            return "poor"
        else:
            return "critical"

    def cleanup_old_events(self, max_age_hours: int = 24) -> None:
        """
        Remove old events from history.

        Args:
            max_age_hours: Maximum age of events to keep
        """
        cutoff = datetime.now() - timedelta(hours=max_age_hours)
        self.events = [e for e in self.events if e.timestamp > cutoff]
