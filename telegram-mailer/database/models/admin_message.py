"""AdminMessage model for 8-hour admin window campaigns."""

from datetime import datetime
from typing import TYPE_CHECKING, Optional, List

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from database.models.base import BaseModel

if TYPE_CHECKING:
    pass


class AdminMessage(BaseModel):
    """
    Admin message template for 8-hour window campaigns.

    These messages are sent using user accounts during the admin window (8 hours).
    The 16/8 model: 16 hours user campaigns, 8 hours admin campaigns.

    Supports:
    - Spintax syntax for message variation: {option1|option2|option3}
    - Category targeting for relevant audience

    Attributes:
        name: Template name for identification
        message_text: Message text content (supports spintax)
        message_media: Media attachments (JSONB)
        is_active: Whether template is active
        priority: Priority for rotation (higher = more frequent)
        usage_count: Times this template was used
        last_used_at: Last usage timestamp
        target_categories: Category slugs to target (empty = all)
        footer_text: Optional footer to append
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
    # Target category slugs (empty array = target all)
    target_categories: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
    )
    # Optional footer to append
    footer_text: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    @property
    def has_spintax(self) -> bool:
        """Check if message contains spintax syntax."""
        if not self.message_text:
            return False
        return '{' in self.message_text and '|' in self.message_text

    @property
    def targets_all(self) -> bool:
        """Check if message targets all categories."""
        return not self.target_categories or len(self.target_categories) == 0

    def matches_category(self, category_slug: str) -> bool:
        """Check if message targets a specific category."""
        if self.targets_all:
            return True
        return category_slug in (self.target_categories or [])

    def __repr__(self) -> str:
        return f"<AdminMessage(id={self.id}, name={self.name}, active={self.is_active})>"
