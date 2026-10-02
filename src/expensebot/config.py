"""Application configuration.

Settings are read once from the environment (and a local ``.env`` file) and
validated eagerly, so a misconfigured deployment fails at startup with a precise
error instead of surfacing as a confusing ``None`` deep inside a handler.
"""

from __future__ import annotations

import hashlib
from enum import StrEnum
from functools import lru_cache
from typing import Literal

from pydantic import AliasChoices, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class BotMode(StrEnum):
    """How the bot receives updates from Telegram."""

    POLLING = "polling"
    WEBHOOK = "webhook"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    bot_token: SecretStr = Field(
        min_length=20,
        description="Token issued by @BotFather. Rejected when empty or obviously truncated.",
    )
    bot_mode: BotMode = BotMode.POLLING

    # Only consulted when bot_mode is WEBHOOK.
    webhook_url: str | None = None
    # Platforms such as Render and Heroku inject the port to bind as PORT, so it
    # is accepted as an alias and the service needs no platform-specific config.
    webhook_port: int = Field(
        default=8080,
        ge=1,
        le=65535,
        validation_alias=AliasChoices("WEBHOOK_PORT", "PORT"),
    )
    webhook_listen: str = "0.0.0.0"
    webhook_secret: SecretStr | None = None

    database_url: str = "sqlite+aiosqlite:///./data/expenses.db"

    timezone: str = "Asia/Tehran"
    currency: str = Field(default="IRR", min_length=3, max_length=3)
    default_locale: str = "en"

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    @model_validator(mode="after")
    def _check_webhook_config(self) -> Settings:
        """Webhook mode is unusable without a public URL, so reject it early."""
        if self.bot_mode is BotMode.WEBHOOK and not self.webhook_url:
            raise ValueError("WEBHOOK_URL is required when BOT_MODE=webhook")
        return self

    @property
    def webhook_path(self) -> str:
        """Unguessable URL path Telegram posts updates to.

        The path is a hash rather than the token itself: hosts, proxies and CDNs
        record request paths in plain text, so a token placed in the URL ends up
        in logs outside this application's control. Authenticity is established
        by the secret_token header instead, which is never logged; the hash only
        keeps the endpoint from being discovered by chance.
        """
        material = (
            self.webhook_secret.get_secret_value()
            if self.webhook_secret
            else self.bot_token.get_secret_value()
        )
        return hashlib.sha256(material.encode()).hexdigest()[:32]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings, parsed on first use."""
    return Settings()  # type: ignore[call-arg]  # values come from the environment
