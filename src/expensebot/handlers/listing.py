"""Browsing and editing recorded expenses."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from expensebot import repository as repo
from expensebot.handlers.common import with_user
from expensebot.i18n import format_amount, format_date, t
from expensebot.models import Expense, User
from expensebot.parsing import ParseError, parse_expense
from expensebot.periods import parse_month, to_local

logger = logging.getLogger(__name__)

PAGE_SIZE = 5

PAGE_PREFIX = "lp:"
DETAIL_PREFIX = "lx:"
DELETE_PREFIX = "lxd:"
RECAT_PREFIX = "lxc:"
SETCAT_PREFIX = "lxs:"
EDIT_AMOUNT_PREFIX = "lxa:"
EDIT_NOTE_PREFIX = "lxn:"

ASK_AMOUNT, ASK_NOTE = range(2)
MONTH_KEY = "list_month"


def _row(index: int, expense: Expense, user: User) -> str:
    note = t("expense_note_suffix", user.locale, note=expense.note) if expense.note else ""
    category = expense.category.label() if expense.category else t("uncategorized", user.locale)
    return t(
        "list_row",
        user.locale,
        index=index,
        date=format_date(to_local(expense.spent_at, user.timezone), user.locale),
        category=category,
        amount=format_amount(expense.amount, user.locale, currency=user.currency),
        note=note,
    )


def _page_keyboard(
    expenses: Sequence[Expense], page: int, total: int, locale: str
) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                f"{page * PAGE_SIZE + i + 1}", callback_data=f"{DETAIL_PREFIX}{e.id}"
            )
            for i, e in enumerate(expenses)
        ]
    ]
    nav = []
    if page > 0:
        nav.append(
            InlineKeyboardButton(t("btn_prev", locale), callback_data=f"{PAGE_PREFIX}{page - 1}")
        )
    if (page + 1) * PAGE_SIZE < total:
        nav.append(
            InlineKeyboardButton(t("btn_next", locale), callback_data=f"{PAGE_PREFIX}{page + 1}")
        )
    if nav:
        rows.append(nav)
    return InlineKeyboardMarkup(rows)


async def _render_page(
    session: AsyncSession, user: User, context: ContextTypes.DEFAULT_TYPE, page: int
) -> tuple[str, InlineKeyboardMarkup | None]:
    assert context.user_data is not None
    period = context.user_data.get(MONTH_KEY)
    start = period.start if period else None
    end = period.end if period else None

    total = await repo.count_expenses(session, user.id, start=start, end=end)
    if total == 0:
        return t("list_empty", user.locale), None

    # Clamp so that deleting the last item on a page cannot strand the user.
    pages = max(1, -(-total // PAGE_SIZE))
    page = max(0, min(page, pages - 1))

    expenses = await repo.list_expenses(
        session, user.id, start=start, end=end, limit=PAGE_SIZE, offset=page * PAGE_SIZE
    )
    header = t("list_title", user.locale, page=page + 1, pages=pages)
    body = "\n".join(_row(page * PAGE_SIZE + i + 1, e, user) for i, e in enumerate(expenses))
    return f"{header}\n{body}", _page_keyboard(expenses, page, total, user.locale)


@with_user
async def list_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE, session: AsyncSession, user: User
) -> None:
    assert update.message is not None and context.user_data is not None

    argument = (update.message.text or "").partition(" ")[2].strip()
    # An argument such as 2026-03 narrows the listing to that month.
    context.user_data[MONTH_KEY] = parse_month(argument, user.timezone) if argument else None

    text, keyboard = await _render_page(session, user, context, 0)
    await update.message.reply_text(text, reply_markup=keyboard, parse_mode=ParseMode.HTML)


@with_user
async def change_page(
    update: Update, context: ContextTypes.DEFAULT_TYPE, session: AsyncSession, user: User
) -> None:
    query = update.callback_query
    assert query is not None and query.data is not None
    await query.answer()

    page = int(query.data.removeprefix(PAGE_PREFIX))
    text, keyboard = await _render_page(session, user, context, page)
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode=ParseMode.HTML)


def _detail_keyboard(expense: Expense, locale: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    t("btn_edit_amount", locale), callback_data=f"{EDIT_AMOUNT_PREFIX}{expense.id}"
                ),
                InlineKeyboardButton(
                    t("btn_edit_note", locale), callback_data=f"{EDIT_NOTE_PREFIX}{expense.id}"
                ),
            ],
            [
                InlineKeyboardButton(
                    t("btn_change_category", locale), callback_data=f"{RECAT_PREFIX}{expense.id}"
                ),
                InlineKeyboardButton(
                    t("btn_delete", locale), callback_data=f"{DELETE_PREFIX}{expense.id}"
                ),
            ],
            [InlineKeyboardButton(t("btn_back", locale), callback_data=f"{PAGE_PREFIX}0")],
        ]
    )


def _detail_text(expense: Expense, user: User) -> str:
    return t(
        "expense_detail",
        user.locale,
        amount=format_amount(expense.amount, user.locale, currency=user.currency),
        category=expense.category.label() if expense.category else t("uncategorized", user.locale),
        date=format_date(to_local(expense.spent_at, user.timezone), user.locale),
        note=expense.note or t("none", user.locale),
    )


@with_user
async def show_detail(
    update: Update, context: ContextTypes.DEFAULT_TYPE, session: AsyncSession, user: User
) -> None:
    query = update.callback_query
    assert query is not None and query.data is not None
    await query.answer()

    expense = await repo.get_expense(session, user.id, int(query.data.removeprefix(DETAIL_PREFIX)))
    if expense is None:
        await query.edit_message_text(t("not_found", user.locale))
        return

    await query.edit_message_text(
        _detail_text(expense, user),
        reply_markup=_detail_keyboard(expense, user.locale),
        parse_mode=ParseMode.HTML,
    )


@with_user
async def delete(
    update: Update, context: ContextTypes.DEFAULT_TYPE, session: AsyncSession, user: User
) -> None:
    query = update.callback_query
    assert query is not None and query.data is not None
    await query.answer()

    expense = await repo.get_expense(session, user.id, int(query.data.removeprefix(DELETE_PREFIX)))
    if expense is None:
        await query.edit_message_text(t("not_found", user.locale))
        return

    await repo.delete_expense(session, expense)
    text, keyboard = await _render_page(session, user, context, 0)
    await query.edit_message_text(
        f"{t('expense_deleted', user.locale)}\n\n{text}",
        reply_markup=keyboard,
        parse_mode=ParseMode.HTML,
    )


@with_user
async def choose_category(
    update: Update, context: ContextTypes.DEFAULT_TYPE, session: AsyncSession, user: User
) -> None:
    query = update.callback_query
    assert query is not None and query.data is not None
    await query.answer()

    expense_id = int(query.data.removeprefix(RECAT_PREFIX))
    categories = await repo.list_categories(session, user.id)
    rows = [
        [
            InlineKeyboardButton(c.label(), callback_data=f"{SETCAT_PREFIX}{expense_id}:{c.id}")
            for c in categories[i : i + 2]
        ]
        for i in range(0, len(categories), 2)
    ]
    await query.edit_message_text(
        t("btn_change_category", user.locale), reply_markup=InlineKeyboardMarkup(rows)
    )


@with_user
async def set_category(
    update: Update, context: ContextTypes.DEFAULT_TYPE, session: AsyncSession, user: User
) -> None:
    query = update.callback_query
    assert query is not None and query.data is not None
    await query.answer()

    expense_id, _, category_id = query.data.removeprefix(SETCAT_PREFIX).partition(":")
    expense = await repo.get_expense(session, user.id, int(expense_id))
    category = await repo.get_category(session, user.id, int(category_id))
    if expense is None or category is None:
        await query.edit_message_text(t("not_found", user.locale))
        return

    expense.category_id = category.id
    await session.flush()
    await session.refresh(expense)
    await query.edit_message_text(
        f"{t('expense_updated', user.locale)}\n\n{_detail_text(expense, user)}",
        reply_markup=_detail_keyboard(expense, user.locale),
        parse_mode=ParseMode.HTML,
    )


# ------------------------------------------------------------------ edit flows


@with_user
async def _ask_amount(
    update: Update, context: ContextTypes.DEFAULT_TYPE, session: AsyncSession, user: User
) -> None:
    query = update.callback_query
    assert query is not None and query.data is not None and context.user_data is not None
    await query.answer()
    context.user_data["edit_expense_id"] = int(query.data.removeprefix(EDIT_AMOUNT_PREFIX))
    await query.edit_message_text(t("ask_new_amount", user.locale))


@with_user
async def _ask_note(
    update: Update, context: ContextTypes.DEFAULT_TYPE, session: AsyncSession, user: User
) -> None:
    query = update.callback_query
    assert query is not None and query.data is not None and context.user_data is not None
    await query.answer()
    context.user_data["edit_expense_id"] = int(query.data.removeprefix(EDIT_NOTE_PREFIX))
    await query.edit_message_text(t("ask_new_note", user.locale))


async def _enter_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await _ask_amount(update, context)
    return ASK_AMOUNT


async def _enter_note(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await _ask_note(update, context)
    return ASK_NOTE


@with_user
async def _save_amount(
    update: Update, context: ContextTypes.DEFAULT_TYPE, session: AsyncSession, user: User
) -> None:
    assert update.message is not None and context.user_data is not None
    expense_id = context.user_data.pop("edit_expense_id", None)
    expense = (
        await repo.get_expense(session, user.id, expense_id) if expense_id is not None else None
    )
    if expense is None:
        await update.message.reply_text(t("not_found", user.locale))
        return

    try:
        # Reuse the entry parser so edits accept the same formats as new entries.
        parsed = parse_expense(update.message.text or "")
    except ParseError as exc:
        await update.message.reply_text(
            t(exc.key, user.locale, **exc.params), parse_mode=ParseMode.HTML
        )
        return

    expense.amount = Decimal(parsed.amount)
    await session.flush()
    await update.message.reply_text(
        f"{t('expense_updated', user.locale)}\n\n{_detail_text(expense, user)}",
        parse_mode=ParseMode.HTML,
    )


@with_user
async def _save_note(
    update: Update, context: ContextTypes.DEFAULT_TYPE, session: AsyncSession, user: User
) -> None:
    assert update.message is not None and context.user_data is not None
    expense_id = context.user_data.pop("edit_expense_id", None)
    expense = (
        await repo.get_expense(session, user.id, expense_id) if expense_id is not None else None
    )
    if expense is None:
        await update.message.reply_text(t("not_found", user.locale))
        return

    expense.note = (update.message.text or "").strip()[:256] or None
    await session.flush()
    await update.message.reply_text(
        f"{t('expense_updated', user.locale)}\n\n{_detail_text(expense, user)}",
        parse_mode=ParseMode.HTML,
    )


async def _finish_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await _save_amount(update, context)
    return ConversationHandler.END


async def _finish_note(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await _save_note(update, context)
    return ConversationHandler.END


async def _cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    assert context.user_data is not None
    context.user_data.pop("edit_expense_id", None)
    return ConversationHandler.END


def register(application: Application) -> None:  # type: ignore[type-arg]
    text_only = filters.TEXT & ~filters.COMMAND

    application.add_handler(CommandHandler("list", list_command))
    application.add_handler(CallbackQueryHandler(change_page, pattern=f"^{PAGE_PREFIX}"))
    application.add_handler(CallbackQueryHandler(show_detail, pattern=f"^{DETAIL_PREFIX}"))
    application.add_handler(CallbackQueryHandler(delete, pattern=f"^{DELETE_PREFIX}"))
    application.add_handler(CallbackQueryHandler(choose_category, pattern=f"^{RECAT_PREFIX}"))
    application.add_handler(CallbackQueryHandler(set_category, pattern=f"^{SETCAT_PREFIX}"))
    application.add_handler(
        ConversationHandler(
            entry_points=[
                CallbackQueryHandler(_enter_amount, pattern=f"^{EDIT_AMOUNT_PREFIX}"),
                CallbackQueryHandler(_enter_note, pattern=f"^{EDIT_NOTE_PREFIX}"),
            ],
            states={
                ASK_AMOUNT: [MessageHandler(text_only, _finish_amount)],
                ASK_NOTE: [MessageHandler(text_only, _finish_note)],
            },
            fallbacks=[CommandHandler("cancel", _cancel)],
            # per_message stays False because these conversations are entered
            # from a button but answered with ordinary messages; tracking per
            # message would prevent the message steps from matching. The
            # library's warning about this combination does not apply here.
        )
    )
