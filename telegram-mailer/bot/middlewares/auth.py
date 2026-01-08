"""Authentication middleware."""

from typing import Any, Awaitable, Callable, Dict, Optional

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from database import get_db_manager
from database.repositories import UserRepository


class AuthMiddleware(BaseMiddleware):
    """
    Middleware for user authentication.

    Checks if user is registered and injects user object into handler data.
    """

    # Commands that don't require authentication
    EXEMPT_COMMANDS = {"/start", "/help"}

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

        # Check if command is exempt
        if isinstance(event, Message) and event.text:
            command = event.text.split()[0] if event.text.startswith("/") else ""
            if command in self.EXEMPT_COMMANDS:
                return await handler(event, data)

        # Get user from database
        db_user = await self._get_db_user(telegram_id)

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

    async def _get_db_user(self, telegram_id: int):
        """Get user from database."""
        db_manager = get_db_manager()
        async with db_manager.session() as session:
            repo = UserRepository(session)
            return await repo.get_by_telegram_id(telegram_id)
