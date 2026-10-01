"""Construction and startup of the Telegram application.

``build_application`` performs no I/O, which keeps it usable from tests; ``run``
is the only function that talks to Telegram.
"""

from __future__ import annotations

import logging

from telegram.ext import Application, ApplicationBuilder

from expensebot.config import BotMode, Settings, get_settings
from expensebot.db import dispose_db, init_db

logger = logging.getLogger(__name__)


async def _on_startup(application: Application) -> None:
    """Work that must happen after the event loop exists.

    The engine is created here rather than at import time because an async
    engine binds to the running loop.
    """
    from expensebot.handlers.reminders import restore_reminders
    from expensebot.menu import setup_commands

    settings = get_settings()
    await init_db(settings.database_url)
    # Scheduled jobs live only in memory, so they are rebuilt from the database.
    await restore_reminders(application)
    await setup_commands(application.bot)
    logger.info("Bot started as @%s", application.bot.username)


async def _on_shutdown(application: Application) -> None:
    """Release resources acquired in :func:`_on_startup`."""
    await dispose_db()
    logger.info("Bot stopped")


def build_application(settings: Settings | None = None) -> Application:
    """Create the application with handlers registered but nothing running."""
    settings = settings or get_settings()

    application = (
        ApplicationBuilder()
        .token(settings.bot_token.get_secret_value())
        .post_init(_on_startup)
        .post_shutdown(_on_shutdown)
        .build()
    )

    register_handlers(application)
    return application


def register_handlers(application: Application) -> None:
    """Attach every handler to the application.

    Registration is delegated to each feature module so that the bot's surface
    area can be read off this one function. Order matters: the free-form
    message handler in ``expenses`` must be registered last so that it cannot
    shadow a more specific handler.
    """
    from expensebot.handlers import (
        categories,
        errors,
        expenses,
        export,
        listing,
        reminders,
        reports,
        start,
    )

    start.register(application)
    categories.register(application)
    listing.register(application)
    reports.register(application)
    export.register(application)
    reminders.register(application)
    # Registered last: its catch-all text handler would otherwise shadow the
    # conversation steps belonging to the modules above.
    expenses.register(application)
    errors.register(application)


def run() -> None:
    """Start the bot and block until it is interrupted."""
    settings = get_settings()
    application = build_application(settings)

    if settings.bot_mode is BotMode.WEBHOOK:
        assert settings.webhook_url is not None  # guaranteed by Settings validation
        logger.info("Listening for webhooks on port %s", settings.webhook_port)
        application.run_webhook(
            listen=settings.webhook_listen,
            port=settings.webhook_port,
            url_path=settings.webhook_path,
            webhook_url=f"{settings.webhook_url.rstrip('/')}/{settings.webhook_path}",
            secret_token=(
                settings.webhook_secret.get_secret_value() if settings.webhook_secret else None
            ),
        )
    else:
        logger.info("Polling for updates")
        # drop_pending_updates avoids replaying a backlog accumulated while down.
        application.run_polling(drop_pending_updates=True)
