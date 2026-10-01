"""CSV export."""

from __future__ import annotations

import csv
import io
import logging

from sqlalchemy.ext.asyncio import AsyncSession
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from expensebot import repository as repo
from expensebot.handlers.common import with_user
from expensebot.handlers.errors import rate_limited
from expensebot.i18n import t
from expensebot.models import User
from expensebot.periods import parse_month, to_local

logger = logging.getLogger(__name__)

EXPORT_PAGE = 1000


def build_csv(rows: list[dict[str, str]], headers: list[str]) -> bytes:
    """Serialise to CSV encoded for Excel.

    Excel assumes the system codepage unless a UTF-8 byte order mark is
    present, which is what otherwise turns Persian notes into mojibake when the
    file is opened by double-clicking it.
    """
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=headers, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8-sig")


@with_user
async def export_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE, session: AsyncSession, user: User
) -> None:
    assert update.message is not None
    if rate_limited(user.id, "export"):
        await update.message.reply_text(t("rate_limited", user.locale))
        return

    argument = (update.message.text or "").partition(" ")[2].strip()
    period = parse_month(argument, user.timezone) if argument else None

    expenses = await repo.list_expenses(
        session,
        user.id,
        start=period.start if period else None,
        end=period.end if period else None,
        limit=EXPORT_PAGE,
    )
    if not expenses:
        await update.message.reply_text(t("export_empty", user.locale))
        return

    locale = user.locale
    headers = [
        t(f"csv_{name}", locale) for name in ("date", "amount", "currency", "category", "note")
    ]
    rows = [
        dict(
            zip(
                headers,
                [
                    # ISO 8601 regardless of locale: a date column has to stay
                    # machine-readable for a spreadsheet to sort or filter it.
                    to_local(e.spent_at, user.timezone).strftime("%Y-%m-%d"),
                    f"{e.amount:f}",
                    user.currency,
                    e.category.name if e.category else t("uncategorized", locale),
                    e.note or "",
                ],
                strict=True,
            )
        )
        for e in reversed(expenses)
    ]

    payload = build_csv(rows, headers)
    await update.message.reply_document(
        document=io.BytesIO(payload),
        filename=f"expenses-{period.label:%Y-%m}.csv" if period else "expenses.csv",
        caption=t("export_caption", locale, count=len(rows)),
    )


def register(application: Application) -> None:  # type: ignore[type-arg]
    application.add_handler(CommandHandler("export", export_command))
