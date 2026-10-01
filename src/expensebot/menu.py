"""The command menu Telegram shows beside the input box.

Registered by the application at startup rather than configured by hand in
@BotFather, so the menu cannot drift away from the handlers that exist. Telegram
stores one list per language and serves whichever matches the viewer's own app
language, which is independent of the locale the user chose in this bot.
"""

from __future__ import annotations

import logging

from telegram import Bot, BotCommand
from telegram.error import TelegramError

from expensebot.i18n import LOCALES
from expensebot.i18n import t as translate

logger = logging.getLogger(__name__)

# Ordered by how often a command is reached for, since Telegram shows the list
# in the order it is given.
COMMANDS: tuple[tuple[str, str], ...] = (
    ("add", "cmd_add"),
    ("list", "cmd_list"),
    ("report", "cmd_report"),
    ("categories", "cmd_categories"),
    ("export", "cmd_export"),
    ("remind", "cmd_remind"),
    ("language", "cmd_language"),
    ("settings", "cmd_settings"),
    ("help", "cmd_help"),
)


def commands_for(locale: str) -> list[BotCommand]:
    """Build the menu for one locale from the message catalogs."""
    return [BotCommand(name, translate(key, locale)) for name, key in COMMANDS]


async def setup_commands(bot: Bot) -> None:
    """Publish the menu once per registered language.

    Failure is logged rather than raised: an unreachable Telegram at startup
    should not stop the bot from coming up and serving updates.
    """
    try:
        # The default list is what users whose app language has no entry see.
        await bot.set_my_commands(commands_for("en"))
        for code in LOCALES:
            if code == "en":
                continue
            await bot.set_my_commands(commands_for(code), language_code=code)
    except TelegramError:
        logger.warning("Could not publish the command menu", exc_info=True)
        return
    logger.info("Published command menu for %d language(s)", len(LOCALES))
