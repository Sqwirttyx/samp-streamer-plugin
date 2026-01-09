"""Bot main entry point."""

import asyncio
from typing import Optional

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from bot.config import bot_config
from bot.handlers import (
    accounts,
    account_auth,
    admin,
    campaigns,
    folders,
    proxy,
    start,
    stats,
)
from bot.middlewares.auth import AuthMiddleware
from bot.middlewares.throttling import ThrottlingMiddleware
from common.logger import get_logger
from database import init_db
from redis_client.connection import get_redis_manager

logger = get_logger(__name__)


def create_bot() -> Bot:
    """Create and configure bot instance."""
    return Bot(
        token=bot_config.TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )


def create_dispatcher() -> Dispatcher:
    """Create and configure dispatcher with handlers and middlewares."""
    dp = Dispatcher(storage=MemoryStorage())

    # Register middlewares
    dp.message.middleware(ThrottlingMiddleware())
    dp.callback_query.middleware(ThrottlingMiddleware(rate=bot_config.CALLBACK_THROTTLE_RATE))
    dp.message.middleware(AuthMiddleware())
    dp.callback_query.middleware(AuthMiddleware())

    # Register handlers
    dp.include_router(start.router)
    dp.include_router(accounts.router)
    dp.include_router(account_auth.router)
    dp.include_router(folders.router)
    dp.include_router(proxy.router)
    dp.include_router(campaigns.router)
    dp.include_router(stats.router)
    dp.include_router(admin.router)

    return dp


async def on_startup(bot: Bot) -> None:
    """Startup hook."""
    logger.info("Bot starting up...")

    # Initialize database
    await init_db()
    logger.info("Database initialized")

    # Initialize Redis
    redis_manager = get_redis_manager()
    await redis_manager.init()
    logger.info("Redis initialized")

    # Get bot info
    bot_info = await bot.get_me()
    logger.info(f"Bot started: @{bot_info.username}")


async def on_shutdown(bot: Bot) -> None:
    """Shutdown hook."""
    logger.info("Bot shutting down...")

    # Close Redis
    redis_manager = get_redis_manager()
    await redis_manager.close()

    logger.info("Bot shutdown complete")


async def run_bot() -> None:
    """Run the bot."""
    bot = create_bot()
    dp = create_dispatcher()

    # Register lifecycle hooks
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    try:
        logger.info("Starting bot polling...")
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()


def main() -> None:
    """Main entry point."""
    asyncio.run(run_bot())


if __name__ == "__main__":
    main()
