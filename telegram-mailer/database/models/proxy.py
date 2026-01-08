"""Proxy model."""

from datetime import datetime
from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from common.constants import ProxyStatus, ProxyType
from database.models.base import BaseModel

if TYPE_CHECKING:
    from database.models.account import Account
    from database.models.user import User


class Proxy(BaseModel):
    """
    Proxy model.

    Represents a proxy server for Telegram connections.

    Attributes:
        user_id: Owner's ID
        type: Proxy type (socks5, http, mtproxy)
        host: Proxy host
        port: Proxy port
        username: Proxy username (optional)
        password: Proxy password (optional)
        status: Proxy status (active, checking, dead)
        last_check: Last check timestamp
    """

    __tablename__ = "proxies"

    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    type: Mapped[ProxyType] = mapped_column(
        Enum(ProxyType, name="proxy_type"),
        nullable=False,
    )
    host: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    port: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    username: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    password: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    status: Mapped[ProxyStatus] = mapped_column(
        Enum(ProxyStatus, name="proxy_status"),
        default=ProxyStatus.ACTIVE,
        nullable=False,
    )
    last_check: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        back_populates="proxies",
    )
    accounts: Mapped[list["Account"]] = relationship(
        "Account",
        back_populates="proxy",
    )

    @property
    def connection_string(self) -> str:
        """Get proxy connection string."""
        auth = ""
        if self.username:
            auth = f"{self.username}"
            if self.password:
                auth += f":{self.password}"
            auth += "@"
        return f"{self.type.value}://{auth}{self.host}:{self.port}"

    @property
    def is_available(self) -> bool:
        """Check if proxy is available for use."""
        return self.status == ProxyStatus.ACTIVE

    def __repr__(self) -> str:
        return f"<Proxy(id={self.id}, type={self.type}, host={self.host}:{self.port}, status={self.status})>"
