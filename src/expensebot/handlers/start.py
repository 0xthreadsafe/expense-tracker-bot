"""Onboarding, help, settings and language selection."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

from expensebot import repository as repo
from expensebot.handlers.common import with_user
from expensebot.i18n import LOCALES, format_time, t
from expensebot.models import User

LANGUAGE_PREFIX = "lang:"


def language_keyboard() -> InlineKeyboardMarkup:
    """One button per registered locale.

    Built from the registry so that registering a new language adds its button
    automatically.
    """
    buttons = [
        InlineKeyboardButton(profile.native_name, callback_data=f"{LANGUAGE_PREFIX}{code}")
        for code, profile in sorted(LOCALES.items())
    ]
    rows = [buttons[i : i + 2] for i in range(0, len(buttons), 2)]
    return InlineKeyboardMarkup(rows)


@with_user
async def start(
    update: Update, context: ContextTypes.DEFAULT_TYPE, session: AsyncSession, user: User
) -> None:
    assert update.message is not None
    await update.message.reply_text(t("welcome", user.locale), parse_mode=ParseMode.HTML)


@with_user
async def help_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE, session: AsyncSession, user: User
) -> None:
    assert update.message is not None
    await update.message.reply_text(t("help", user.locale), parse_mode=ParseMode.HTML)


@with_user
async def settings_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE, session: AsyncSession, user: User
) -> None:
    assert update.message is not None
    locale = user.locale

    if user.reminder_enabled:
        time_text = format_time(f"{user.reminder_hour:02d}:{user.reminder_minute:02d}", locale)
        reminder_line = t("settings_reminder_on", locale, value=time_text)
    else:
        reminder_line = t("settings_reminder_off", locale)

    lines = [
        t("settings_title", locale),
        t("settings_language", locale, value=LOCALES[locale].native_name),
        t("settings_timezone", locale, value=user.timezone),
        t("settings_currency", locale, value=user.currency),
        reminder_line,
    ]
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


@with_user
async def language_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE, session: AsyncSession, user: User
) -> None:
    assert update.message is not None
    await update.message.reply_text(
        t("choose_language", user.locale), reply_markup=language_keyboard()
    )


@with_user
async def language_chosen(
    update: Update, context: ContextTypes.DEFAULT_TYPE, session: AsyncSession, user: User
) -> None:
    query = update.callback_query
    assert query is not None and query.data is not None
    await query.answer()

    code = query.data.removeprefix(LANGUAGE_PREFIX)
    if code not in LOCALES:
        return

    await repo.set_locale(session, user, code)
    # Confirmation is rendered in the newly chosen language, which doubles as
    # immediate feedback that the switch took effect.
    await query.edit_message_text(t("language_changed", code))


def register(application: Application) -> None:  # type: ignore[type-arg]
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("settings", settings_command))
    application.add_handler(CommandHandler("language", language_command))
    application.add_handler(CallbackQueryHandler(language_chosen, pattern=f"^{LANGUAGE_PREFIX}"))
