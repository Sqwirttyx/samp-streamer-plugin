"""Bot configuration."""

from common.config import settings


class BotConfig:
    """Bot-specific configuration."""

    TOKEN = settings.bot_token
    ADMIN_IDS = settings.admin_ids

    # Throttling
    THROTTLE_RATE = 0.5  # seconds between messages
    CALLBACK_THROTTLE_RATE = 1.0  # seconds between callback queries

    # Pagination
    ITEMS_PER_PAGE = 10

    # Messages
    WELCOME_MESSAGE = """
👋 Добро пожаловать в Telegram Mailer!

Это система для управления рассылками в Telegram.

Используйте меню ниже для навигации.
"""

    HELP_MESSAGE = """
📚 Справка по использованию бота:

📱 **Аккаунты** - управление Telegram аккаунтами
📁 **Папки** - управление папками с чатами
📨 **Рассылки** - создание и управление рассылками
📊 **Статистика** - просмотр статистики
👑 **Админка** - /admin (требуется мастер-ключ)

❓ По вопросам обращайтесь к администратору.
"""

    NOT_AUTHORIZED = """
🚫 У вас нет доступа к этой функции.

Для получения прав администратора используйте команду /admin
"""


bot_config = BotConfig()
