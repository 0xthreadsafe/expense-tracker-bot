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


def test_webhook_path_never_contains_the_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """Hosts and proxies log request paths, so a token in the URL leaks."""
    monkeypatch.setenv("WEBHOOK_SECRET", "a-secret")
    config = settings()

    assert config.bot_token.get_secret_value() not in config.webhook_path
    assert "a-secret" not in config.webhook_path
    # Unguessable, and stable so the registered URL does not drift per restart.
    assert len(config.webhook_path) == 32
    assert config.webhook_path == settings().webhook_path
