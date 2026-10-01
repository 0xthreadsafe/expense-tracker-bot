"""Monthly summary with a category breakdown and chart."""

from __future__ import annotations

import asyncio
import logging
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession
from telegram import Update
from telegram.constants import ChatAction, ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes

from expensebot import repository as repo
from expensebot.charts import render_breakdown
from expensebot.handlers.common import with_user
from expensebot.handlers.errors import rate_limited
from expensebot.i18n import format_amount, format_month, format_number, t
from expensebot.models import User
from expensebot.periods import Period, month_period, parse_month

logger = logging.getLogger(__name__)


def _comparison_line(current: Decimal, previous: Decimal, previous_label: str, locale: str) -> str:
    if previous == 0:
        return t("report_no_previous", locale, month=previous_label)

    change = (current - previous) / previous * 100
    percent = format_number(abs(change), locale, decimals=0)
    if abs(change) < 1:
        return t("report_vs_previous_same", locale, month=previous_label)
    key = "report_vs_previous_up" if change > 0 else "report_vs_previous_down"
    return t(key, locale, percent=percent, month=previous_label)


@with_user
async def report_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE, session: AsyncSession, user: User
) -> None:
    assert update.message is not None
    if rate_limited(user.id, "report"):
        await update.message.reply_text(t("rate_limited", user.locale))
        return

    argument = (update.message.text or "").partition(" ")[2].strip()

    period: Period
    if argument.lower() == "last":
        period = month_period(user.timezone, offset=-1)
    else:
        parsed = parse_month(argument, user.timezone) if argument else None
        period = parsed or month_period(user.timezone)

    month_label = format_month(period.label, user.locale)
    totals = await repo.totals_by_category(session, user.id, start=period.start, end=period.end)

    if not totals:
        await update.message.reply_text(
            t("report_empty", user.locale, month=month_label), parse_mode=ParseMode.HTML
        )
        return

    total = sum((c.total for c in totals), Decimal(0))
    lines = [
        t("report_title", user.locale, month=month_label),
        t(
            "report_total",
            user.locale,
            amount=format_amount(total, user.locale, currency=user.currency),
        ),
        "",
    ]
    for entry in totals:
        share = entry.total / total * 100 if total else Decimal(0)
        name = entry.name if entry.slug != "uncategorized" else t("uncategorized", user.locale)
        lines.append(
            t(
                "report_row",
                user.locale,
                emoji=entry.emoji,
                name=name,
                amount=format_amount(entry.total, user.locale, currency=user.currency),
                percent=format_number(share, user.locale, decimals=0),
            )
        )

    # Comparison is only meaningful against the month immediately before the one
    # being reported, which is not necessarily last month.
    previous = month_period(user.timezone, reference=period.label, offset=-1)
    previous_total = await repo.total_for_period(
        session, user.id, start=previous.start, end=previous.end
    )
    lines += [
        "",
        _comparison_line(
            total, previous_total, format_month(previous.label, user.locale), user.locale
        ),
    ]

    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)

    # Rendering takes long enough to look like the bot has stalled, so the
    # client is told to show "typing" first. The action lapses on its own once
    # the photo arrives.
    assert update.effective_chat is not None
    await context.bot.send_chat_action(update.effective_chat.id, ChatAction.UPLOAD_PHOTO)

    # Chart rendering is CPU-bound; running it inline would stall every other
    # user's updates for its duration.
    png = await asyncio.to_thread(
        render_breakdown,
        totals,
        title=format_month(period.label, "en"),
        currency=user.currency,
    )
    await update.message.reply_photo(png)


def register(application: Application) -> None:  # type: ignore[type-arg]
    application.add_handler(CommandHandler("report", report_command))
