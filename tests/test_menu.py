from __future__ import annotations

from typing import Any, cast

import pytest

from expensebot.i18n import LOCALES
from expensebot.menu import COMMANDS, commands_for, setup_commands
from tests.fakes import FakeBot

pytestmark = pytest.mark.usefixtures("app_db")


@pytest.mark.parametrize("code", sorted(LOCALES))
def test_every_command_has_a_description_in_every_language(code: str) -> None:
    """An untranslated description would show the raw key in the menu."""
    for command in commands_for(code):
        assert command.description, command.command
        assert not command.description.startswith("cmd_"), command.command


@pytest.mark.parametrize("code", sorted(LOCALES))
def test_descriptions_fit_telegrams_limit(code: str) -> None:
    for command in commands_for(code):
        assert 1 <= len(command.description) <= 256
        assert 1 <= len(command.command) <= 32


def test_persian_menu_is_actually_persian() -> None:
    english = {c.description for c in commands_for("en")}
    persian = {c.description for c in commands_for("fa")}

    assert not english & persian


def test_every_registered_command_is_a_real_handler() -> None:
    """Guards against the menu advertising a command that was never wired up."""
    from telegram.ext import CommandHandler

    from expensebot.app import build_application
    from expensebot.config import get_settings

    application = build_application(get_settings())
    wired: set[str] = set()
    for group in application.handlers.values():
        for handler in group:
            if isinstance(handler, CommandHandler):
                wired.update(handler.commands)

    advertised = {name for name, _ in COMMANDS}
    assert advertised <= wired, f"menu advertises unhandled commands: {advertised - wired}"


async def test_setup_publishes_one_list_per_language() -> None:
    bot = FakeBot()

    await setup_commands(cast(Any, bot))

    languages = [language for language, _ in bot.commands]
    # One default list, plus one per non-default locale.
    assert languages[0] is None
    assert set(languages[1:]) == set(LOCALES) - {"en"}


async def test_setup_survives_telegram_being_unreachable() -> None:
    """A failure here must not stop the bot from starting."""
    from telegram.error import TelegramError

    class BrokenBot(FakeBot):
        async def set_my_commands(self, commands: list[Any], **kwargs: Any) -> None:
            raise TelegramError("unreachable")

    await setup_commands(cast(Any, BrokenBot()))  # must not raise
