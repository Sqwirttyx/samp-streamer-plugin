"""Throttling middleware."""

import time
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from common.logger import get_logger

logger = get_logger(__name__)


class ThrottlingMiddleware(BaseMiddleware):
    """
    Middleware for rate limiting.

    Prevents users from sending too many requests.
    """

    def __init__(self, rate: float = 0.5):
        """
        Initialize throttling middleware.

        Args:
            rate: Minimum seconds between requests
        """
        self.rate = rate
        self._last_request: Dict[int, float] = {}
        super().__init__()

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        # Get user ID
        user_id = self._get_user_id(event)
        if not user_id:
            return await handler(event, data)

        # Check rate limit
        now = time.time()
        last = self._last_request.get(user_id, 0)

        if now - last < self.rate:
            # Throttled - ignore for callbacks, warn for messages
            if isinstance(event, CallbackQuery):
                await event.answer("⏳ Пожалуйста, подождите...", show_alert=False)
                return None
            elif isinstance(event, Message):
                logger.debug(f"User {user_id} throttled")
                return None

        # Update last request time
        self._last_request[user_id] = now

        # Clean up old entries periodically
        if len(self._last_request) > 10000:
            self._cleanup()

        return await handler(event, data)

    @staticmethod
    def _get_user_id(event: TelegramObject) -> int:
        """Extract user ID from event."""
        if isinstance(event, Message):
            return event.from_user.id if event.from_user else 0
        elif isinstance(event, CallbackQuery):
            return event.from_user.id if event.from_user else 0
        return 0

    def _cleanup(self) -> None:
        """Clean up old entries."""
        now = time.time()
        cutoff = now - 300  # 5 minutes
        self._last_request = {
            user_id: timestamp
            for user_id, timestamp in self._last_request.items()
            if timestamp > cutoff
        }
