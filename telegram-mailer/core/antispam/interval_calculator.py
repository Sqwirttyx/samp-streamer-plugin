"""Interval calculation for antispam."""

import random
from typing import Optional

from common.constants import HEALTH_SCORE_CRITICAL, HEALTH_SCORE_WARNING
from common.logger import get_logger

logger = get_logger(__name__)


class IntervalCalculator:
    """
    Calculator for message sending intervals.

    Provides smart interval calculation based on:
    - Number of chats
    - Account health
    - FloodWait history
    - Randomization
    """

    # Base intervals
    MIN_INTERVAL = 10  # seconds
    MAX_INTERVAL = 120  # seconds
    DEFAULT_MIN = 25
    DEFAULT_MAX = 45

    # Randomization factors
    JITTER_MIN = 0.7
    JITTER_MAX = 1.3

    # Adaptation factors
    FLOOD_WAIT_MULTIPLIER = 1.5
    LOW_HEALTH_MULTIPLIER = 1.3

    def __init__(
        self,
        base_min: int = DEFAULT_MIN,
        base_max: int = DEFAULT_MAX,
    ):
        """
        Initialize calculator.

        Args:
            base_min: Base minimum interval
            base_max: Base maximum interval
        """
        self.base_min = max(self.MIN_INTERVAL, base_min)
        self.base_max = min(self.MAX_INTERVAL, base_max)
        self.current_min = self.base_min
        self.current_max = self.base_max

    @classmethod
    def calculate_base_interval(
        cls,
        chat_count: int,
        cycle_duration_hours: float = 16,
    ) -> tuple[int, int]:
        """
        Calculate base interval for given chat count and cycle duration.

        Args:
            chat_count: Number of chats to send to
            cycle_duration_hours: Duration of one cycle in hours

        Returns:
            Tuple of (min_interval, max_interval)
        """
        if chat_count == 0:
            return cls.DEFAULT_MIN, cls.DEFAULT_MAX

        # Calculate average interval needed
        total_seconds = cycle_duration_hours * 3600
        avg_interval = total_seconds / chat_count

        # Set min/max around average
        min_interval = int(avg_interval * 0.6)
        max_interval = int(avg_interval * 1.4)

        # Clamp to allowed range
        min_interval = max(cls.MIN_INTERVAL, min(cls.MAX_INTERVAL - 10, min_interval))
        max_interval = max(min_interval + 10, min(cls.MAX_INTERVAL, max_interval))

        return min_interval, max_interval

    def get_interval(self) -> int:
        """
        Get next interval with randomization.

        Returns:
            Interval in seconds
        """
        base = random.randint(self.current_min, self.current_max)
        jitter = random.uniform(self.JITTER_MIN, self.JITTER_MAX)
        return int(base * jitter)

    def adapt_to_flood_wait(self, flood_wait_count: int) -> None:
        """
        Adapt intervals based on flood wait occurrences.

        Args:
            flood_wait_count: Number of consecutive flood waits
        """
        if flood_wait_count <= 0:
            return

        # Increase intervals based on flood wait count
        multiplier = self.FLOOD_WAIT_MULTIPLIER ** min(flood_wait_count, 3)

        self.current_min = min(
            self.MAX_INTERVAL - 10,
            int(self.base_min * multiplier),
        )
        self.current_max = min(
            self.MAX_INTERVAL,
            int(self.base_max * multiplier),
        )

        logger.info(
            f"Intervals adapted for flood waits: {self.current_min}-{self.current_max}"
        )

    def adapt_to_health(self, health_score: int) -> None:
        """
        Adapt intervals based on account health.

        Args:
            health_score: Account health score (0-100)
        """
        if health_score >= HEALTH_SCORE_WARNING:
            # Good health - use base intervals
            self.current_min = self.base_min
            self.current_max = self.base_max
            return

        if health_score <= HEALTH_SCORE_CRITICAL:
            # Critical health - max intervals
            self.current_min = int(self.base_min * 2)
            self.current_max = self.MAX_INTERVAL
        else:
            # Low health - increased intervals
            self.current_min = int(self.base_min * self.LOW_HEALTH_MULTIPLIER)
            self.current_max = int(self.base_max * self.LOW_HEALTH_MULTIPLIER)

        logger.info(
            f"Intervals adapted for health {health_score}: "
            f"{self.current_min}-{self.current_max}"
        )

    def get_safe_interval(
        self,
        health_score: int,
        flood_wait_count: int = 0,
    ) -> int:
        """
        Get safe interval considering health and flood waits.

        Args:
            health_score: Account health score
            flood_wait_count: Number of recent flood waits

        Returns:
            Safe interval in seconds
        """
        # Reset to base
        self.current_min = self.base_min
        self.current_max = self.base_max

        # Apply health adaptation
        self.adapt_to_health(health_score)

        # Apply flood wait adaptation
        self.adapt_to_flood_wait(flood_wait_count)

        return self.get_interval()

    def reset(self) -> None:
        """Reset to base intervals."""
        self.current_min = self.base_min
        self.current_max = self.base_max

    def get_status(self) -> dict:
        """Get current calculator status."""
        return {
            "base_min": self.base_min,
            "base_max": self.base_max,
            "current_min": self.current_min,
            "current_max": self.current_max,
        }
