"""Account model."""

from datetime import datetime
from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import BigInteger, Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from common.constants import AccountStatus, TrustLevel, WarmingPhase
from database.models.base import BaseModel

if TYPE_CHECKING:
    from database.models.campaign import Campaign
    from database.models.error_log import ErrorLog
    from database.models.folder import Folder
    from database.models.proxy import Proxy
    from database.models.stats import StatsHourly
    from database.models.user import User


class Account(BaseModel):
    """
    Telegram account model.

    Represents a Telegram account used for sending messages.
    Extended with trust scoring, warming phases, and device fingerprinting.
    """

    __tablename__ = "accounts"

    # ==========================================================================
    # CORE FIELDS
    # ==========================================================================

    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Telegram account data
    telegram_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        nullable=True,
        unique=True,
        index=True,
    )
    phone: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    phone_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    username: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    first_name: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True,
    )

    # Session storage
    session_path: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
    )
    session_string: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Encrypted session string (alternative to file)",
    )

    # Proxy binding
    proxy_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("proxies.id", ondelete="SET NULL"),
        nullable=True,
    )

    # ==========================================================================
    # STATUS & TRUST
    # ==========================================================================

    status: Mapped[AccountStatus] = mapped_column(
        Enum(AccountStatus, name="account_status", values_callable=lambda x: [e.value for e in x]),
        default=AccountStatus.WARMING_UP,
        nullable=False,
        index=True,
    )

    # Trust score system (0-100)
    trust_score: Mapped[int] = mapped_column(
        Integer,
        default=10,  # New accounts start with low score
        nullable=False,
    )
    trust_level: Mapped[TrustLevel] = mapped_column(
        Enum(TrustLevel, name="trust_level", values_callable=lambda x: [e.value for e in x]),
        default=TrustLevel.QUARANTINE,
        nullable=False,
        index=True,
    )

    # Premium status
    is_premium: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    # ==========================================================================
    # WARMING SYSTEM
    # ==========================================================================

    warming_phase: Mapped[WarmingPhase] = mapped_column(
        Enum(WarmingPhase, name="warming_phase", values_callable=lambda x: [e.value for e in x]),
        default=WarmingPhase.PHASE_1,
        nullable=False,
    )
    warming_started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_warming_activity: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Account age (days since first seen)
    age_days: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    # ==========================================================================
    # STATISTICS
    # ==========================================================================

    # Health monitoring
    health_score: Mapped[int] = mapped_column(
        Integer,
        default=100,
        nullable=False,
    )
    last_health_check: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Message statistics
    messages_sent_total: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    messages_sent_today: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    successful_messages: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    last_message_time: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Organic activity counter
    organic_activity_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    # Error statistics
    total_errors: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    # Contacts and groups
    contacts_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    groups_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    # ==========================================================================
    # BAN & FLOODWAIT TRACKING
    # ==========================================================================

    total_bans: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    last_ban_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    days_since_last_ban: Mapped[int] = mapped_column(
        Integer,
        default=999,
        nullable=False,
    )

    # FloodWait tracking
    flood_wait_until: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    flood_wait_count_today: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    last_flood_wait: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Quarantine
    is_quarantined: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    quarantine_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    quarantine_start: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # ==========================================================================
    # DEVICE FINGERPRINT
    # ==========================================================================

    device_fingerprint: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Immutable device fingerprint for this account",
    )

    # ==========================================================================
    # LEGACY FIELDS (for compatibility)
    # ==========================================================================

    total_sent: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    # ==========================================================================
    # RELATIONSHIPS
    # ==========================================================================

    user: Mapped["User"] = relationship(
        "User",
        back_populates="accounts",
    )
    proxy: Mapped[Optional["Proxy"]] = relationship(
        "Proxy",
        back_populates="accounts",
    )
    folders: Mapped[list["Folder"]] = relationship(
        "Folder",
        back_populates="account",
    )
    campaigns: Mapped[list["Campaign"]] = relationship(
        "Campaign",
        back_populates="account",
    )
    stats: Mapped[list["StatsHourly"]] = relationship(
        "StatsHourly",
        back_populates="account",
    )
    error_logs: Mapped[list["ErrorLog"]] = relationship(
        "ErrorLog",
        back_populates="account",
    )

    # ==========================================================================
    # PROPERTIES
    # ==========================================================================

    @property
    def is_available(self) -> bool:
        """Check if account is available for sending."""
        if self.status not in (AccountStatus.ACTIVE, AccountStatus.WARMING_UP):
            return False
        if self.is_quarantined:
            return False
        if self.flood_wait_until and self.flood_wait_until > datetime.utcnow():
            return False
        return True

    @property
    def is_ready_for_campaigns(self) -> bool:
        """Check if account is ready for full campaigns."""
        return (
            self.status == AccountStatus.ACTIVE
            and self.trust_level not in (TrustLevel.QUARANTINE, TrustLevel.WARMING)
            and not self.is_quarantined
            and self.warming_phase == WarmingPhase.PHASE_4
        )

    @property
    def can_use_aggressive_mode(self) -> bool:
        """Check if account can use aggressive sending mode."""
        return (
            self.age_days >= 180  # At least 6 months old
            and self.trust_score >= 60
            and self.total_bans == 0
            and not self.is_quarantined
        )

    def __repr__(self) -> str:
        return (
            f"<Account(id={self.id}, phone={self.phone[:4]}***, "
            f"status={self.status}, trust={self.trust_score})>"
        )
