"""User model."""

from typing import TYPE_CHECKING, Optional

from sqlalchemy import BigInteger, Boolean, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.models.base import BaseModel

if TYPE_CHECKING:
    from database.models.account import Account
    from database.models.campaign import Campaign
    from database.models.folder import Folder
    from database.models.invite import InviteKey
    from database.models.proxy import Proxy


class User(BaseModel):
    """
    User model representing a registered Telegram user.

    Attributes:
        telegram_id: Unique Telegram user ID
        username: Telegram username (optional)
        invite_key: The key used for registration
        is_admin: Admin flag
        is_active: Whether user is active
        settings: User-specific settings (JSONB)
    """

    __tablename__ = "users"

    telegram_id: Mapped[int] = mapped_column(
        BigInteger,
        unique=True,
        nullable=False,
        index=True,
    )
    username: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    invite_key: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
    )
    is_admin: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    settings: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        default=dict,
    )

    # Relationships
    accounts: Mapped[list["Account"]] = relationship(
        "Account",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    proxies: Mapped[list["Proxy"]] = relationship(
        "Proxy",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    folders: Mapped[list["Folder"]] = relationship(
        "Folder",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    campaigns: Mapped[list["Campaign"]] = relationship(
        "Campaign",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    created_invite_keys: Mapped[list["InviteKey"]] = relationship(
        "InviteKey",
        foreign_keys="InviteKey.created_by",
        back_populates="creator",
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, telegram_id={self.telegram_id}, username={self.username})>"
