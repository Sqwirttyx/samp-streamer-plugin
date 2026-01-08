"""Invite key repository."""

import secrets
from datetime import datetime, timedelta
from typing import Optional, Sequence
from uuid import UUID

from sqlalchemy import select, update

from database.models.invite import InviteKey
from database.repositories.base import BaseRepository


class InviteKeyRepository(BaseRepository[InviteKey]):
    """Repository for InviteKey model operations."""

    model = InviteKey

    @staticmethod
    def generate_key(length: int = 32) -> str:
        """
        Generate a random invite key.

        Args:
            length: Key length

        Returns:
            Random key string
        """
        return secrets.token_urlsafe(length)[:length]

    async def get_by_key(self, key: str) -> Optional[InviteKey]:
        """
        Get invite key by key string.

        Args:
            key: Invite key string

        Returns:
            InviteKey or None
        """
        result = await self.session.execute(
            select(InviteKey).where(InviteKey.key == key)
        )
        return result.scalar_one_or_none()

    async def create_key(
        self,
        created_by: UUID,
        max_uses: int = 1,
        expires_in_days: Optional[int] = None,
    ) -> InviteKey:
        """
        Create a new invite key.

        Args:
            created_by: Creator user UUID
            max_uses: Maximum number of uses
            expires_in_days: Days until expiration (None = no expiration)

        Returns:
            Created invite key
        """
        expires_at = None
        if expires_in_days:
            expires_at = datetime.utcnow() + timedelta(days=expires_in_days)

        return await self.create(
            key=self.generate_key(),
            created_by=created_by,
            max_uses=max_uses,
            current_uses=0,
            expires_at=expires_at,
        )

    async def create_batch(
        self,
        created_by: UUID,
        count: int,
        max_uses: int = 1,
        expires_in_days: Optional[int] = None,
    ) -> list[InviteKey]:
        """
        Create multiple invite keys.

        Args:
            created_by: Creator user UUID
            count: Number of keys to create
            max_uses: Maximum uses per key
            expires_in_days: Days until expiration

        Returns:
            List of created invite keys
        """
        keys = []
        for _ in range(count):
            key = await self.create_key(
                created_by=created_by,
                max_uses=max_uses,
                expires_in_days=expires_in_days,
            )
            keys.append(key)
        return keys

    async def validate(self, key: str) -> bool:
        """
        Validate if invite key can be used.

        Args:
            key: Invite key string

        Returns:
            True if valid, False otherwise
        """
        invite_key = await self.get_by_key(key)
        return invite_key is not None and invite_key.is_valid

    async def use_key(
        self,
        key: str,
        used_by: UUID,
    ) -> Optional[InviteKey]:
        """
        Use an invite key.

        Args:
            key: Invite key string
            used_by: User who uses the key

        Returns:
            Updated invite key or None if invalid
        """
        invite_key = await self.get_by_key(key)
        if not invite_key or not invite_key.is_valid:
            return None

        await self.session.execute(
            update(InviteKey)
            .where(InviteKey.key == key)
            .values(
                current_uses=InviteKey.current_uses + 1,
                used_by=used_by,
            )
        )
        await self.session.flush()
        return await self.get_by_key(key)

    async def get_by_creator(
        self,
        created_by: UUID,
        offset: int = 0,
        limit: int = 100,
    ) -> Sequence[InviteKey]:
        """
        Get invite keys created by user.

        Args:
            created_by: Creator user UUID
            offset: Pagination offset
            limit: Pagination limit

        Returns:
            List of invite keys
        """
        result = await self.session.execute(
            select(InviteKey)
            .where(InviteKey.created_by == created_by)
            .order_by(InviteKey.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return result.scalars().all()

    async def get_unused(self, created_by: UUID) -> Sequence[InviteKey]:
        """
        Get unused invite keys created by user.

        Args:
            created_by: Creator user UUID

        Returns:
            List of unused invite keys
        """
        now = datetime.utcnow()
        result = await self.session.execute(
            select(InviteKey)
            .where(
                InviteKey.created_by == created_by,
                InviteKey.current_uses < InviteKey.max_uses,
                (InviteKey.expires_at == None) | (InviteKey.expires_at > now),
            )
            .order_by(InviteKey.created_at.desc())
        )
        return result.scalars().all()

    async def count_by_creator(self, created_by: UUID) -> int:
        """
        Count invite keys created by user.

        Args:
            created_by: Creator user UUID

        Returns:
            Number of invite keys
        """
        return await self.count(created_by=created_by)

    async def revoke(self, key: str) -> bool:
        """
        Revoke an invite key (set max_uses to current_uses).

        Args:
            key: Invite key string

        Returns:
            True if revoked, False if not found
        """
        invite_key = await self.get_by_key(key)
        if not invite_key:
            return False

        await self.session.execute(
            update(InviteKey)
            .where(InviteKey.key == key)
            .values(max_uses=invite_key.current_uses)
        )
        await self.session.flush()
        return True
