"""Account model."""

from datetime import datetime
from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from common.constants import AccountStatus
from database.models.base import BaseModel

if TYPE_CHECKING:
    from database.models.campaign import Campaign
    from database.models.folder import Folder
    from database.models.proxy import Proxy
    from database.models.stats import StatsHourly
    from database.models.user import User


class Account(BaseModel):
    """
    Telegram account model.

    Represents a Telegram account used for sending messages.

    Attributes:
        user_id: Owner's ID
        phone_hash: Hashed phone number
        session_path: Path to encrypted session file
        proxy_id: Bound proxy ID (optional)
        status: Account status (active, paused, banned, error)
        health_score: Health score 0-100
        last_health_check: Last health check timestamp
        flood_wait_until: FloodWait expiry time
        total_sent: Total messages sent
        total_errors: Total errors count
    """

    __tablename__ = "accounts"

    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    phone_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    session_path: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
    )
    proxy_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("proxies.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[AccountStatus] = mapped_column(
        Enum(AccountStatus, name="account_status"),
        default=AccountStatus.ACTIVE,
        nullable=False,
        index=True,
    )
    health_score: Mapped[int] = mapped_column(
        Integer,
        default=100,
        nullable=False,
    )
    last_health_check: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    flood_wait_until: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    total_sent: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    total_errors: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    # Relationships
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

    @property
    def is_available(self) -> bool:
        """Check if account is available for sending."""
        if self.status != AccountStatus.ACTIVE:
            return False
        if self.flood_wait_until and self.flood_wait_until > datetime.utcnow():
            return False
        return True

    def __repr__(self) -> str:
        return f"<Account(id={self.id}, status={self.status}, health={self.health_score})>"
