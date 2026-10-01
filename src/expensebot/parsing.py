"""Parsing free-form expense input.

Users type amounts the way they speak them, so this accepts Persian and Western
digits, thousands separators, decimal commas, and the shorthand multipliers that
are common in both languages. It is pure logic with no Telegram or database
dependency, which makes it exhaustively testable.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from expensebot.i18n import PERSIAN_DIGITS, WESTERN_DIGITS

# Guards against a typo becoming a permanent outlier that distorts every report.
MAX_AMOUNT = Decimal("999999999999")
MAX_NOTE_LENGTH = 256

ARABIC_DIGITS = "٠١٢٣٤٥٦٧٨٩"

_DIGIT_TRANSLATION = str.maketrans(
    PERSIAN_DIGITS + ARABIC_DIGITS,
    WESTERN_DIGITS + WESTERN_DIGITS,
)

# Written as "<multiplier spelling>: factor". Persian speakers routinely write
# "۲۵ هزار" and English speakers "25k" for the same quantity.
MULTIPLIERS: dict[str, int] = {
    "k": 1_000,
    "m": 1_000_000,
    "هزار": 1_000,
    "تا": 1,
    "میلیون": 1_000_000,
    "ملیون": 1_000_000,
}

# Separators used for grouping in either language.
_GROUPING = ",٬ ‌٬"


class ParseError(Exception):
    """Raised when a message contains no usable amount.

    Carries a message key rather than text so the caller can render it in the
    user's own language.
    """

    def __init__(self, key: str, **params: object) -> None:
        super().__init__(key)
        self.key = key
        self.params = params


@dataclass(frozen=True)
class ParsedExpense:
    amount: Decimal
    note: str | None


def normalize_digits(text: str) -> str:
    """Convert Persian and Arabic-Indic digits to Western ones."""
    return text.translate(_DIGIT_TRANSLATION)


def _strip_grouping(number: str) -> str:
    for ch in _GROUPING:
        number = number.replace(ch, "")
    # Persian decimal separator maps onto the Western point.
    return number.replace("٫", ".")


def parse_expense(text: str) -> ParsedExpense:
    """Extract an amount and an optional note from a free-form message.

    Accepts forms such as ``25000 lunch``, ``25k lunch``, ``۲۵ هزار ناهار``,
    ``1,250.50`` and ``۱٬۲۵۰٫۵۰``.
    """
    cleaned = normalize_digits(text).strip()
    if not cleaned:
        raise ParseError("parse_failed")

    # The amount is the first number in the message; everything else is a note.
    match = re.search(rf"(\d[\d{re.escape(_GROUPING)}]*(?:[.٫]\d+)?)", cleaned)
    if match is None:
        raise ParseError("parse_failed")

    try:
        amount = Decimal(_strip_grouping(match.group(1)))
    except InvalidOperation as exc:
        raise ParseError("parse_failed") from exc

    remainder = (cleaned[: match.start()] + " " + cleaned[match.end() :]).strip()

    # A multiplier only counts when it immediately follows the number, so that
    # a note such as "milk" is never mistaken for "m".
    tail = cleaned[match.end() :].lstrip()
    for word, factor in sorted(MULTIPLIERS.items(), key=lambda kv: -len(kv[0])):
        if tail.lower().startswith(word) and (
            len(tail) == len(word) or not tail[len(word)].isalnum()
        ):
            amount *= factor
            remainder = (cleaned[: match.start()] + " " + tail[len(word) :]).strip()
            break

    if amount <= 0:
        raise ParseError("amount_must_be_positive")
    if amount > MAX_AMOUNT:
        raise ParseError("amount_too_large")

    note = " ".join(remainder.split()) or None
    if note is not None and len(note) > MAX_NOTE_LENGTH:
        raise ParseError("note_too_long", limit=MAX_NOTE_LENGTH)

    return ParsedExpense(amount=amount.normalize(), note=note)
