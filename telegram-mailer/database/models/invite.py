"""Invite key model."""

from datetime import datetime
from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.models.base import BaseModel

if TYPE_CHECKING:
    from database.models.user import User


class InviteKey(BaseModel):
    """
    Invite key model.

    Represents an invitation key for user registration.

    Attributes:
        key: Unique invite key string
        created_by: Creator user ID
        used_by: User who used the key (nullable)
        max_uses: Maximum number of uses
        current_uses: Current usage count
        expires_at: Key expiration time
    """

    __tablename__ = "invite_keys"

    key: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=False,
        index=True,
    )
    created_by: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    used_by: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    max_uses: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )
    current_uses: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    creator: Mapped["User"] = relationship(
        "User",
        foreign_keys=[created_by],
        back_populates="created_invite_keys",
    )

    @property
    def is_valid(self) -> bool:
        """Check if invite key is valid for use."""
        if self.current_uses >= self.max_uses:
            return False
        if self.expires_at and self.expires_at < datetime.utcnow():
            return False
        return True

    @property
    def remaining_uses(self) -> int:
        """Get remaining uses count."""
        return max(0, self.max_uses - self.current_uses)

    def __repr__(self) -> str:
        return f"<InviteKey(key={self.key[:8]}..., uses={self.current_uses}/{self.max_uses})>"
