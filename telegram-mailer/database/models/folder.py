"""Folder model."""

from datetime import datetime
from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from common.constants import FolderStatus
from database.models.base import BaseModel

if TYPE_CHECKING:
    from database.models.account import Account
    from database.models.campaign import Campaign
    from database.models.user import User


class Folder(BaseModel):
    """
    Telegram folder model.

    Represents a Telegram chat folder with synced chats.

    Attributes:
        user_id: Owner's ID
        account_id: Bound account ID (optional)
        folder_link: Folder invite link
        folder_id: Telegram folder ID
        name: Folder name
        chat_count: Number of chats
        chat_ids: List of chat IDs (JSONB)
        last_sync: Last sync timestamp
        status: Folder status
    """

    __tablename__ = "folders"

    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    account_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="SET NULL"),
        nullable=True,
    )
    folder_link: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
    )
    folder_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    chat_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    chat_ids: Mapped[Optional[list]] = mapped_column(
        JSONB,
        nullable=True,
        default=list,
    )
    last_sync: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    status: Mapped[FolderStatus] = mapped_column(
        Enum(FolderStatus, name="folder_status", values_callable=lambda x: [e.value for e in x]),
        default=FolderStatus.ACTIVE,
        nullable=False,
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        back_populates="folders",
    )
    account: Mapped[Optional["Account"]] = relationship(
        "Account",
        back_populates="folders",
    )
    campaigns: Mapped[list["Campaign"]] = relationship(
        "Campaign",
        back_populates="folder",
    )

    @property
    def is_synced(self) -> bool:
        """Check if folder is synced."""
        return self.status == FolderStatus.ACTIVE and self.chat_ids is not None

    @property
    def is_bound(self) -> bool:
        """Check if folder is bound to an account."""
        return self.account_id is not None

    def __repr__(self) -> str:
        return f"<Folder(id={self.id}, name={self.name}, chats={self.chat_count})>"
