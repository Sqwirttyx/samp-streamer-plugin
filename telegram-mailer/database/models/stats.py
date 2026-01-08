"""Statistics models."""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.models.base import BaseModel

if TYPE_CHECKING:
    from database.models.account import Account
    from database.models.campaign import Campaign


class StatsHourly(BaseModel):
    """
    Hourly statistics model.

    Aggregated statistics per campaign/account per hour.

    Attributes:
        campaign_id: Campaign ID
        account_id: Account ID
        hour: Hour timestamp (truncated)
        sent_count: Messages sent
        error_count: Errors count
        flood_wait_count: FloodWait count
        spam_block: Whether spam block occurred
    """

    __tablename__ = "stats_hourly"

    campaign_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("campaigns.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    account_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    hour: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    sent_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    error_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    flood_wait_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    spam_block: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    # Relationships
    campaign: Mapped["Campaign"] = relationship(
        "Campaign",
        back_populates="stats",
    )
    account: Mapped["Account"] = relationship(
        "Account",
        back_populates="stats",
    )

    def __repr__(self) -> str:
        return f"<StatsHourly(campaign={self.campaign_id}, hour={self.hour}, sent={self.sent_count})>"
