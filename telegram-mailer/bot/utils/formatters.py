"""Message formatting utilities."""

from datetime import timedelta
from typing import Optional


def format_number(value: int) -> str:
    """
    Format number with thousands separator.

    Args:
        value: Number to format

    Returns:
        Formatted string (e.g., "1,234,567")
    """
    return f"{value:,}".replace(",", " ")


def format_duration(seconds: int) -> str:
    """
    Format duration in human-readable format.

    Args:
        seconds: Duration in seconds

    Returns:
        Formatted string (e.g., "2ч 30мин", "45мин", "30сек")
    """
    if seconds < 60:
        return f"{seconds}сек"

    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}мин"

    hours = minutes // 60
    remaining_minutes = minutes % 60

    if remaining_minutes == 0:
        return f"{hours}ч"

    return f"{hours}ч {remaining_minutes}мин"


def format_duration_long(seconds: int) -> str:
    """
    Format duration in long human-readable format.

    Args:
        seconds: Duration in seconds

    Returns:
        Formatted string (e.g., "2 часа 30 минут")
    """
    if seconds < 60:
        return f"{seconds} секунд"

    minutes = seconds // 60
    if minutes < 60:
        word = _get_plural(minutes, "минута", "минуты", "минут")
        return f"{minutes} {word}"

    hours = minutes // 60
    remaining_minutes = minutes % 60

    hour_word = _get_plural(hours, "час", "часа", "часов")
    if remaining_minutes == 0:
        return f"{hours} {hour_word}"

    minute_word = _get_plural(remaining_minutes, "минута", "минуты", "минут")
    return f"{hours} {hour_word} {remaining_minutes} {minute_word}"


def format_phone(phone_hash: str) -> str:
    """
    Format phone hash for display.

    Args:
        phone_hash: Phone hash string

    Returns:
        Masked phone display (e.g., "***1234")
    """
    return f"***{phone_hash[:4]}"


def format_progress_bar(
    current: int,
    total: int,
    width: int = 10,
    filled: str = "█",
    empty: str = "░",
) -> str:
    """
    Create a text progress bar.

    Args:
        current: Current progress value
        total: Total value
        width: Bar width in characters
        filled: Character for filled portion
        empty: Character for empty portion

    Returns:
        Progress bar string (e.g., "████░░░░░░ 40%")
    """
    if total == 0:
        return f"{empty * width} 0%"

    percentage = min(100, (current / total) * 100)
    filled_width = int(width * percentage / 100)
    empty_width = width - filled_width

    bar = filled * filled_width + empty * empty_width
    return f"{bar} {percentage:.0f}%"


def format_stats_summary(
    sent: int,
    errors: int,
    flood_waits: int = 0,
) -> str:
    """
    Format statistics summary.

    Args:
        sent: Messages sent
        errors: Errors count
        flood_waits: FloodWait count

    Returns:
        Formatted summary string
    """
    total = sent + errors
    success_rate = (sent / total * 100) if total > 0 else 0

    lines = [
        f"📨 Отправлено: {format_number(sent)}",
        f"❌ Ошибок: {format_number(errors)}",
        f"✅ Успешность: {success_rate:.1f}%",
    ]

    if flood_waits > 0:
        lines.append(f"⏳ FloodWait: {flood_waits}")

    return "\n".join(lines)


def format_account_status(
    status: str,
    health_score: int,
    flood_until: Optional[str] = None,
) -> str:
    """
    Format account status for display.

    Args:
        status: Account status string
        health_score: Health score 0-100
        flood_until: FloodWait expiry time

    Returns:
        Formatted status string
    """
    status_emoji = {
        "active": "✅",
        "paused": "⏸️",
        "banned": "🚫",
        "error": "❌",
    }.get(status, "❓")

    health_emoji = "💚" if health_score >= 80 else "💛" if health_score >= 50 else "❤️"

    text = f"{status_emoji} {status.title()} | {health_emoji} {health_score}%"

    if flood_until:
        text += f"\n⏳ FloodWait до: {flood_until}"

    return text


def format_campaign_info(
    name: str,
    status: str,
    sent: int,
    total_chats: int,
    cycle: int,
) -> str:
    """
    Format campaign info for display.

    Args:
        name: Campaign name
        status: Campaign status
        sent: Messages sent in current cycle
        total_chats: Total chats in folder
        cycle: Current cycle number

    Returns:
        Formatted campaign info
    """
    status_emoji = {
        "draft": "📝",
        "scheduled": "📅",
        "active": "▶️",
        "paused": "⏸️",
        "completed": "✅",
        "error": "❌",
    }.get(status, "❓")

    progress = format_progress_bar(sent, total_chats)

    return f"""
{status_emoji} <b>{name}</b>

📊 Прогресс: {progress}
💬 {sent}/{total_chats} чатов
🔄 Цикл: {cycle}
"""


def _get_plural(n: int, form1: str, form2: str, form3: str) -> str:
    """
    Get correct plural form for Russian language.

    Args:
        n: Number
        form1: Form for 1 (минута)
        form2: Form for 2-4 (минуты)
        form3: Form for 5-20 and 0 (минут)

    Returns:
        Correct plural form
    """
    n = abs(n) % 100

    if 10 < n < 20:
        return form3

    n = n % 10

    if n == 1:
        return form1
    elif 1 < n < 5:
        return form2
    else:
        return form3


def escape_html(text: str) -> str:
    """
    Escape HTML special characters.

    Args:
        text: Text to escape

    Returns:
        Escaped text
    """
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """
    Truncate text to specified length.

    Args:
        text: Text to truncate
        max_length: Maximum length
        suffix: Suffix to add if truncated

    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text
    return text[: max_length - len(suffix)] + suffix
