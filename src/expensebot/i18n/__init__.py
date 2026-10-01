"""Localization.

A locale is described entirely by a :class:`LocaleProfile`: its message
catalog, writing direction, digit set and number formatting. Application code
never branches on a locale code, so adding a language means registering one
more profile and translating one catalog, with no change to any handler.

Dates and chart labels are deliberately Gregorian and English in every locale;
see ``docs/architecture.md`` and the deferred calendar work.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from expensebot.i18n.catalogs import en as en_catalog
from expensebot.i18n.catalogs import fa as fa_catalog

logger = logging.getLogger(__name__)

FALLBACK_LOCALE = "en"

# Unicode isolates. Wrapping a run of digits or Latin text in FIRST STRONG
# ISOLATE ... POP DIRECTIONAL ISOLATE stops it from being reordered by the bidi
# algorithm when it sits inside right-to-left text, which is what otherwise
# turns "25,000 IRR" into "IRR 25,000" or worse inside a Persian sentence.
_FSI = "⁨"
_PDI = "⁩"

WESTERN_DIGITS = "0123456789"
PERSIAN_DIGITS = "۰۱۲۳۴۵۶۷۸۹"


@dataclass(frozen=True)
class LocaleProfile:
    """Everything that varies between languages, in one place."""

    code: str
    native_name: str
    messages: dict[str, str]
    rtl: bool = False
    digits: str = WESTERN_DIGITS
    thousands_separator: str = ","
    decimal_separator: str = "."
    # Maps a Telegram ``language_code`` prefix onto this locale.
    language_codes: tuple[str, ...] = field(default_factory=tuple)

    def localize_digits(self, text: str) -> str:
        if self.digits == WESTERN_DIGITS:
            return text
        return text.translate(str.maketrans(WESTERN_DIGITS, self.digits))

    def isolate(self, text: str) -> str:
        """Protect a left-to-right run embedded in right-to-left text."""
        return f"{_FSI}{text}{_PDI}" if self.rtl else text


LOCALES: dict[str, LocaleProfile] = {
    "en": LocaleProfile(
        code="en",
        native_name="English",
        messages=en_catalog.MESSAGES,
        language_codes=("en",),
    ),
    "fa": LocaleProfile(
        code="fa",
        native_name="فارسی",
        messages=fa_catalog.MESSAGES,
        rtl=True,
        digits=PERSIAN_DIGITS,
        thousands_separator="٬",
        decimal_separator="٫",
        language_codes=("fa", "pes", "prs"),
    ),
}


def register_locale(profile: LocaleProfile) -> None:
    """Add a locale at runtime. Used by tests and by plugins."""
    LOCALES[profile.code] = profile


def get_profile(locale: str | None) -> LocaleProfile:
    return LOCALES.get(locale or "", LOCALES[FALLBACK_LOCALE])


def resolve_locale(language_code: str | None, default: str = FALLBACK_LOCALE) -> str:
    """Pick a locale from Telegram's ``language_code`` (e.g. ``fa-IR``)."""
    if language_code:
        prefix = language_code.lower().split("-")[0]
        for profile in LOCALES.values():
            if prefix in profile.language_codes:
                return profile.code
    return default if default in LOCALES else FALLBACK_LOCALE


def t(key: str, locale: str | None = None, **kwargs: object) -> str:
    """Translate ``key``, falling back per key rather than per language.

    A locale that is only partially translated therefore degrades to English
    for the missing keys instead of failing.
    """
    profile = get_profile(locale)
    template = profile.messages.get(key)
    if template is None:
        template = LOCALES[FALLBACK_LOCALE].messages.get(key)
    if template is None:
        logger.warning("Missing translation key: %s", key)
        return key

    try:
        text = template.format(**kwargs) if kwargs else template
    except (KeyError, IndexError):
        # A malformed placeholder must never take down a handler.
        logger.warning("Bad placeholders for key %s in locale %s", key, profile.code)
        return template
    return profile.localize_digits(text) if profile.digits != WESTERN_DIGITS else text


def format_number(value: Decimal | float, locale: str | None = None, *, decimals: int = 0) -> str:
    """Group thousands and localize digits, without any currency label."""
    profile = get_profile(locale)
    formatted = f"{float(value):,.{decimals}f}"
    formatted = formatted.replace(",", "\x00").replace(".", profile.decimal_separator)
    formatted = formatted.replace("\x00", profile.thousands_separator)
    return profile.localize_digits(formatted)


def format_amount(value: Decimal | float, locale: str | None = None, *, currency: str = "") -> str:
    """Format money for display, isolated so it survives right-to-left text."""
    profile = get_profile(locale)
    # Whole amounts are the common case for the currencies this targets; only
    # show decimals when they carry information.
    decimals = 0 if float(value) == int(float(value)) else 2
    text = format_number(value, locale, decimals=decimals)
    if currency:
        text = f"{text} {currency}"
    return profile.isolate(text)


def format_date(value: datetime, locale: str | None = None) -> str:
    profile = get_profile(locale)
    return profile.isolate(profile.localize_digits(value.strftime("%Y-%m-%d")))


def format_time(value: datetime | str, locale: str | None = None) -> str:
    profile = get_profile(locale)
    text = value if isinstance(value, str) else value.strftime("%H:%M")
    return profile.isolate(profile.localize_digits(text))


def format_month(value: datetime, locale: str | None = None) -> str:
    """Month heading, e.g. 'March 2026'. Gregorian in every locale."""
    profile = get_profile(locale)
    name = t(f"month.{value.month}", locale)
    year = profile.isolate(profile.localize_digits(str(value.year)))
    return f"{name} {year}"


def category_name(slug: str, locale: str | None = None) -> str:
    """Localized name for a built-in category slug."""
    return t(f"category.{slug}", locale)
