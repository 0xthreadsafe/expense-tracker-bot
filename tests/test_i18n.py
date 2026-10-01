from __future__ import annotations

from datetime import datetime

import pytest

from expensebot.i18n import (
    FALLBACK_LOCALE,
    LOCALES,
    LocaleProfile,
    category_name,
    format_amount,
    format_month,
    format_number,
    get_profile,
    register_locale,
    resolve_locale,
    t,
)
from expensebot.repository import DEFAULT_CATEGORIES


@pytest.mark.parametrize("code", sorted(LOCALES))
def test_catalogs_have_identical_keys(code: str) -> None:
    """Drift between catalogs is the usual way a translation silently rots."""
    reference = set(LOCALES[FALLBACK_LOCALE].messages)
    actual = set(LOCALES[code].messages)

    assert (
        actual == reference
    ), f"locale {code}: missing {sorted(reference - actual)}, extra {sorted(actual - reference)}"


@pytest.mark.parametrize("code", sorted(LOCALES))
def test_every_builtin_category_is_translated(code: str) -> None:
    for slug, _emoji in DEFAULT_CATEGORIES:
        assert category_name(slug, code) != f"category.{slug}"


@pytest.mark.parametrize("code", sorted(LOCALES))
def test_placeholders_match_the_reference_catalog(code: str) -> None:
    """A translation that drops a placeholder would render an incomplete message."""
    import re

    pattern = re.compile(r"\{(\w+)\}")
    reference = LOCALES[FALLBACK_LOCALE].messages
    for key, template in LOCALES[code].messages.items():
        assert set(pattern.findall(template)) == set(pattern.findall(reference[key])), key


def test_missing_key_falls_back_per_key_not_per_language() -> None:
    register_locale(LocaleProfile(code="xx", native_name="Test", messages={"welcome": "hi"}))
    try:
        assert t("welcome", "xx") == "hi"
        # Not translated in xx, so English is used rather than failing.
        assert t("cancelled", "xx") == LOCALES["en"].messages["cancelled"]
    finally:
        del LOCALES["xx"]


def test_unknown_key_returns_the_key_instead_of_raising() -> None:
    assert t("no_such_key", "en") == "no_such_key"


def test_bad_placeholder_does_not_raise() -> None:
    # A handler passing the wrong kwargs must degrade, never crash.
    assert t("expense_saved", "en", wrong="x")


def test_persian_uses_persian_digits_and_separators() -> None:
    assert format_number(1234567, "fa") == "۱٬۲۳۴٬۵۶۷"
    assert format_number(1234567, "en") == "1,234,567"
    assert format_number(12.5, "fa", decimals=2) == "۱۲٫۵۰"


def test_amounts_are_bidi_isolated_only_where_needed() -> None:
    fa = format_amount(25000, "fa", currency="IRR")
    en = format_amount(25000, "en", currency="IRR")

    assert fa.startswith("⁨") and fa.endswith("⁩")
    # Isolates would be noise in a left-to-right language.
    assert "⁨" not in en


def test_amount_hides_decimals_when_they_carry_nothing() -> None:
    assert format_amount(25000, "en") == "25,000"
    assert format_amount(25000.5, "en") == "25,000.50"


def test_resolve_locale_from_telegram_language_code() -> None:
    assert resolve_locale("fa-IR") == "fa"
    assert resolve_locale("en-GB") == "en"
    assert resolve_locale("de-DE") == "en"  # unsupported falls back
    assert resolve_locale(None) == "en"
    assert resolve_locale("de-DE", default="fa") == "fa"


def test_month_is_gregorian_in_every_locale() -> None:
    when = datetime(2026, 3, 1)
    assert format_month(when, "en") == "March 2026"
    # Persian renders Gregorian month names by project decision; only the
    # numerals are localized.
    assert "۲۰۲۶" in format_month(when, "fa")


def test_a_new_locale_is_a_drop_in() -> None:
    """The guarantee that adding a language later costs no handler changes.

    Registering a profile is the only step; everything else keeps working.
    """
    register_locale(
        LocaleProfile(
            code="qq",
            native_name="Qqish",
            messages={"expense_saved": "QQ {amount} / {category}"},
            rtl=True,
            digits="⁰¹²³⁴⁵⁶⁷⁸⁹",
            thousands_separator=" ",
        )
    )
    try:
        assert "qq" in LOCALES
        profile = get_profile("qq")
        assert profile.rtl is True
        # Its own catalog is used where present, English fills the rest, and
        # the profile's digit set and separator drive formatting.
        # Digits anywhere in the rendered message adopt the locale's digit set,
        # which is what makes "page 1 of 3" localize without caller effort.
        assert t("expense_saved", "qq", amount="1", category="c") == "QQ ¹ / c"
        assert t("btn_cancel", "qq") == "Cancel"
        assert format_number(1234, "qq") == "¹ ²³⁴"
    finally:
        del LOCALES["qq"]
