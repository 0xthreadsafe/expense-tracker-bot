"""Shared handler plumbing.

Every handler needs the same three things: a database session, the current
user, and that user's locale. The :func:`with_user` decorator supplies them so
individual handlers contain feature logic only.
"""

from __future__ import annotations

import functools
import logging
from collections.abc import Awaitable, Callable, Coroutine
from typing import Any, ParamSpec, TypeVar

from sqlalchemy.ext.asyncio import AsyncSession
from telegram import Update
from telegram.ext import ContextTypes

from expensebot import repository as repo
from expensebot.config import get_settings
from expensebot.db import session_scope
from expensebot.i18n import category_name, resolve_locale
from expensebot.models import User

logger = logging.getLogger(__name__)

P = ParamSpec("P")
R = TypeVar("R")

Handler = Callable[[Update, ContextTypes.DEFAULT_TYPE, AsyncSession, User], Awaitable[None]]


def _builtin_category_names(locale: str) -> dict[str, str]:
    """Localized names for the seeded categories.

    Built here rather than in the repository so that persistence stays
    independent of the translation layer.
    """
    return {slug: category_name(slug, locale) for slug, _ in repo.DEFAULT_CATEGORIES}


async def get_or_create_user(session: AsyncSession, update: Update) -> User:
    """Return the current user, creating and seeding them on first contact.

    Any update can be a user's first, not only ``/start``, so registration is
    handled here rather than in the onboarding handler alone.
    """
    tg_user = update.effective_user
    assert tg_user is not None  # handlers are only registered for user updates

    user = await repo.get_user(session, tg_user.id)
    if user is not None:
        return user

    settings = get_settings()
    locale = resolve_locale(tg_user.language_code, default=settings.default_locale)
    logger.info("Registering user %s with locale %s", tg_user.id, locale)
    return await repo.create_user(
        session,
        tg_user.id,
        locale=locale,
        timezone=settings.timezone,
        currency=settings.currency,
        category_names=_builtin_category_names(locale),
    )


def with_user(
    func: Handler,
) -> Callable[[Update, ContextTypes.DEFAULT_TYPE], Coroutine[Any, Any, None]]:
    """Open a transaction and resolve the user before running a handler."""

    @functools.wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        async with session_scope() as session:
            user = await get_or_create_user(session, update)
            await func(update, context, session, user)

    return wrapper
