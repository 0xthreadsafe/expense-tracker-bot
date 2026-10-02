from __future__ import annotations

import pytest

from expensebot.config import Settings


def settings() -> Settings:
    # Values come from the environment, which mypy cannot see.
    return Settings()  # type: ignore[call-arg]


# BOT_TOKEN and friends come from the autouse fixture in conftest, and
# environment variables take precedence over the dotenv file, so these build
# settings from the environment rather than passing private constructor
# arguments.


def test_port_is_accepted_as_an_alias(monkeypatch: pytest.MonkeyPatch) -> None:
    """Render and Heroku inject PORT; binding elsewhere fails their health check."""
    monkeypatch.setenv("PORT", "10000")
    monkeypatch.delenv("WEBHOOK_PORT", raising=False)

    assert settings().webhook_port == 10000


def test_explicit_webhook_port_wins_over_port(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PORT", "10000")
    monkeypatch.setenv("WEBHOOK_PORT", "9999")

    assert settings().webhook_port == 9999


def test_webhook_mode_requires_a_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BOT_MODE", "webhook")
    monkeypatch.delenv("WEBHOOK_URL", raising=False)

    with pytest.raises(ValueError, match="WEBHOOK_URL"):
        settings()
