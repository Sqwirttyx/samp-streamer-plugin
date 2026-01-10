"""
Spintax parser and generator for message variation.

Spintax syntax:
    {option1|option2|option3} - randomly selects one option

Example:
    "{Привет|Здравствуйте}! {Меня зовут|Я} {Анна|Мария}."
    -> "Привет! Я Мария."
    -> "Здравствуйте! Меня зовут Анна."

Supports nested spintax:
    "{Привет|{Добрый день|Здравствуйте}}"
"""

import random
import re
from typing import List, Optional, Tuple


class SpintaxError(Exception):
    """Spintax parsing error."""
    pass


class SpintaxParser:
    """
    Parser and generator for spintax text variations.

    Usage:
        parser = SpintaxParser()
        unique_text = parser.spin("{Привет|Здравствуйте}!")
        variations = parser.preview("{A|B|C}", count=3)
        total = parser.count_variations("{A|B} {X|Y|Z}")  # 2 * 3 = 6
    """

    # Pattern to find spintax blocks: {...|...|...}
    SPINTAX_PATTERN = re.compile(r'\{([^{}]+)\}')

    def __init__(self, seed: Optional[int] = None):
        """
        Initialize parser.

        Args:
            seed: Random seed for reproducible results (testing)
        """
        if seed is not None:
            random.seed(seed)

    def spin(self, text: str) -> str:
        """
        Generate a single unique variation of spintax text.

        Args:
            text: Text with spintax syntax

        Returns:
            Text with randomly selected variations
        """
        if not text:
            return text

        # Process from innermost to outermost (for nested spintax)
        result = text
        max_iterations = 100  # Prevent infinite loops
        iteration = 0

        while self.SPINTAX_PATTERN.search(result) and iteration < max_iterations:
            result = self.SPINTAX_PATTERN.sub(self._replace_match, result)
            iteration += 1

        return result

    def _replace_match(self, match: re.Match) -> str:
        """Replace a single spintax match with random option."""
        options = match.group(1).split('|')
        return random.choice(options)

    def preview(self, text: str, count: int = 5) -> List[str]:
        """
        Generate multiple preview variations.

        Args:
            text: Text with spintax syntax
            count: Number of variations to generate

        Returns:
            List of unique variations (may be less than count if few options)
        """
        if not text or not self.has_spintax(text):
            return [text] if text else []

        variations = set()
        max_attempts = count * 10  # Prevent infinite loops
        attempts = 0

        while len(variations) < count and attempts < max_attempts:
            variation = self.spin(text)
            variations.add(variation)
            attempts += 1

        return list(variations)[:count]

    def count_variations(self, text: str) -> int:
        """
        Calculate total number of possible variations.

        Args:
            text: Text with spintax syntax

        Returns:
            Total number of unique combinations
        """
        if not text:
            return 0

        # Find all spintax blocks (non-nested first approximation)
        # For nested, this gives approximate count
        blocks = self.SPINTAX_PATTERN.findall(text)

        if not blocks:
            return 1

        total = 1
        for block in blocks:
            options = block.split('|')
            total *= len(options)

        return total

    def has_spintax(self, text: str) -> bool:
        """
        Check if text contains spintax syntax.

        Args:
            text: Text to check

        Returns:
            True if spintax found
        """
        if not text:
            return False
        return bool(self.SPINTAX_PATTERN.search(text))

    def validate(self, text: str) -> Tuple[bool, Optional[str]]:
        """
        Validate spintax syntax.

        Args:
            text: Text to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not text:
            return True, None

        # Check for balanced braces
        open_count = text.count('{')
        close_count = text.count('}')

        if open_count != close_count:
            return False, f"Несбалансированные скобки: {{ = {open_count}, }} = {close_count}"

        # Check for empty options
        if '||' in text or '{|' in text or '|}' in text:
            return False, "Пустые варианты запрещены (||, {|, |})"

        # Check for empty blocks
        if '{}' in text:
            return False, "Пустые блоки {} запрещены"

        # Try to parse
        try:
            self.spin(text)
            return True, None
        except Exception as e:
            return False, f"Ошибка парсинга: {str(e)}"

    def extract_options(self, text: str) -> List[List[str]]:
        """
        Extract all spintax option groups.

        Args:
            text: Text with spintax

        Returns:
            List of option lists for each spintax block
        """
        blocks = self.SPINTAX_PATTERN.findall(text)
        return [block.split('|') for block in blocks]

    def get_stats(self, text: str) -> dict:
        """
        Get statistics about spintax text.

        Args:
            text: Text with spintax

        Returns:
            Stats dictionary
        """
        blocks = self.SPINTAX_PATTERN.findall(text)
        options_per_block = [len(block.split('|')) for block in blocks]

        return {
            "has_spintax": bool(blocks),
            "blocks_count": len(blocks),
            "total_variations": self.count_variations(text),
            "options_per_block": options_per_block,
            "min_options": min(options_per_block) if options_per_block else 0,
            "max_options": max(options_per_block) if options_per_block else 0,
        }


# Global parser instance
_parser: Optional[SpintaxParser] = None


def get_spintax_parser() -> SpintaxParser:
    """Get global spintax parser instance."""
    global _parser
    if _parser is None:
        _parser = SpintaxParser()
    return _parser


# Convenience functions
def spin(text: str) -> str:
    """Generate a single spintax variation."""
    return get_spintax_parser().spin(text)


def spin_preview(text: str, count: int = 5) -> List[str]:
    """Generate preview variations."""
    return get_spintax_parser().preview(text, count)


def spin_validate(text: str) -> Tuple[bool, Optional[str]]:
    """Validate spintax syntax."""
    return get_spintax_parser().validate(text)


def spin_count(text: str) -> int:
    """Count possible variations."""
    return get_spintax_parser().count_variations(text)


def has_spintax(text: str) -> bool:
    """Check if text has spintax."""
    return get_spintax_parser().has_spintax(text)
