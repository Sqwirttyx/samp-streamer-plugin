"""User repository."""

from typing import Any, Optional

from sqlalchemy import select, update

from database.models.user import User
from database.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    """Repository for User model operations."""

    model = User

    async def get_by_telegram_id(self, telegram_id: int) -> Optional[User]:
        """
        Get user by Telegram ID.

        Args:
            telegram_id: Telegram user ID

        Returns:
            User instance or None
        """
        result = await self.session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()

    async def create_user(
        self,
        telegram_id: int,
        username: Optional[str] = None,
        invite_key: Optional[str] = None,
        is_admin: bool = False,
    ) -> User:
        """
        Create a new user.

        Args:
            telegram_id: Telegram user ID
            username: Telegram username
            invite_key: Invite key used for registration
            is_admin: Admin flag

        Returns:
            Created user instance
        """
        return await self.create(
            telegram_id=telegram_id,
            username=username,
            invite_key=invite_key,
            is_admin=is_admin,
            is_active=True,
            settings={},
        )

    async def update_settings(
        self,
        telegram_id: int,
        settings: dict[str, Any],
    ) -> Optional[User]:
        """
        Update user settings.

        Args:
            telegram_id: Telegram user ID
            settings: New settings dictionary

        Returns:
            Updated user or None
        """
        user = await self.get_by_telegram_id(telegram_id)
        if not user:
            return None

        current_settings = user.settings or {}
        current_settings.update(settings)

        await self.session.execute(
            update(User)
            .where(User.telegram_id == telegram_id)
            .values(settings=current_settings)
        )
        await self.session.flush()
        return await self.get_by_telegram_id(telegram_id)

    async def set_admin(self, telegram_id: int, is_admin: bool) -> Optional[User]:
        """
        Set user admin status.

        Args:
            telegram_id: Telegram user ID
            is_admin: Admin flag

        Returns:
            Updated user or None
        """
        await self.session.execute(
            update(User)
            .where(User.telegram_id == telegram_id)
            .values(is_admin=is_admin)
        )
        await self.session.flush()
        return await self.get_by_telegram_id(telegram_id)

    async def deactivate(self, telegram_id: int) -> Optional[User]:
        """
        Deactivate user.

        Args:
            telegram_id: Telegram user ID

        Returns:
            Updated user or None
        """
        await self.session.execute(
            update(User)
            .where(User.telegram_id == telegram_id)
            .values(is_active=False)
        )
        await self.session.flush()
        return await self.get_by_telegram_id(telegram_id)

    async def get_admins(self) -> list[User]:
        """
        Get all admin users.

        Returns:
            List of admin users
        """
        result = await self.session.execute(
            select(User).where(User.is_admin == True, User.is_active == True)
        )
        return list(result.scalars().all())

    async def get_active_users(self, offset: int = 0, limit: int = 100) -> list[User]:
        """
        Get all active users.

        Args:
            offset: Pagination offset
            limit: Pagination limit

        Returns:
            List of active users
        """
        result = await self.session.execute(
            select(User)
            .where(User.is_active == True)
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all())
