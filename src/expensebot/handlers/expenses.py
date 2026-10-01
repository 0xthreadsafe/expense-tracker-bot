"""Recording expenses: /add, free-form entry, category choice and undo."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from expensebot import repository as repo
from expensebot.handlers.common import with_user
from expensebot.i18n import format_amount, t
from expensebot.models import Category, User
from expensebot.parsing import ParseError, parse_expense

logger = logging.getLogger(__name__)

CATEGORY_PREFIX = "pick:"
UNDO_PREFIX = "undo:"
PENDING_KEY = "pending_expense"

CATEGORY_COLUMNS = 2


def category_keyboard(categories: Sequence[Category]) -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(c.label(), callback_data=f"{CATEGORY_PREFIX}{c.id}")
        for c in categories
    ]
    rows = [buttons[i : i + CATEGORY_COLUMNS] for i in range(0, len(buttons), CATEGORY_COLUMNS)]
    return InlineKeyboardMarkup(rows)


async def _begin_expense(
    update: Update, context: ContextTypes.DEFAULT_TYPE, session: AsyncSession, user: User, text: str
) -> None:
    """Parse input and ask which category it belongs to."""
    assert update.message is not None

    try:
        parsed = parse_expense(text)
    except ParseError as exc:
        await update.message.reply_text(
            t(exc.key, user.locale, **exc.params), parse_mode=ParseMode.HTML
        )
        return

    # Held in per-user state only until a category is chosen; nothing is written
    # to the database until the user commits by tapping a button.
    assert context.user_data is not None
    context.user_data[PENDING_KEY] = {
        "amount": str(parsed.amount),
        "note": parsed.note,
    }

    categories = await repo.list_categories(session, user.id)
    amount_text = format_amount(parsed.amount, user.locale, currency=user.currency)
    note_text = t("expense_note_suffix", user.locale, note=parsed.note) if parsed.note else ""

    await update.message.reply_text(
        t("ask_category", user.locale, amount=amount_text, note=note_text),
        reply_markup=category_keyboard(categories),
        parse_mode=ParseMode.HTML,
    )


@with_user
async def add_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE, session: AsyncSession, user: User
) -> None:
    assert update.message is not None and update.message.text is not None
    argument = update.message.text.partition(" ")[2]
    await _begin_expense(update, context, session, user, argument)


@with_user
async def freeform(
    update: Update, context: ContextTypes.DEFAULT_TYPE, session: AsyncSession, user: User
) -> None:
    """Treat a bare message as an expense, which is the fastest way to log one."""
    assert update.message is not None and update.message.text is not None
    await _begin_expense(update, context, session, user, update.message.text)


@with_user
async def category_chosen(
    update: Update, context: ContextTypes.DEFAULT_TYPE, session: AsyncSession, user: User
) -> None:
    query = update.callback_query
    assert query is not None and query.data is not None
    await query.answer()

    assert context.user_data is not None
    pending = context.user_data.pop(PENDING_KEY, None)
    if pending is None:
        # The message outlived its state, typically after a restart.
        await query.edit_message_text(t("not_found", user.locale))
        return

    category_id = int(query.data.removeprefix(CATEGORY_PREFIX))
    category = await repo.get_category(session, user.id, category_id)
    if category is None:
        await query.edit_message_text(t("not_found", user.locale))
        return

    expense = await repo.add_expense(
        session,
        user.id,
        amount=Decimal(pending["amount"]),
        category_id=category.id,
        note=pending["note"],
        spent_at=datetime.now(UTC),
    )

    undo = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    t("btn_undo", user.locale), callback_data=f"{UNDO_PREFIX}{expense.id}"
                )
            ]
        ]
    )
    await query.edit_message_text(
        t(
            "expense_saved",
            user.locale,
            amount=format_amount(expense.amount, user.locale, currency=user.currency),
            category=category.label(),
        ),
        reply_markup=undo,
        parse_mode=ParseMode.HTML,
    )


@with_user
async def undo(
    update: Update, context: ContextTypes.DEFAULT_TYPE, session: AsyncSession, user: User
) -> None:
    query = update.callback_query
    assert query is not None and query.data is not None
    await query.answer()

    expense_id = int(query.data.removeprefix(UNDO_PREFIX))
    expense = await repo.get_expense(session, user.id, expense_id)
    if expense is None:
        await query.edit_message_text(t("not_found", user.locale))
        return

    await repo.delete_expense(session, expense)
    await query.edit_message_text(t("expense_deleted", user.locale))


def register(application: Application) -> None:  # type: ignore[type-arg]
    application.add_handler(CommandHandler("add", add_command))
    application.add_handler(CallbackQueryHandler(category_chosen, pattern=f"^{CATEGORY_PREFIX}"))
    application.add_handler(CallbackQueryHandler(undo, pattern=f"^{UNDO_PREFIX}"))
    # Registered last so that it never shadows a command or another handler.
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, freeform))
