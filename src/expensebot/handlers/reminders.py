"""Opt-in daily reminder to log spending.

Jobs live in the scheduler, which is memory-resident, so the stored schedule is
the source of truth and jobs are rebuilt from the database at startup.
Otherwise every restart would silently cancel everyone's reminders.
"""

from __future__ import annotations

import logging
import re
from datetime import time

from sqlalchemy.ext.asyncio import AsyncSession
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes

from expensebot import repository as repo
from expensebot.db import session_scope
from expensebot.handlers.common import with_user
from expensebot.i18n import format_time, t
from expensebot.models import User
from expensebot.periods import day_period, get_zone

logger = logging.getLogger(__name__)

_TIME_PATTERN = re.compile(r"^(\d{1,2})[:.\s](\d{2})$")


def job_name(user_id: int) -> str:
    return f"reminder:{user_id}"


def _parse_time(value: str) -> tuple[int, int] | None:
    from expensebot.parsing import normalize_digits

    match = _TIME_PATTERN.match(normalize_digits(value).strip())
    if match is None:
        return None
    hour, minute = int(match.group(1)), int(match.group(2))
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None
    return hour, minute


async def send_reminder(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Nudge a user who has logged nothing today."""
    job = context.job
    assert job is not None and job.chat_id is not None
    user_id = int(job.chat_id)

    async with session_scope() as session:
        user = await repo.get_user(session, user_id)
        if user is None or not user.reminder_enabled:
            return
        today = day_period(user.timezone)
        if await repo.has_expense_on_day(session, user.id, start=today.start, end=today.end):
            return
        locale = user.locale

    await context.bot.send_message(user_id, t("reminder_nudge", locale))


def schedule_reminder(application: Application, user: User) -> None:  # type: ignore[type-arg]
    """Install or replace a user's daily job."""
    queue = application.job_queue
    if queue is None:  # job-queue extra not installed
        logger.warning("JobQueue unavailable; reminders disabled")
        return

    for existing in queue.get_jobs_by_name(job_name(user.id)):
        existing.schedule_removal()

    if not user.reminder_enabled:
        return

    assert user.reminder_hour is not None and user.reminder_minute is not None
    queue.run_daily(
        send_reminder,
        # Scheduling in the user's own zone keeps the reminder at the same wall
        # clock time year round, including across daylight saving changes.
        time=time(user.reminder_hour, user.reminder_minute, tzinfo=get_zone(user.timezone)),
        chat_id=user.id,
        name=job_name(user.id),
    )


async def restore_reminders(application: Application) -> None:  # type: ignore[type-arg]
    """Rebuild every stored reminder after a restart."""
    async with session_scope() as session:
        users = await repo.users_with_reminders(session)
        for user in users:
            schedule_reminder(application, user)
    if users:
        logger.info("Restored %d reminder job(s)", len(users))


@with_user
async def remind_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE, session: AsyncSession, user: User
) -> None:
    assert update.message is not None
    argument = (update.message.text or "").partition(" ")[2].strip()

    if not argument:
        await update.message.reply_text(t("reminder_usage", user.locale), parse_mode=ParseMode.HTML)
        return

    if argument.lower() in {"off", "خاموش", "0"}:
        await repo.set_reminder(session, user, None, None)
        schedule_reminder(context.application, user)
        await update.message.reply_text(t("reminder_cleared", user.locale))
        return

    parsed = _parse_time(argument)
    if parsed is None:
        await update.message.reply_text(
            t("reminder_bad_time", user.locale), parse_mode=ParseMode.HTML
        )
        return

    hour, minute = parsed
    await repo.set_reminder(session, user, hour, minute)
    schedule_reminder(context.application, user)
    await update.message.reply_text(
        t("reminder_set", user.locale, time=format_time(f"{hour:02d}:{minute:02d}", user.locale))
    )


def register(application: Application) -> None:  # type: ignore[type-arg]
    application.add_handler(CommandHandler("remind", remind_command))
