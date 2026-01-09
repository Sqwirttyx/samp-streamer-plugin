"""Authentication middleware."""

from typing import Any, Awaitable, Callable, Dict, Optional

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from database import get_db_manager
from database.repositories import UserRepository

# Master key for admin access
MASTER_KEY = "JSjsk7NiJ9777M"


class AuthMiddleware(BaseMiddleware):
    """
    Middleware for user authentication.

    - Auto-registers new users on first interaction
    - Checks admin status
    - Injects user object into handler data
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        # Get user from event
        user = self._get_user(event)
        if not user:
            return await handler(event, data)

        telegram_id = user.id
        username = user.username

        # Get or create user in database
        db_user = await self._get_or_create_user(telegram_id, username)

        # Inject user into data
        data["db_user"] = db_user
        data["is_registered"] = db_user is not None
        data["is_admin"] = db_user.is_admin if db_user else False

        return await handler(event, data)

    @staticmethod
    def _get_user(event: TelegramObject) -> Optional[Any]:
        """Extract user from event."""
        if isinstance(event, Message):
            return event.from_user
        elif isinstance(event, CallbackQuery):
            return event.from_user
        return None

    async def _get_or_create_user(self, telegram_id: int, username: Optional[str] = None):
        """
        Get user from database, or create if not exists.

        All users are automatically registered on first interaction.
        """
        db_manager = get_db_manager()

        async with db_manager.session() as session:
            repo = UserRepository(session)

            # Try to get existing user
            user = await repo.get_by_telegram_id(telegram_id)

            if not user:
                # Auto-register new user
                user = await repo.create_user(
                    telegram_id=telegram_id,
                    username=username,
                    is_admin=False,
                )
            elif username and user.username != username:
                # Update username if changed
                user.username = username
                await session.flush()

            return user
