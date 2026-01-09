"""Trust score calculation system."""

from typing import Optional

from common.constants import (
    TrustLevel,
    TRUST_SCORE_QUARANTINE,
    TRUST_SCORE_WARMING,
    TRUST_SCORE_LOW,
    TRUST_SCORE_MEDIUM,
    TRUST_LIMITS,
)
from common.logger import get_logger

logger = get_logger(__name__)


class TrustScoreCalculator:
    """
    Trust score calculation for accounts.

    Based on research: new accounts are banned from 1 complaint,
    old accounts can withstand several. Age is critical.
    """

    # Weight configuration for score calculation
    WEIGHTS = {
        "age_days": 0.25,           # Account age (critical!)
        "successful_messages": 0.15, # Successful sends
        "no_bans_period": 0.20,     # Period without bans
        "organic_activity": 0.15,   # Organic activity (reads, reactions)
        "contacts_count": 0.10,     # Number of contacts
        "groups_count": 0.10,       # Group participation
        "is_premium": 0.05,         # Premium status (small bonus)
    }

    @classmethod
    def calculate_score(cls, account_data: dict) -> int:
        """
        Calculate trust score for account.

        Args:
            account_data: Dictionary with account fields

        Returns:
            Trust score (0-100)
        """
        score = 0

        # 1. Account age (max 25 points)
        # Critical: account < 30 days = very high risk
        age_days = account_data.get("age_days", 0)
        if age_days < 7:
            age_score = 0
        elif age_days < 14:
            age_score = 5
        elif age_days < 30:
            age_score = 10
        elif age_days < 60:
            age_score = 15
        elif age_days < 90:
            age_score = 20
        elif age_days < 180:
            age_score = 22
        elif age_days < 365:
            age_score = 24
        else:
            age_score = 25
        score += age_score

        # 2. Successful messages without complaints (max 15 points)
        successful = account_data.get("successful_messages", 0)
        if successful > 5000:
            score += 15
        elif successful > 2000:
            score += 13
        elif successful > 1000:
            score += 11
        elif successful > 500:
            score += 9
        elif successful > 200:
            score += 7
        elif successful > 100:
            score += 5
        elif successful > 50:
            score += 3
        else:
            score += min(successful // 20, 3)

        # 3. Period without bans (max 20 points)
        days_since_ban = account_data.get("days_since_last_ban", 999)
        total_bans = account_data.get("total_bans", 0)

        if total_bans == 0:
            score += 20
        elif days_since_ban > 180:
            score += 16
        elif days_since_ban > 90:
            score += 12
        elif days_since_ban > 30:
            score += 8
        elif days_since_ban > 7:
            score += 4
        else:
            score += 0  # Recent ban - maximum penalty

        # 4. Organic activity (max 15 points)
        organic_actions = account_data.get("organic_activity_count", 0)
        score += min(organic_actions // 50, 15)

        # 5. Contacts (max 10 points)
        contacts = account_data.get("contacts_count", 0)
        score += min(contacts // 5, 10)

        # 6. Group participation (max 10 points)
        groups = account_data.get("groups_count", 0)
        score += min(groups // 3, 10)

        # 7. Premium bonus (5 points)
        if account_data.get("is_premium", False):
            score += 5

        # Penalties
        flood_wait_count = account_data.get("flood_wait_count_today", 0)
        if flood_wait_count > 5:
            score -= 15
        elif flood_wait_count > 3:
            score -= 10
        elif flood_wait_count > 1:
            score -= 5

        # Ban penalties
        if total_bans > 0:
            score -= min(total_bans * 5, 20)

        # Quarantine penalty
        if account_data.get("is_quarantined", False):
            score -= 20

        return max(0, min(100, score))

    @classmethod
    def get_trust_level(cls, score: int) -> TrustLevel:
        """
        Get trust level for given score.

        Args:
            score: Trust score (0-100)

        Returns:
            TrustLevel enum value
        """
        if score < TRUST_SCORE_QUARANTINE:
            return TrustLevel.QUARANTINE
        elif score < TRUST_SCORE_WARMING:
            return TrustLevel.WARMING
        elif score < TRUST_SCORE_LOW:
            return TrustLevel.LOW
        elif score < TRUST_SCORE_MEDIUM:
            return TrustLevel.MEDIUM
        else:
            return TrustLevel.HIGH

    @classmethod
    def get_limits_for_level(cls, trust_level: TrustLevel) -> dict:
        """
        Get sending limits for trust level.

        Args:
            trust_level: Trust level

        Returns:
            Dictionary with limits
        """
        return TRUST_LIMITS.get(trust_level, TRUST_LIMITS[TrustLevel.LOW])

    @classmethod
    def get_recommended_daily_limit(
        cls,
        account_data: dict,
        is_aggressive: bool = False,
    ) -> int:
        """
        Get recommended daily message limit.

        Args:
            account_data: Account data dictionary
            is_aggressive: Whether aggressive mode is requested

        Returns:
            Recommended daily limit
        """
        age_days = account_data.get("age_days", 0)
        is_premium = account_data.get("is_premium", False)
        total_bans = account_data.get("total_bans", 0)

        # If banned before, be very conservative
        if total_bans > 0:
            return 30 if is_premium else 20

        if not is_aggressive:
            # Safe mode limits based on trust level
            score = cls.calculate_score(account_data)
            level = cls.get_trust_level(score)
            return cls.get_limits_for_level(level)["messages_per_day"]

        # Aggressive mode limits based on age + premium
        if is_premium and age_days >= 730:
            return 9000
        elif is_premium and age_days >= 365:
            return 7000
        elif is_premium and age_days >= 180:
            return 5000
        elif is_premium:
            return 3000
        elif age_days >= 730:
            return 6000
        elif age_days >= 365:
            return 4000
        elif age_days >= 180:
            return 2000
        elif age_days >= 90:
            return 1000
        else:
            return 500

    @classmethod
    def check_aggressive_eligibility(cls, account_data: dict) -> dict:
        """
        Check if account is eligible for aggressive mode.

        Args:
            account_data: Account data dictionary

        Returns:
            Dictionary with eligibility info
        """
        issues = []
        warnings = []

        age_days = account_data.get("age_days", 0)
        is_premium = account_data.get("is_premium", False)
        total_bans = account_data.get("total_bans", 0)
        trust_score = cls.calculate_score(account_data)

        # Critical checks
        if age_days < 90:
            issues.append(
                f"Account too young ({age_days} days). "
                f"Need at least 3 months, better 6+ months"
            )

        if total_bans > 0:
            issues.append(
                f"Account has {total_bans} ban(s). "
                f"Not recommended for aggressive mode"
            )

        if trust_score < 40:
            issues.append(
                f"Trust score too low ({trust_score}). "
                f"Need at least 40 for aggressive mode"
            )

        # Warnings
        if age_days < 180:
            warnings.append(
                f"Account is {age_days} days old. "
                f"For 5000+ msg/day recommend 6+ months"
            )

        if age_days < 365:
            warnings.append(
                f"Account is {age_days} days old. "
                f"For 7000+ msg/day recommend 1+ year"
            )

        if not is_premium:
            warnings.append(
                "Without Premium expect more FloodWait and higher ban risk"
            )

        # Calculate recommended limit
        recommended_daily = cls.get_recommended_daily_limit(
            account_data, is_aggressive=True
        )

        # Risk level
        if is_premium and age_days >= 730 and total_bans == 0:
            risk_level = "low"
        elif is_premium and age_days >= 365 and total_bans == 0:
            risk_level = "medium"
        elif age_days >= 365 and total_bans == 0:
            risk_level = "medium"
        elif age_days >= 180:
            risk_level = "high"
        else:
            risk_level = "very_high"

        return {
            "ready": len(issues) == 0,
            "issues": issues,
            "warnings": warnings,
            "recommended_daily": recommended_daily,
            "risk_level": risk_level,
            "trust_score": trust_score,
            "details": {
                "age_days": age_days,
                "is_premium": is_premium,
                "total_bans": total_bans,
            },
        }
