"""Text variation system for message uniqueness."""

import random
import re
from typing import Dict, List, Optional

from common.constants import INVISIBLE_CHARS
from common.logger import get_logger

logger = get_logger(__name__)


class TextVariationSystem:
    """
    Advanced text variation for spam filter bypass.

    At 8000+ messages per day, EACH message must be unique.
    Telegram ML detects patterns - even 5 identical messages
    with 3-minute pauses can trigger detection.

    Techniques:
    1. Synonym replacement
    2. Emoji variation
    3. Punctuation changes
    4. Zero-width character insertion (invisible uniqueness)
    5. Unique invisible signature per message
    """

    # Russian synonyms for common advertising words
    SYNONYMS: Dict[str, List[str]] = {
        # Greetings
        "привет": ["хай", "здравствуйте", "добрый день", "приветствую", "доброго времени"],
        "здравствуйте": ["привет", "добрый день", "приветствую"],

        # Advertising terms
        "реклама": ["промо", "размещение", "публикация", "пост", "объявление"],
        "закреп": ["закреплённый пост", "топ", "шапка", "пин", "первый пост"],
        "свободен": ["доступен", "открыт", "можно занять", "есть место", "актуально"],
        "свободна": ["доступна", "открыта", "можно занять", "есть место"],
        "занят": ["забронирован", "недоступен", "закрыт"],

        # Price terms
        "цена": ["стоимость", "прайс", "условия", "тариф", "расценки"],
        "дешево": ["недорого", "доступно", "бюджетно", "выгодно"],
        "бесплатно": ["без оплаты", "даром", "безвозмездно"],

        # Actions
        "пишите": ["обращайтесь", "пишите в лс", "напишите", "связь в лс"],
        "подробности": ["детали", "информация", "инфо", "подробнее", "условия"],
        "смотрите": ["читайте", "изучите", "ознакомьтесь"],

        # Objects
        "канал": ["паблик", "сообщество", "группа", "чат"],
        "чат": ["группа", "сообщество", "беседа"],

        # Time
        "срочно": ["быстро", "оперативно", "скоро", "в ближайшее время"],
        "сегодня": ["сейчас", "в этот день", "прямо сейчас"],
        "скоро": ["в ближайшее время", "скоро", "вот-вот"],
    }

    # Interchangeable emoji groups
    EMOJI_GROUPS: Dict[str, List[str]] = {
        "attention": ["📌", "📣", "🔔", "❗", "⚠️", "🎯", "💡", "👀", "📢"],
        "positive": ["✅", "💚", "👍", "🔥", "⭐", "💎", "✨", "🚀", "👌"],
        "money": ["💰", "💵", "💸", "🤑", "💳", "💲"],
        "arrow": ["👉", "👇", "➡️", "▶️", "🔜", "⬇️"],
        "fire": ["🔥", "💥", "⚡", "✨", "💫"],
    }

    # All emojis in one set for detection
    ALL_EMOJIS = set()
    for emojis in EMOJI_GROUPS.values():
        ALL_EMOJIS.update(emojis)

    # Punctuation variations
    ENDINGS = [".", "!", "!!", " 👇", " ⬇️", "...", "", " ✅", " 🔥"]

    def __init__(self):
        """Initialize variation system."""
        self.counter = 0

    def variate(self, text: str) -> str:
        """
        Create unique variation of text.

        Args:
            text: Original message text

        Returns:
            Varied unique text
        """
        self.counter += 1
        result = text

        # 1. Replace synonyms (40% chance per word)
        result = self._replace_synonyms(result)

        # 2. Replace emojis with alternatives
        result = self._replace_emojis(result)

        # 3. Vary ending punctuation
        result = self._vary_ending(result)

        # 4. Insert invisible characters (guarantees uniqueness)
        result = self._insert_invisible(result)

        # 5. Add unique invisible signature
        result = self._add_signature(result)

        return result

    def _replace_synonyms(self, text: str, probability: float = 0.4) -> str:
        """Replace words with synonyms."""
        result = text

        for word, synonyms in self.SYNONYMS.items():
            if word.lower() in result.lower() and random.random() < probability:
                # Case-insensitive replacement
                pattern = re.compile(re.escape(word), re.IGNORECASE)
                replacement = random.choice(synonyms)

                # Match case of original
                def match_case(match):
                    original = match.group(0)
                    if original.isupper():
                        return replacement.upper()
                    elif original[0].isupper():
                        return replacement.capitalize()
                    return replacement

                result = pattern.sub(match_case, result, count=1)

        return result

    def _replace_emojis(self, text: str) -> str:
        """Replace emojis with alternatives from same group."""
        result = text

        for group_name, emojis in self.EMOJI_GROUPS.items():
            for emoji in emojis:
                if emoji in result and random.random() < 0.5:
                    replacement = random.choice(emojis)
                    result = result.replace(emoji, replacement, 1)

        return result

    def _vary_ending(self, text: str) -> str:
        """Vary ending punctuation."""
        text = text.rstrip()

        # Check current ending
        for end in [".", "!", "?", "..."]:
            if text.endswith(end):
                # Remove old ending
                text = text[:-len(end)]
                # Add new random ending
                text += random.choice(self.ENDINGS)
                break
        else:
            # No punctuation - maybe add one
            if random.random() < 0.3:
                text += random.choice(self.ENDINGS)

        return text

    def _insert_invisible(self, text: str) -> str:
        """Insert invisible zero-width characters for uniqueness."""
        if len(text) < 10:
            return text

        result = text

        # Insert 2-4 invisible characters at random positions
        for _ in range(random.randint(2, 4)):
            if len(result) > 10:
                pos = random.randint(5, len(result) - 5)
                char = random.choice(INVISIBLE_CHARS)
                result = result[:pos] + char + result[pos:]

        return result

    def _add_signature(self, text: str) -> str:
        """
        Add unique invisible signature.

        Encodes counter into sequence of zero-width chars.
        This guarantees every message is unique.
        """
        # Encode counter + random into invisible chars
        n = self.counter + random.randint(0, 10000)

        signature = ""
        while n > 0:
            signature += INVISIBLE_CHARS[n % len(INVISIBLE_CHARS)]
            n //= len(INVISIBLE_CHARS)

        # Add more randomness
        signature += random.choice(INVISIBLE_CHARS)

        return text + signature

    def bulk_variate(self, text: str, count: int) -> List[str]:
        """
        Generate multiple unique variations.

        Args:
            text: Original text
            count: Number of variations

        Returns:
            List of unique variations
        """
        variations = set()

        while len(variations) < count:
            variation = self.variate(text)
            variations.add(variation)

        return list(variations)


class MessageTypeVariator:
    """Vary message types for more natural behavior."""

    # Distribution of message types
    MESSAGE_TYPES = {
        "text_only": 0.55,
        "text_with_photo": 0.25,
        "text_with_gif": 0.10,
        "text_with_video": 0.05,
        "photo_with_caption": 0.05,
    }

    def __init__(self):
        """Initialize variator."""
        self.previous_types: List[str] = []

    def choose_type(self) -> str:
        """
        Choose message type avoiding repetition.

        Returns:
            Message type string
        """
        available = list(self.MESSAGE_TYPES.keys())

        # Don't repeat last 2 types
        if len(self.previous_types) >= 1:
            last = self.previous_types[-1]
            if last in available:
                available.remove(last)

        if len(self.previous_types) >= 2:
            second_last = self.previous_types[-2]
            if second_last in available:
                available.remove(second_last)

        # Weighted random choice
        weights = [self.MESSAGE_TYPES.get(t, 0.1) for t in available]
        total = sum(weights)
        weights = [w / total for w in weights]

        chosen = random.choices(available, weights=weights, k=1)[0]

        # Track history
        self.previous_types.append(chosen)
        if len(self.previous_types) > 5:
            self.previous_types.pop(0)

        return chosen


# Global instance for convenience
text_variator = TextVariationSystem()


def variate_text(text: str) -> str:
    """
    Convenience function to variate text.

    Args:
        text: Original text

    Returns:
        Varied text
    """
    return text_variator.variate(text)
