"""AdminMessage model for 8-hour admin window campaigns."""

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from database.models.base import BaseModel

if TYPE_CHECKING:
    pass


class AdminMessage(BaseModel):
    """
    Admin message template for 8-hour window campaigns.

    These messages are sent using user accounts during the admin window (8 hours).
    The 16/8 model: 16 hours user campaigns, 8 hours admin campaigns.

    Attributes:
        name: Template name for identification
        message_text: Message text content
        message_media: Media attachments (JSONB)
        is_active: Whether template is active
        priority: Priority for rotation (higher = more frequent)
        usage_count: Times this template was used
        last_used_at: Last usage timestamp
        target_folders: Optional list of folder types to target
    """

    __tablename__ = "admin_messages"

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
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
    )
    priority: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )
    usage_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    last_used_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    # Optional targeting by folder categories
    target_folders: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )
    # Optional footer to append
    footer_text: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    def __repr__(self) -> str:
        return f"<AdminMessage(id={self.id}, name={self.name}, active={self.is_active})>"
