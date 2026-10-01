"""Managing categories: list, create, rename, remove.

Creating and renaming are multi-step, so they use a ConversationHandler: the
bot asks a question, remembers which step the user is on, and routes the next
message to the matching state rather than to the generic text handler.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Sequence

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
from expensebot.i18n import t
from expensebot.models import Category, User

logger = logging.getLogger(__name__)

ASK_NAME, ASK_EMOJI, ASK_RENAME = range(3)

NEW_CATEGORY = "cat:new"
DELETE_PREFIX = "cat:del:"
RENAME_PREFIX = "cat:ren:"

MAX_CATEGORIES = 30
MAX_CATEGORY_NAME = 64

_SLUG_SAFE = re.compile(r"[^a-z0-9]+")


def make_slug(name: str, existing: set[str]) -> str:
    """Derive a stable, locale-independent identifier for a category.

    Non-Latin names cannot produce a meaningful Latin slug, so those fall back
    to a numbered identifier. The slug is what labels charts, so it must never
    change once assigned.
    """
    base = _SLUG_SAFE.sub("-", name.lower()).strip("-")
    if not base:
        base = "custom"
    slug = base[:32]
    counter = 2
    while slug in existing:
        suffix = f"-{counter}"
        slug = base[: 32 - len(suffix)] + suffix
        counter += 1
    return slug


def _categories_keyboard(categories: Sequence[Category], locale: str) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(c.label(), callback_data=f"{RENAME_PREFIX}{c.id}"),
            InlineKeyboardButton("🗑", callback_data=f"{DELETE_PREFIX}{c.id}"),
        ]
        for c in categories
    ]
    rows.append([InlineKeyboardButton(t("btn_add_category", locale), callback_data=NEW_CATEGORY)])
    return InlineKeyboardMarkup(rows)


@with_user
async def categories_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE, session: AsyncSession, user: User
) -> None:
    assert update.message is not None
    categories = await repo.list_categories(session, user.id)
    await update.message.reply_text(
        t("categories_title", user.locale),
        reply_markup=_categories_keyboard(categories, user.locale),
        parse_mode=ParseMode.HTML,
    )


@with_user
async def delete_category(
    update: Update, context: ContextTypes.DEFAULT_TYPE, session: AsyncSession, user: User
) -> None:
    query = update.callback_query
    assert query is not None and query.data is not None
    await query.answer()

    category = await repo.get_category(
        session, user.id, int(query.data.removeprefix(DELETE_PREFIX))
    )
    if category is None:
        await query.edit_message_text(t("not_found", user.locale))
        return

    was_builtin = category.is_builtin
    await repo.delete_category(session, category)

    remaining = await repo.list_categories(session, user.id)
    await query.edit_message_text(
        t("category_builtin_hidden" if was_builtin else "category_deleted", user.locale),
        reply_markup=_categories_keyboard(remaining, user.locale),
    )


# ----------------------------------------------------------------- create flow


@with_user
async def start_create(
    update: Update, context: ContextTypes.DEFAULT_TYPE, session: AsyncSession, user: User
) -> None:
    query = update.callback_query
    assert query is not None and context.user_data is not None
    await query.answer()

    existing = await repo.list_categories(session, user.id, include_hidden=True)
    if len(existing) >= MAX_CATEGORIES:
        await query.edit_message_text(t("category_limit", user.locale, limit=MAX_CATEGORIES))
        return

    await query.edit_message_text(t("ask_category_name", user.locale))


async def _enter_create(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await start_create(update, context)
    return ASK_NAME


@with_user
async def receive_name(
    update: Update, context: ContextTypes.DEFAULT_TYPE, session: AsyncSession, user: User
) -> None:
    assert update.message is not None and update.message.text is not None
    assert context.user_data is not None

    name = update.message.text.strip()[:MAX_CATEGORY_NAME]
    existing = await repo.list_categories(session, user.id, include_hidden=True)
    if any(c.name.lower() == name.lower() for c in existing):
        await update.message.reply_text(t("category_exists", user.locale))
        return

    context.user_data["new_category_name"] = name
    await update.message.reply_text(t("ask_category_emoji", user.locale))


async def _receive_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await receive_name(update, context)
    assert context.user_data is not None
    # Stay on this step when the name was rejected.
    return ASK_EMOJI if "new_category_name" in context.user_data else ASK_NAME


@with_user
async def receive_emoji(
    update: Update, context: ContextTypes.DEFAULT_TYPE, session: AsyncSession, user: User
) -> None:
    assert update.message is not None and context.user_data is not None
    name = context.user_data.pop("new_category_name", None)
    if name is None:
        return

    text = (update.message.text or "").strip()
    emoji = "•" if text.startswith("/skip") or not text else text[:8]

    existing = {c.slug for c in await repo.list_categories(session, user.id, include_hidden=True)}
    category = await repo.create_category(
        session, user.id, slug=make_slug(name, existing), name=name, emoji=emoji
    )
    await update.message.reply_text(t("category_added", user.locale, category=category.label()))


async def _receive_emoji(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await receive_emoji(update, context)
    return ConversationHandler.END


# ----------------------------------------------------------------- rename flow


@with_user
async def start_rename(
    update: Update, context: ContextTypes.DEFAULT_TYPE, session: AsyncSession, user: User
) -> None:
    query = update.callback_query
    assert query is not None and query.data is not None and context.user_data is not None
    await query.answer()

    context.user_data["rename_category_id"] = int(query.data.removeprefix(RENAME_PREFIX))
    await query.edit_message_text(t("ask_category_name", user.locale))


async def _enter_rename(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await start_rename(update, context)
    return ASK_RENAME


@with_user
async def receive_rename(
    update: Update, context: ContextTypes.DEFAULT_TYPE, session: AsyncSession, user: User
) -> None:
    assert update.message is not None and update.message.text is not None
    assert context.user_data is not None

    category_id = context.user_data.pop("rename_category_id", None)
    if category_id is None:
        return

    category = await repo.get_category(session, user.id, category_id)
    if category is None:
        await update.message.reply_text(t("not_found", user.locale))
        return

    await repo.rename_category(session, category, update.message.text.strip()[:MAX_CATEGORY_NAME])
    await update.message.reply_text(t("category_renamed", user.locale, category=category.label()))


async def _receive_rename(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await receive_rename(update, context)
    return ConversationHandler.END


@with_user
async def cancel(
    update: Update, context: ContextTypes.DEFAULT_TYPE, session: AsyncSession, user: User
) -> None:
    assert update.message is not None and context.user_data is not None
    context.user_data.pop("new_category_name", None)
    context.user_data.pop("rename_category_id", None)
    await update.message.reply_text(t("cancelled", user.locale))


async def _cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await cancel(update, context)
    return ConversationHandler.END


def register(application: Application) -> None:  # type: ignore[type-arg]
    text_only = filters.TEXT & ~filters.COMMAND

    application.add_handler(CommandHandler("categories", categories_command))
    application.add_handler(
        ConversationHandler(
            entry_points=[
                CallbackQueryHandler(_enter_create, pattern=f"^{NEW_CATEGORY}$"),
                CallbackQueryHandler(_enter_rename, pattern=f"^{RENAME_PREFIX}"),
            ],
            states={
                ASK_NAME: [MessageHandler(text_only, _receive_name)],
                ASK_EMOJI: [
                    CommandHandler("skip", _receive_emoji),
                    MessageHandler(text_only, _receive_emoji),
                ],
                ASK_RENAME: [MessageHandler(text_only, _receive_rename)],
            },
            fallbacks=[CommandHandler("cancel", _cancel)],
            # per_message stays False because these conversations are entered
            # from a button but answered with ordinary messages; tracking per
            # message would prevent the message steps from matching. The
            # library's warning about this combination does not apply here.
            # Without this the conversation would capture the free-form expense
            # handler's messages for every user in a group chat.
            per_chat=True,
            per_user=True,
        )
    )
    application.add_handler(CallbackQueryHandler(delete_category, pattern=f"^{DELETE_PREFIX}"))
