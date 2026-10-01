from __future__ import annotations

from decimal import Decimal

import pytest

from expensebot.parsing import MAX_NOTE_LENGTH, ParseError, parse_expense


@pytest.mark.parametrize(
    ("text", "amount", "note"),
    [
        # plain western input
        ("25000 lunch", "25000", "lunch"),
        ("25000", "25000", None),
        ("  25000   lunch  with  spaces ", "25000", "lunch with spaces"),
        # grouping separators
        ("1,250 taxi", "1250", "taxi"),
        ("1 250 taxi", "1250", "taxi"),
        # decimals
        ("12.50 coffee", "12.5", "coffee"),
        # multipliers
        ("25k lunch", "25000", "lunch"),
        ("25K lunch", "25000", "lunch"),
        ("2m rent", "2000000", "rent"),
        # persian digits
        ("۲۵۰۰۰ ناهار", "25000", "ناهار"),
        ("۱٬۲۵۰ تاکسی", "1250", "تاکسی"),
        ("۱۲٫۵۰ قهوه", "12.5", "قهوه"),
        # persian multiplier words
        ("۲۵ هزار ناهار", "25000", "ناهار"),
        ("۲ میلیون اجاره", "2000000", "اجاره"),
        # arabic-indic digits
        ("٢٥٠٠٠ غداء", "25000", "غداء"),
        # note before the amount
        ("lunch 25000", "25000", "lunch"),
    ],
)
def test_parses_common_forms(text: str, amount: str, note: str | None) -> None:
    result = parse_expense(text)

    assert result.amount == Decimal(amount)
    assert result.note == note


def test_multiplier_letter_is_not_stolen_from_a_note() -> None:
    """'milk' must not be read as the 'm' million multiplier."""
    result = parse_expense("25 milk")

    assert result.amount == Decimal("25")
    assert result.note == "milk"


@pytest.mark.parametrize("text", ["", "   ", "lunch", "no numbers here", "...", "ناهار"])
def test_rejects_input_without_an_amount(text: str) -> None:
    with pytest.raises(ParseError) as excinfo:
        parse_expense(text)

    assert excinfo.value.key == "parse_failed"


def test_rejects_zero() -> None:
    with pytest.raises(ParseError) as excinfo:
        parse_expense("0 lunch")

    assert excinfo.value.key == "amount_must_be_positive"


def test_rejects_implausibly_large_amounts() -> None:
    with pytest.raises(ParseError) as excinfo:
        parse_expense("9999999999999999 typo")

    assert excinfo.value.key == "amount_too_large"


def test_rejects_an_overlong_note() -> None:
    with pytest.raises(ParseError) as excinfo:
        parse_expense("100 " + "x" * (MAX_NOTE_LENGTH + 1))

    assert excinfo.value.key == "note_too_long"
    assert excinfo.value.params == {"limit": MAX_NOTE_LENGTH}


def test_errors_carry_a_translation_key_not_english_text() -> None:
    """Errors must be renderable in the user's language by the handler."""
    with pytest.raises(ParseError) as excinfo:
        parse_expense("nothing")

    from expensebot.i18n import t

    assert t(excinfo.value.key, "fa") != excinfo.value.key


def test_decimal_precision_is_exact() -> None:
    # The reason amounts are Decimal rather than float.
    total = parse_expense("0.1").amount + parse_expense("0.2").amount
    assert total == Decimal("0.3")
