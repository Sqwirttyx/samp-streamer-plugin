"""ChatCategory model for targeting system."""

from typing import TYPE_CHECKING, Optional, List

from sqlalchemy import Boolean, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.models.base import BaseModel

if TYPE_CHECKING:
    pass


class ChatCategory(BaseModel):
    """
    Chat category for targeting.

    Categories are used to classify folders/chats and match them
    with appropriate admin messages.

    Attributes:
        name: Category name (e.g., "Крипто", "Бизнес")
        slug: URL-safe identifier
        description: Category description
        keywords: Keywords for auto-detection
        icon: Emoji icon
        color: Hex color for UI
        is_active: Whether category is active
        priority: Display order priority
    """

    __tablename__ = "chat_categories"

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    slug: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        unique=True,
        index=True,
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    keywords: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
    )
    icon: Mapped[str] = mapped_column(
        String(10),
        default="📁",
        nullable=False,
    )
    color: Mapped[str] = mapped_column(
        String(7),
        default="#808080",
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
    )
    priority: Mapped[int] = mapped_column(
        default=0,
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<ChatCategory(id={self.id}, name={self.name}, slug={self.slug})>"


class FolderCategory(BaseModel):
    """
    Many-to-many relation between Folder and ChatCategory.

    Attributes:
        folder_id: Folder UUID
        category_id: Category UUID
        confidence: Auto-detection confidence (0.0-1.0)
        is_manual: Manually assigned (not auto-detected)
    """

    __tablename__ = "folder_categories"

    folder_id: Mapped[str] = mapped_column(
        String(36),  # UUID as string
        nullable=False,
        index=True,
    )
    category_id: Mapped[str] = mapped_column(
        String(36),  # UUID as string
        nullable=False,
        index=True,
    )
    confidence: Mapped[float] = mapped_column(
        default=1.0,
        nullable=False,
    )
    is_manual: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<FolderCategory(folder={self.folder_id}, category={self.category_id})>"
