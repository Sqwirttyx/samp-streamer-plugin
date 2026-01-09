"""Account limits management."""

from datetime import datetime, timedelta
from typing import Optional, Tuple
from uuid import UUID

from common.constants import (
    TrustLevel,
    TRUST_LIMITS,
    SENDING_MODE_CONFIG,
    SendingMode,
)
from common.logger import get_logger
from core.trust.scoring import TrustScoreCalculator

logger = get_logger(__name__)


class AccountLimitsManager:
    """
    Account sending limits management.

    Critical limits from research:
    - ~50 unsolicited messages per day (unofficial limit)
    - 20 messages per minute to one group (official)
    - FloodWait on exceed - escalating delays
    """

    # Hard limits (absolute maximums)
    HARD_LIMITS = {
        "messages_per_day_safe": 50,
        "messages_per_day_aggressive": 9000,
        "messages_per_hour_safe": 15,
        "messages_per_hour_aggressive": 600,
        "messages_per_minute_per_chat": 1,  # Telegram technical limit
        "groups_per_day": 500,
        "flood_wait_threshold": 5,  # After 5 FloodWaits - pause
    }

    def __init__(self, redis_client=None):
        """
        Initialize limits manager.

        Args:
            redis_client: Redis client for tracking counters
        """
        self.redis = redis_client
        self.scoring = TrustScoreCalculator()

    async def can_send_message(
        self,
        account_data: dict,
        mode: SendingMode = SendingMode.SAFE,
    ) -> Tuple[bool, str]:
        """
        Check if account can send a message.

        Args:
            account_data: Account data dictionary
            mode: Sending mode

        Returns:
            Tuple of (can_send, reason)
        """
        account_id = account_data.get("id")

        # 1. Check quarantine
        if account_data.get("is_quarantined"):
            return False, "Account is quarantined"

        # 2. Check status
        status = account_data.get("status")
        if status in ("banned", "error"):
            return False, f"Account status is {status}"

        # 3. Check FloodWait
        flood_wait_until = account_data.get("flood_wait_until")
        if flood_wait_until and flood_wait_until > datetime.utcnow():
            remaining = (flood_wait_until - datetime.utcnow()).seconds
            return False, f"FloodWait active, {remaining}s remaining"

        # 4. Check trust level (for safe mode)
        if mode == SendingMode.SAFE:
            trust_level = account_data.get("trust_level", TrustLevel.LOW)
            limits = TRUST_LIMITS.get(trust_level, TRUST_LIMITS[TrustLevel.LOW])
            if not limits.get("can_send", False):
                return False, f"Trust level '{trust_level}' doesn't allow sending"

        # 5. Check daily limit
        messages_today = account_data.get("messages_sent_today", 0)
        mode_config = SENDING_MODE_CONFIG[mode]
        max_daily = mode_config["messages_per_day"]

        if messages_today >= max_daily:
            return False, f"Daily limit reached ({max_daily} messages)"

        # 6. Check FloodWait counter
        flood_waits_today = account_data.get("flood_wait_count_today", 0)
        if flood_waits_today >= self.HARD_LIMITS["flood_wait_threshold"]:
            return False, "Too many FloodWaits today - account is resting"

        # 7. Check time since last message (for safe mode)
        if mode == SendingMode.SAFE:
            last_message = account_data.get("last_message_time")
            if last_message:
                elapsed = (datetime.utcnow() - last_message).total_seconds()
                min_delay = limits.get("min_delay_seconds", 60)
                if elapsed < min_delay:
                    return False, f"Wait {int(min_delay - elapsed)}s more"

        return True, "OK"

    def get_mode_limits(self, mode: SendingMode) -> dict:
        """
        Get limits for sending mode.

        Args:
            mode: Sending mode

        Returns:
            Dictionary with limits
        """
        return SENDING_MODE_CONFIG.get(mode, SENDING_MODE_CONFIG[SendingMode.SAFE])

    def get_recommended_delay(
        self,
        account_data: dict,
        mode: SendingMode = SendingMode.SAFE,
    ) -> int:
        """
        Get recommended delay between messages.

        Args:
            account_data: Account data
            mode: Sending mode

        Returns:
            Delay in seconds
        """
        mode_config = SENDING_MODE_CONFIG[mode]
        base_delay = (mode_config["min_delay"] + mode_config["max_delay"]) // 2

        # Adjust for FloodWait history
        flood_waits = account_data.get("flood_wait_count_today", 0)
        if flood_waits > 0:
            base_delay = int(base_delay * (1 + flood_waits * 0.2))

        # Adjust for trust score (safe mode only)
        if mode == SendingMode.SAFE:
            trust_score = account_data.get("trust_score", 50)
            if trust_score < 40:
                base_delay = int(base_delay * 1.5)
            elif trust_score < 60:
                base_delay = int(base_delay * 1.2)

        return min(base_delay, mode_config["max_delay"] * 2)

    def calculate_eta(
        self,
        total_chats: int,
        mode: SendingMode,
        account_data: Optional[dict] = None,
    ) -> dict:
        """
        Calculate estimated time for campaign.

        Args:
            total_chats: Number of chats to send to
            mode: Sending mode
            account_data: Optional account data for adjustments

        Returns:
            Dictionary with ETA info
        """
        mode_config = SENDING_MODE_CONFIG[mode]
        avg_delay = (mode_config["min_delay"] + mode_config["max_delay"]) / 2

        # Account for bursts
        burst_size = mode_config["burst_size"]
        burst_pause = mode_config["burst_pause"]

        # Messages per burst cycle
        burst_cycle_time = (burst_size * avg_delay) + burst_pause
        messages_per_cycle = burst_size

        # Total cycles needed
        cycles = total_chats / messages_per_cycle

        # Total time
        total_seconds = cycles * burst_cycle_time

        # Add buffer for FloodWaits (estimate 5% overhead)
        total_seconds *= 1.05

        return {
            "total_messages": total_chats,
            "estimated_seconds": int(total_seconds),
            "estimated_minutes": int(total_seconds / 60),
            "estimated_hours": round(total_seconds / 3600, 1),
            "avg_speed_per_minute": round(60 / avg_delay, 1),
            "mode": mode.value,
        }
