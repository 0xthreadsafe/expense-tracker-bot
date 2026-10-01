"""Global error handling and flood protection."""

from __future__ import annotations

import logging
import time

from telegram import Update
from telegram.error import Forbidden, NetworkError, TelegramError
from telegram.ext import Application, ContextTypes

from expensebot import repository as repo
from expensebot.db import session_scope
from expensebot.i18n import t

logger = logging.getLogger(__name__)

# Expensive commands are limited per user; cheap ones are left alone so that
# normal use is never throttled.
RATE_LIMIT_SECONDS = 5.0
# Above this many tracked keys, expired ones are swept. Without a bound the
# table would grow for the lifetime of the process, one entry per user.
_SWEEP_THRESHOLD = 10_000

_last_call: dict[tuple[int, str], float] = {}


def rate_limited(user_id: int, command: str) -> bool:
    """Return True when this user called ``command`` too recently."""
    now = time.monotonic()
    key = (user_id, command)

    previous = _last_call.get(key)
    if previous is not None and now - previous < RATE_LIMIT_SECONDS:
        return True

    if len(_last_call) > _SWEEP_THRESHOLD:
        expired = [k for k, seen in _last_call.items() if now - seen > RATE_LIMIT_SECONDS]
        for k in expired:
            del _last_call[k]

    _last_call[key] = now
    return False


def reset_rate_limits() -> None:
    """Clear the table. Used by tests to keep cases independent."""
    _last_call.clear()


async def _user_locale(user_id: int) -> str:
    try:
        async with session_scope() as session:
            user = await repo.get_user(session, user_id)
            return user.locale if user else "en"
    except Exception:  # pragma: no cover - the database may be the thing that failed
        return "en"


async def handle_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log the failure in full and tell the user something neutral.

    Exception text can contain tokens, identifiers or query fragments, so it is
    never echoed back to the user.
    """
    error = context.error

    # A user blocking the bot, or a transient network blip, is expected
    # operation rather than a defect: log it quietly and do not try to reply.
    if isinstance(error, Forbidden | NetworkError):
        logger.info("Transport error: %s", error)
        return

    logger.exception("Unhandled error while processing update", exc_info=error)

    if not isinstance(update, Update) or update.effective_chat is None:
        return

    user_id = update.effective_user.id if update.effective_user else 0
    try:
        await context.bot.send_message(
            update.effective_chat.id, t("error_generic", await _user_locale(user_id))
        )
    except TelegramError:
        # Failing to deliver the apology must not raise a second error.
        logger.debug("Could not deliver the error message", exc_info=True)


def register(application: Application) -> None:  # type: ignore[type-arg]
    application.add_error_handler(handle_error)
