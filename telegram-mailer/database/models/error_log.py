"""Error log model."""

from datetime import datetime
from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.models.base import BaseModel

if TYPE_CHECKING:
    from database.models.account import Account


class ErrorLog(BaseModel):
    """
    Error log model.

    Tracks errors that occur during message sending.

    Attributes:
        account_id: Account that encountered the error
        chat_id: Telegram chat ID where error occurred
        error_type: Type of error (flood_wait, spam_block, etc.)
        error_message: Detailed error message
    """

    __tablename__ = "error_logs"

    account_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chat_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        nullable=True,
    )
    error_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Relationships
    account: Mapped["Account"] = relationship(
        "Account",
        back_populates="error_logs",
    )

    def __repr__(self) -> str:
        return f"<ErrorLog(account={self.account_id}, type={self.error_type})>"
