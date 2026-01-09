"""Account authorization by code handlers."""

import re
from uuid import uuid4

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton

from bot.config import bot_config
from bot.keyboards.inline import get_cancel_kb
from bot.states import AccountAuthState
from common.constants import AccountStatus, TrustLevel, WarmingPhase
from common.logger import get_logger
from core.trust import TrustScoreCalculator
from database import get_db_manager
from database.repositories import AccountRepository, ProxyRepository
from services.auth import AccountAuthManager, DeviceFingerprint
from storage.session_storage import get_session_storage

logger = get_logger(__name__)

router = Router(name="account_auth")

# Global auth manager (will be initialized with config)
_auth_manager = None


def get_auth_manager() -> AccountAuthManager:
    """Get or create auth manager instance."""
    global _auth_manager
    if _auth_manager is None:
        _auth_manager = AccountAuthManager(
            api_id=bot_config.API_ID,
            api_hash=bot_config.API_HASH,
        )
    return _auth_manager


@router.callback_query(F.data == "account:add_by_code")
async def start_add_by_code(callback: CallbackQuery, state: FSMContext, db_user=None):
    """Start account addition by phone code."""
    if not db_user:
        await callback.answer("Не авторизован", show_alert=True)
        return

    text = """
📱 <b>Добавление аккаунта по номеру</b>

Отправьте номер телефона в международном формате:
Пример: <code>+79001234567</code>

⚠️ <b>Важно:</b>
• Используйте только реальные SIM-карты
• Виртуальные номера (Google Voice и др.) будут забанены
• Новый аккаунт пройдёт 4-6 недель прогрева

💡 Telegram отправит код в приложение на другом устройстве
"""

    await callback.message.edit_text(
        text,
        reply_markup=get_cancel_kb("menu:accounts"),
    )
    await state.set_state(AccountAuthState.waiting_phone)
    await callback.answer()


@router.message(AccountAuthState.waiting_phone)
async def process_phone(message: Message, state: FSMContext, db_user=None):
    """Process phone number input."""
    phone = message.text.strip()

    # Validate phone format
    if not re.match(r'^\+\d{10,15}$', phone):
        await message.answer(
            "❌ Неверный формат номера.\n"
            "Используйте международный формат: <code>+79001234567</code>"
        )
        return

    await message.answer("⏳ Отправляю запрос кода...")

    # Get auth manager and start auth
    auth_manager = get_auth_manager()
    result = await auth_manager.start_auth(message.from_user.id, phone)

    if result["status"] == "code_sent":
        await state.update_data(phone=phone)

        text = f"""
✅ <b>Код отправлен на {phone}</b>

Введите код из Telegram (5 цифр):

⏱ Код действителен {result.get('timeout', 120)} секунд

💡 Если код не приходит:
• Проверьте другие устройства с Telegram
• Код может прийти как сообщение от Telegram
"""

        await message.answer(text, reply_markup=get_cancel_kb("menu:accounts"))
        await state.set_state(AccountAuthState.waiting_code)

    elif result["status"] == "already_pending":
        await message.answer(
            f"⚠️ Код уже отправлен на {result.get('phone', 'номер')}.\n"
            "Введите полученный код или отмените операцию."
        )
        await state.set_state(AccountAuthState.waiting_code)

    else:
        error_messages = {
            "phone_banned": "🚫 Этот номер заблокирован в Telegram.\n"
                          "Возможно, он ранее использовался для спама.",
            "phone_flood": "⏳ Слишком много попыток.\n"
                          "Подождите несколько часов и попробуйте снова.",
            "flood_wait": f"⏳ Подождите {result.get('wait_seconds', 60)} секунд.",
        }

        error_type = result.get("error_type", "unknown")
        error_text = error_messages.get(
            error_type,
            f"❌ Ошибка: {result.get('message', 'Неизвестная ошибка')}"
        )

        await message.answer(error_text, reply_markup=get_cancel_kb("menu:accounts"))
        await state.clear()


@router.message(AccountAuthState.waiting_code)
async def process_code(message: Message, state: FSMContext, db_user=None):
    """Process verification code."""
    code = message.text.strip().replace(" ", "").replace("-", "")

    # Validate code format
    if not code.isdigit() or len(code) != 5:
        await message.answer(
            "❌ Код должен содержать 5 цифр.\n"
            "Пример: <code>12345</code>"
        )
        return

    await message.answer("⏳ Проверяю код...")

    auth_manager = get_auth_manager()
    result = await auth_manager.verify_code(message.from_user.id, code)

    if result["status"] == "success":
        # Success - proceed to save account
        await _handle_auth_success(message, state, result, db_user)

    elif result["status"] == "need_2fa":
        await message.answer(
            "🔐 <b>Требуется пароль 2FA</b>\n\n"
            "Введите пароль двухфакторной аутентификации:",
            reply_markup=get_cancel_kb("menu:accounts"),
        )
        await state.set_state(AccountAuthState.waiting_2fa)

    else:
        error_messages = {
            "code_expired": "⏱ Код истёк. Начните сначала.",
            "invalid_code": f"❌ Неверный код. {result.get('message', '')}",
            "max_attempts": "❌ Превышено количество попыток. Начните сначала.",
            "no_pending": "⚠️ Сессия авторизации не найдена. Начните сначала.",
        }

        error_type = result.get("error_type", "unknown")
        error_text = error_messages.get(
            error_type,
            f"❌ Ошибка: {result.get('message', 'Неизвестная ошибка')}"
        )

        if error_type in ("code_expired", "max_attempts", "no_pending"):
            await state.clear()

        await message.answer(error_text, reply_markup=get_cancel_kb("menu:accounts"))


@router.message(AccountAuthState.waiting_2fa)
async def process_2fa(message: Message, state: FSMContext, db_user=None):
    """Process 2FA password."""
    password = message.text.strip()

    await message.answer("⏳ Проверяю пароль...")

    auth_manager = get_auth_manager()
    result = await auth_manager.verify_2fa(message.from_user.id, password)

    if result["status"] == "success":
        await _handle_auth_success(message, state, result, db_user)
    else:
        error_text = f"❌ {result.get('message', 'Неверный пароль 2FA')}"
        await message.answer(error_text)


async def _handle_auth_success(message: Message, state: FSMContext, result: dict, db_user):
    """Handle successful authorization."""
    account_data = result["account"]
    data = await state.get_data()

    # Calculate initial trust score
    trust_calc = TrustScoreCalculator()

    # Estimate account age from dialogs count
    dialogs_count = account_data.get("dialogs_count", 0)
    estimated_age = min(dialogs_count // 2, 365)  # Rough estimate

    score_data = {
        "age_days": estimated_age,
        "successful_messages": 0,
        "total_bans": 0,
        "days_since_last_ban": 999,
        "organic_activity_count": dialogs_count,
        "contacts_count": 0,
        "groups_count": 0,
        "is_premium": account_data.get("is_premium", False),
        "flood_wait_count_today": 0,
        "is_quarantined": False,
    }

    trust_score = trust_calc.calculate_score(score_data)
    trust_level = trust_calc.get_trust_level(trust_score)

    # Determine initial status
    if estimated_age < 30:
        status = AccountStatus.WARMING_UP
        warming_phase = WarmingPhase.PHASE_1
    elif estimated_age < 90:
        status = AccountStatus.WARMING_UP
        warming_phase = WarmingPhase.PHASE_3
    else:
        status = AccountStatus.ACTIVE
        warming_phase = WarmingPhase.PHASE_4

    # Save session to storage
    storage = get_session_storage()
    account_id = uuid4()

    try:
        session_path = await storage.save_session_string(
            user_id=db_user.id,
            account_id=account_id,
            session_string=account_data["session_string"],
        )
    except Exception as e:
        logger.error(f"Failed to save session: {e}")
        await message.answer(f"❌ Ошибка сохранения сессии: {e}")
        await state.clear()
        return

    # Create account in database
    db_manager = get_db_manager()
    async with db_manager.session() as session:
        repo = AccountRepository(session)

        from storage.session_storage import SessionStorage

        account = await repo.create(
            id=account_id,
            user_id=db_user.id,
            telegram_id=account_data["telegram_id"],
            phone=account_data["phone"],
            phone_hash=SessionStorage.hash_phone(account_data["phone"]),
            username=account_data.get("username"),
            first_name=account_data.get("first_name"),
            session_path=str(session_path),
            session_string=account_data["session_string"],
            status=status,
            trust_score=trust_score,
            trust_level=trust_level,
            is_premium=account_data.get("is_premium", False),
            warming_phase=warming_phase,
            age_days=estimated_age,
            device_fingerprint=account_data.get("device_fingerprint"),
        )

    # Check aggressive mode eligibility
    eligibility = trust_calc.check_aggressive_eligibility(score_data)

    status_text = {
        AccountStatus.WARMING_UP: "🔄 Прогрев",
        AccountStatus.ACTIVE: "✅ Активен",
    }.get(status, "❓")

    text = f"""
✅ <b>Аккаунт успешно добавлен!</b>

👤 ID: <code>{account_data['telegram_id']}</code>
📛 Username: @{account_data.get('username') or 'не указан'}
⭐ Premium: {'Да' if account_data.get('is_premium') else 'Нет'}

📊 <b>Trust Score:</b> {trust_score}/100 ({trust_level.value})
🔄 <b>Статус:</b> {status_text}
📅 <b>Возраст:</b> ~{estimated_age} дней

💡 <b>Рекомендуемый лимит:</b> {eligibility['recommended_daily']} msg/день
⚠️ <b>Уровень риска:</b> {eligibility['risk_level']}
"""

    if eligibility["warnings"]:
        text += "\n⚠️ <b>Предупреждения:</b>\n"
        for warning in eligibility["warnings"][:3]:
            text += f"• {warning}\n"

    # Keyboard for next actions
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📱 Мои аккаунты", callback_data="menu:accounts")],
        [InlineKeyboardButton(text="➕ Добавить ещё", callback_data="account:add_by_code")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu:main")],
    ])

    await message.answer(text, reply_markup=keyboard)
    await state.clear()


@router.callback_query(F.data == "account:cancel_auth")
async def cancel_auth(callback: CallbackQuery, state: FSMContext):
    """Cancel pending authorization."""
    auth_manager = get_auth_manager()
    await auth_manager.cancel_auth(callback.from_user.id)

    await state.clear()
    await callback.answer("Авторизация отменена")

    # Return to accounts menu
    from bot.handlers.accounts import menu_accounts
    await menu_accounts(callback)
