"""Campaign and CampaignProgress models."""

from datetime import datetime
from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from common.constants import CampaignStatus
from database.models.base import BaseModel

if TYPE_CHECKING:
    from database.models.account import Account
    from database.models.folder import Folder
    from database.models.stats import StatsHourly
    from database.models.user import User


class Campaign(BaseModel):
    """
    Campaign model.

    Represents a message sending campaign.

    Attributes:
        user_id: Owner's ID
        account_id: Account used for sending
        folder_id: Folder with target chats
        name: Campaign name
        message_text: Message text content
        message_media: Media attachments (JSONB)
        interval_min: Minimum interval between messages (seconds)
        interval_max: Maximum interval between messages (seconds)
        work_hours: Hours of work before rest
        rest_minutes: Rest duration in minutes
        is_admin_campaign: Admin campaign flag
        admin_footer: Admin footer text
        status: Campaign status
        started_at: Campaign start time
        completed_at: Campaign completion time
    """

    __tablename__ = "campaigns"

    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    account_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    folder_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("folders.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    message_text: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    message_media: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )
    interval_min: Mapped[int] = mapped_column(
        Integer,
        default=25,
        nullable=False,
    )
    interval_max: Mapped[int] = mapped_column(
        Integer,
        default=45,
        nullable=False,
    )
    work_hours: Mapped[int] = mapped_column(
        Integer,
        default=4,
        nullable=False,
    )
    rest_minutes: Mapped[int] = mapped_column(
        Integer,
        default=30,
        nullable=False,
    )
    is_admin_campaign: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    admin_footer: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    status: Mapped[CampaignStatus] = mapped_column(
        Enum(CampaignStatus, name="campaign_status"),
        default=CampaignStatus.DRAFT,
        nullable=False,
        index=True,
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        back_populates="campaigns",
    )
    account: Mapped["Account"] = relationship(
        "Account",
        back_populates="campaigns",
    )
    folder: Mapped["Folder"] = relationship(
        "Folder",
        back_populates="campaigns",
    )
    progress: Mapped[Optional["CampaignProgress"]] = relationship(
        "CampaignProgress",
        back_populates="campaign",
        uselist=False,
        cascade="all, delete-orphan",
    )
    stats: Mapped[list["StatsHourly"]] = relationship(
        "StatsHourly",
        back_populates="campaign",
    )

    @property
    def is_active(self) -> bool:
        """Check if campaign is currently active."""
        return self.status == CampaignStatus.ACTIVE

    @property
    def can_start(self) -> bool:
        """Check if campaign can be started."""
        return self.status in (CampaignStatus.DRAFT, CampaignStatus.PAUSED)

    @property
    def can_pause(self) -> bool:
        """Check if campaign can be paused."""
        return self.status == CampaignStatus.ACTIVE

    def __repr__(self) -> str:
        return f"<Campaign(id={self.id}, name={self.name}, status={self.status})>"


class CampaignProgress(BaseModel):
    """
    Campaign progress tracking.

    Tracks the current state of a running campaign.

    Attributes:
        campaign_id: Parent campaign ID
        current_chat_index: Current chat index in the list
        cycle_count: Number of completed cycles
        last_sent_at: Last message sent timestamp
        next_send_at: Next scheduled send time
    """

    __tablename__ = "campaign_progress"

    campaign_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("campaigns.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    current_chat_index: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    cycle_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    last_sent_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    next_send_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    campaign: Mapped["Campaign"] = relationship(
        "Campaign",
        back_populates="progress",
    )

    def __repr__(self) -> str:
        return f"<CampaignProgress(campaign_id={self.campaign_id}, index={self.current_chat_index}, cycle={self.cycle_count})>"
