"""User service - business logic for user management."""

from typing import Optional
from uuid import UUID

from common.exceptions import NotFoundError, ValidationError
from common.logger import get_logger
from database import get_db_manager
from database.models import User
from database.repositories import UserRepository, InviteKeyRepository

logger = get_logger(__name__)


class UserService:
    """
    Service for user management.

    Handles user registration, settings, and validation.
    """

    async def get_by_telegram_id(self, telegram_id: int) -> Optional[User]:
        """
        Get user by Telegram ID.

        Args:
            telegram_id: Telegram user ID

        Returns:
            User or None
        """
        db_manager = get_db_manager()

        async with db_manager.readonly_session() as session:
            repo = UserRepository(session)
            return await repo.get_by_telegram_id(telegram_id)

    async def get_by_id(self, user_id: UUID) -> Optional[User]:
        """
        Get user by ID.

        Args:
            user_id: User UUID

        Returns:
            User or None
        """
        db_manager = get_db_manager()

        async with db_manager.readonly_session() as session:
            repo = UserRepository(session)
            return await repo.get_by_id(user_id)

    async def register(
        self,
        telegram_id: int,
        username: Optional[str],
        invite_key: str,
        is_admin: bool = False,
    ) -> User:
        """
        Register new user with invite key.

        Args:
            telegram_id: Telegram user ID
            username: Telegram username
            invite_key: Invite key to use
            is_admin: Whether user is admin

        Returns:
            Created user

        Raises:
            ValidationError: If invite key is invalid
        """
        db_manager = get_db_manager()

        async with db_manager.session() as session:
            # Check if already registered
            user_repo = UserRepository(session)
            existing = await user_repo.get_by_telegram_id(telegram_id)
            if existing:
                raise ValidationError("User already registered")

            # Validate invite key
            invite_repo = InviteKeyRepository(session)
            is_valid = await invite_repo.validate(invite_key)
            if not is_valid:
                raise ValidationError("Invalid invite key")

            # Create user
            user = await user_repo.create_user(
                telegram_id=telegram_id,
                username=username,
                invite_key=invite_key,
                is_admin=is_admin,
            )

            # Mark key as used
            await invite_repo.use_key(invite_key, user.id)

            logger.info(f"User registered: {telegram_id}")
            return user

    async def update_settings(
        self,
        user_id: UUID,
        settings: dict,
    ) -> User:
        """
        Update user settings.

        Args:
            user_id: User UUID
            settings: Settings dictionary to merge

        Returns:
            Updated user
        """
        db_manager = get_db_manager()

        async with db_manager.session() as session:
            repo = UserRepository(session)
            user = await repo.get_by_id(user_id)

            if not user:
                raise NotFoundError("User not found")

            # Merge settings
            current_settings = user.settings or {}
            current_settings.update(settings)

            user.settings = current_settings
            await session.flush()

            logger.info(f"User settings updated: {user_id}")
            return user

    async def get_settings(self, user_id: UUID) -> dict:
        """
        Get user settings.

        Args:
            user_id: User UUID

        Returns:
            Settings dictionary
        """
        user = await self.get_by_id(user_id)
        if not user:
            raise NotFoundError("User not found")

        return user.settings or {}

    async def set_admin(self, user_id: UUID, is_admin: bool) -> User:
        """
        Set user admin status.

        Args:
            user_id: User UUID
            is_admin: Admin status

        Returns:
            Updated user
        """
        db_manager = get_db_manager()

        async with db_manager.session() as session:
            repo = UserRepository(session)
            user = await repo.get_by_id(user_id)

            if not user:
                raise NotFoundError("User not found")

            user.is_admin = is_admin
            await session.flush()

            logger.info(f"User admin status changed: {user_id} -> {is_admin}")
            return user

    async def get_all_users(self, limit: int = 100) -> list[User]:
        """
        Get all users.

        Args:
            limit: Maximum users to return

        Returns:
            List of users
        """
        db_manager = get_db_manager()

        async with db_manager.readonly_session() as session:
            repo = UserRepository(session)
            return await repo.get_all(limit=limit)

    async def get_active_users(self, days: int = 7) -> list[User]:
        """
        Get recently active users.

        Args:
            days: Number of days to consider active

        Returns:
            List of active users
        """
        db_manager = get_db_manager()

        async with db_manager.readonly_session() as session:
            repo = UserRepository(session)
            return await repo.get_active_users(days=days)

    async def delete_user(self, user_id: UUID) -> bool:
        """
        Delete user.

        Args:
            user_id: User UUID

        Returns:
            True if deleted
        """
        db_manager = get_db_manager()

        async with db_manager.session() as session:
            repo = UserRepository(session)
            result = await repo.delete(user_id)

            if result:
                logger.info(f"User deleted: {user_id}")

            return result
