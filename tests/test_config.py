from __future__ import annotations

import pytest

from expensebot.config import BotMode, Settings

TOKEN = "123456789:AAFakeTokenUsedOnlyInTests"


def test_port_is_accepted_as_an_alias(monkeypatch: pytest.MonkeyPatch) -> None:
    """Render and Heroku inject PORT; binding elsewhere fails their health check."""
    monkeypatch.setenv("PORT", "10000")
    monkeypatch.delenv("WEBHOOK_PORT", raising=False)

    assert Settings(_env_file=None, bot_token=TOKEN).webhook_port == 10000


def test_explicit_webhook_port_wins_over_port(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PORT", "10000")
    monkeypatch.setenv("WEBHOOK_PORT", "9999")

    assert Settings(_env_file=None, bot_token=TOKEN).webhook_port == 9999


def test_webhook_mode_requires_a_url() -> None:
    with pytest.raises(ValueError, match="WEBHOOK_URL"):
        Settings(_env_file=None, bot_token=TOKEN, bot_mode=BotMode.WEBHOOK)
