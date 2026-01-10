"""
Auto-categorizer service for chat/folder classification.

Analyzes chat titles and descriptions to automatically assign categories.
"""

import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

from common.logger import get_logger

logger = get_logger(__name__)


@dataclass
class CategoryMatch:
    """Result of category matching."""
    slug: str
    name: str
    confidence: float
    matched_keywords: List[str]


# Default category patterns
DEFAULT_CATEGORIES: Dict[str, Dict] = {
    "crypto": {
        "name": "Крипто",
        "icon": "💰",
        "keywords": [
            "bitcoin", "btc", "crypto", "крипто", "биткоин", "эфир", "ethereum",
            "eth", "blockchain", "блокчейн", "defi", "nft", "токен", "token",
            "binance", "бинанс", "трейдинг", "trading", "pump", "памп", "альткоин",
            "altcoin", "hodl", "майнинг", "mining", "wallet", "кошелек", "usdt",
            "tether", "стейкинг", "staking", "airdrop", "эирдроп", "web3"
        ],
    },
    "business": {
        "name": "Бизнес",
        "icon": "💼",
        "keywords": [
            "бизнес", "business", "заработок", "деньги", "money", "инвестиц",
            "invest", "доход", "income", "прибыль", "profit", "стартап", "startup",
            "предприниматель", "entrepreneur", "млм", "mlm", "партнер", "partner",
            "франшиза", "franchise", "пассивный доход", "финанс", "finance"
        ],
    },
    "dating": {
        "name": "Знакомства",
        "icon": "💕",
        "keywords": [
            "знакомств", "dating", "девушк", "парн", "отношени", "relationship",
            "любов", "love", "свидани", "date", "романтик", "romantic", "флирт",
            "flirt", "одинок", "single", "встреч", "meet", "18+"
        ],
    },
    "gambling": {
        "name": "Гемблинг",
        "icon": "🎰",
        "keywords": [
            "казино", "casino", "ставки", "betting", "bet", "слот", "slot",
            "покер", "poker", "рулетка", "roulette", "джекпот", "jackpot",
            "1xbet", "1win", "пинап", "pinup", "букмекер", "bookmaker",
            "азарт", "gambling", "выигрыш", "win"
        ],
    },
    "education": {
        "name": "Обучение",
        "icon": "📚",
        "keywords": [
            "обучение", "education", "курс", "course", "урок", "lesson",
            "школа", "school", "университет", "university", "вебинар", "webinar",
            "тренинг", "training", "мастер-класс", "masterclass", "учеб", "study",
            "репетитор", "tutor", "навык", "skill"
        ],
    },
    "marketing": {
        "name": "Маркетинг",
        "icon": "📢",
        "keywords": [
            "маркетинг", "marketing", "реклама", "advertising", "smm", "сео",
            "seo", "таргет", "target", "продвижени", "promotion", "трафик",
            "traffic", "лид", "lead", "конверсия", "conversion", "воронка",
            "funnel", "контент", "content", "бренд", "brand"
        ],
    },
    "tech": {
        "name": "IT/Технологии",
        "icon": "💻",
        "keywords": [
            "программ", "program", "разработ", "develop", "код", "code",
            "python", "javascript", "java", "it", "айти", "софт", "software",
            "приложени", "app", "веб", "web", "дизайн", "design", "frontend",
            "backend", "devops", "linux", "android", "ios"
        ],
    },
    "news": {
        "name": "Новости",
        "icon": "📰",
        "keywords": [
            "новост", "news", "события", "events", "политик", "politic",
            "экономик", "econom", "мир", "world", "россия", "russia",
            "украина", "ukraine", "сводк", "digest", "обзор", "review"
        ],
    },
    "entertainment": {
        "name": "Развлечения",
        "icon": "🎬",
        "keywords": [
            "мем", "meme", "юмор", "humor", "приколы", "fun", "смешн",
            "funny", "фильм", "movie", "сериал", "series", "музык", "music",
            "игр", "game", "аним", "anime", "видео", "video", "стрим", "stream"
        ],
    },
    "health": {
        "name": "Здоровье",
        "icon": "🏥",
        "keywords": [
            "здоров", "health", "фитнес", "fitness", "спорт", "sport",
            "похуд", "diet", "питани", "nutrition", "йога", "yoga",
            "медицин", "medic", "врач", "doctor", "лечени", "treatment"
        ],
    },
}


class AutoCategorizer:
    """
    Automatic chat/folder categorizer based on keywords.

    Usage:
        categorizer = AutoCategorizer()
        matches = categorizer.categorize("Крипто трейдинг BTC")
        # [CategoryMatch(slug='crypto', name='Крипто', confidence=0.85, ...)]
    """

    def __init__(self, categories: Optional[Dict] = None):
        """
        Initialize categorizer.

        Args:
            categories: Custom categories dict (uses defaults if None)
        """
        self.categories = categories or DEFAULT_CATEGORIES
        self._compile_patterns()

    def _compile_patterns(self) -> None:
        """Compile regex patterns for faster matching."""
        self._patterns: Dict[str, List[re.Pattern]] = {}

        for slug, data in self.categories.items():
            patterns = []
            for keyword in data.get("keywords", []):
                # Case-insensitive pattern with word boundaries
                try:
                    pattern = re.compile(
                        rf'\b{re.escape(keyword)}\w*',
                        re.IGNORECASE | re.UNICODE
                    )
                    patterns.append((keyword, pattern))
                except re.error:
                    logger.warning(f"Invalid keyword pattern: {keyword}")
            self._patterns[slug] = patterns

    def categorize(
        self,
        text: str,
        min_confidence: float = 0.3,
        max_categories: int = 3,
    ) -> List[CategoryMatch]:
        """
        Categorize text based on keyword matching.

        Args:
            text: Text to analyze (title, description, etc.)
            min_confidence: Minimum confidence threshold (0.0-1.0)
            max_categories: Maximum categories to return

        Returns:
            List of CategoryMatch sorted by confidence (descending)
        """
        if not text:
            return []

        text_lower = text.lower()
        results: List[CategoryMatch] = []

        for slug, patterns in self._patterns.items():
            matched_keywords = []

            for keyword, pattern in patterns:
                if pattern.search(text_lower):
                    matched_keywords.append(keyword)

            if matched_keywords:
                # Calculate confidence based on:
                # - Number of matched keywords
                # - Ratio of matched to total keywords
                total_keywords = len(patterns)
                matched_count = len(matched_keywords)

                # Base confidence from match ratio
                base_confidence = matched_count / max(total_keywords, 1)

                # Boost for multiple matches
                boost = min(0.3, matched_count * 0.1)

                confidence = min(1.0, base_confidence + boost)

                if confidence >= min_confidence:
                    cat_data = self.categories[slug]
                    results.append(CategoryMatch(
                        slug=slug,
                        name=cat_data["name"],
                        confidence=round(confidence, 2),
                        matched_keywords=matched_keywords[:5],  # Top 5
                    ))

        # Sort by confidence and limit
        results.sort(key=lambda x: x.confidence, reverse=True)
        return results[:max_categories]

    def get_best_category(self, text: str) -> Optional[CategoryMatch]:
        """
        Get single best matching category.

        Args:
            text: Text to analyze

        Returns:
            Best CategoryMatch or None
        """
        matches = self.categorize(text, max_categories=1)
        return matches[0] if matches else None

    def categorize_multiple(
        self,
        texts: List[str],
    ) -> Dict[str, List[CategoryMatch]]:
        """
        Categorize multiple texts.

        Args:
            texts: List of texts to analyze

        Returns:
            Dict mapping text to matches
        """
        return {text: self.categorize(text) for text in texts}

    def get_category_info(self, slug: str) -> Optional[Dict]:
        """
        Get category information by slug.

        Args:
            slug: Category slug

        Returns:
            Category data dict or None
        """
        return self.categories.get(slug)

    def list_categories(self) -> List[Dict]:
        """
        List all available categories.

        Returns:
            List of category info dicts
        """
        return [
            {
                "slug": slug,
                "name": data["name"],
                "icon": data.get("icon", "📁"),
                "keywords_count": len(data.get("keywords", [])),
            }
            for slug, data in self.categories.items()
        ]


# Global instance
_categorizer: Optional[AutoCategorizer] = None


def get_categorizer() -> AutoCategorizer:
    """Get global categorizer instance."""
    global _categorizer
    if _categorizer is None:
        _categorizer = AutoCategorizer()
    return _categorizer


# Convenience functions
def categorize_text(text: str) -> List[CategoryMatch]:
    """Categorize text using global categorizer."""
    return get_categorizer().categorize(text)


def get_best_category(text: str) -> Optional[CategoryMatch]:
    """Get best category for text."""
    return get_categorizer().get_best_category(text)
