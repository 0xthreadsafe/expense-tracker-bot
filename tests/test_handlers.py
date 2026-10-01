"""Handler tests.

These exercise the real handlers against fake Telegram objects and a throwaway
database, so they cover the wiring that unit tests of pure functions cannot.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, cast

import pytest

from expensebot import repository as repo
from expensebot.db import session_scope
from expensebot.handlers import expenses, export, listing, reports, start
from expensebot.i18n import LOCALES
from tests.fakes import FakeContext, command, tap, text_of

pytestmark = pytest.mark.usefixtures("app_db")


def _any(value: object) -> Any:
    """Hand a fake to a handler typed for the real Telegram classes."""
    return cast(Any, value)


async def _categories(user_id: int = 1) -> list[Any]:
    async with session_scope() as session:
        return list(await repo.list_categories(session, user_id))


async def _expenses(user_id: int = 1) -> list[Any]:
    async with session_scope() as session:
        return list(await repo.list_expenses(session, user_id, limit=50))


# ------------------------------------------------------------------ onboarding


async def test_start_registers_the_user_and_seeds_categories() -> None:
    update, context = command("/start"), FakeContext()

    await start.start(_any(update), _any(context))

    assert update.message is not None
    assert LOCALES["en"].messages["welcome"][:10] in text_of(update.message.sent[0])
    assert len(await _categories()) == len(repo.DEFAULT_CATEGORIES)


async def test_persian_speaker_is_onboarded_in_persian() -> None:
    update = command("/start", user_id=7, language_code="fa-IR")

    await start.start(_any(update), _any(FakeContext()))

    async with session_scope() as session:
        user = await repo.get_user(session, 7)
    assert user is not None and user.locale == "fa"
    # Seeded categories are stored already translated.
    assert any(c.name == "خوراک" for c in await _categories(7))


async def test_language_switch_persists_and_confirms_in_the_new_language() -> None:
    await start.start(_any(command("/start")), _any(FakeContext()))

    update = tap("lang:fa")
    await start.language_chosen(_any(update), _any(FakeContext()))

    async with session_scope() as session:
        user = await repo.get_user(session, 1)
    assert user is not None and user.locale == "fa"
    assert update.callback_query is not None
    assert update.callback_query.edits[0].text == LOCALES["fa"].messages["language_changed"]


# --------------------------------------------------------------- adding an expense


async def test_freeform_entry_asks_for_a_category_before_saving_anything() -> None:
    update, context = command("25000 lunch"), FakeContext()

    await expenses.freeform(_any(update), _any(context))

    assert update.message is not None
    assert update.message.sent[0].reply_markup is not None
    # Nothing is persisted until the user commits by choosing a category.
    assert await _expenses() == []
    assert context.user_data[expenses.PENDING_KEY]["amount"] == "25000"


async def test_choosing_a_category_saves_the_expense() -> None:
    context = FakeContext()
    await expenses.freeform(_any(command("25000 lunch")), _any(context))
    food = next(c for c in await _categories() if c.slug == "food")

    await expenses.category_chosen(_any(tap(f"pick:{food.id}")), _any(context))

    saved = await _expenses()
    assert len(saved) == 1
    assert saved[0].amount == Decimal("25000")
    assert saved[0].note == "lunch"
    # The pending state is consumed so a second tap cannot duplicate the row.
    assert expenses.PENDING_KEY not in context.user_data


async def test_unparsable_message_is_rejected_in_the_users_language() -> None:
    await start.start(_any(command("/start")), _any(FakeContext()))
    await start.language_chosen(_any(tap("lang:fa")), _any(FakeContext()))

    update = command("hello there")
    await expenses.freeform(_any(update), _any(FakeContext()))

    assert update.message is not None
    assert update.message.sent[0].text == LOCALES["fa"].messages["parse_failed"]
    assert await _expenses() == []


async def test_undo_removes_the_expense_just_saved() -> None:
    context = FakeContext()
    await expenses.freeform(_any(command("25000 lunch")), _any(context))
    food = next(c for c in await _categories() if c.slug == "food")
    await expenses.category_chosen(_any(tap(f"pick:{food.id}")), _any(context))
    saved = await _expenses()

    await expenses.undo(_any(tap(f"undo:{saved[0].id}")), _any(FakeContext()))

    assert await _expenses() == []


async def test_a_stale_button_does_not_crash_or_save() -> None:
    """A button pressed after a restart has no pending state behind it."""
    update = tap("pick:1")

    await expenses.category_chosen(_any(update), _any(FakeContext()))

    assert update.callback_query is not None
    assert update.callback_query.edits[0].text == LOCALES["en"].messages["not_found"]
    assert await _expenses() == []


async def test_one_user_cannot_touch_another_users_expense() -> None:
    context = FakeContext()
    await expenses.freeform(_any(command("25000 lunch", user_id=1)), _any(context))
    food = next(c for c in await _categories(1) if c.slug == "food")
    await expenses.category_chosen(_any(tap(f"pick:{food.id}", user_id=1)), _any(context))
    victim = (await _expenses(1))[0]

    update = tap(f"undo:{victim.id}", user_id=999)
    await expenses.undo(_any(update), _any(FakeContext()))

    assert len(await _expenses(1)) == 1, "an expense was deleted by a different user"


# ------------------------------------------------------------------- listing


async def test_list_is_paginated_and_clamped() -> None:
    context = FakeContext()
    for i in range(12):
        await expenses.freeform(_any(command(f"{i + 1}00 item{i}")), _any(context))
        food = next(c for c in await _categories() if c.slug == "food")
        await expenses.category_chosen(_any(tap(f"pick:{food.id}")), _any(context))

    update = command("/list")
    await listing.list_command(_any(update), _any(context))
    assert update.message is not None
    first_page = update.message.sent[0]
    assert "1" in text_of(first_page)

    # A page far beyond the end is clamped rather than showing nothing.
    beyond = tap("lp:99")
    await listing.change_page(_any(beyond), _any(context))
    assert beyond.callback_query is not None
    assert text_of(beyond.callback_query.edits[0]).strip() != ""


# -------------------------------------------------------------------- reports


async def test_report_says_so_when_the_month_is_empty() -> None:
    update = command("/report")

    await reports.report_command(_any(update), _any(FakeContext()))

    assert update.message is not None
    assert "Nothing recorded" in text_of(update.message.sent[0])


async def test_report_sends_a_summary_and_a_chart() -> None:
    context = FakeContext()
    await expenses.freeform(_any(command("25000 lunch")), _any(context))
    food = next(c for c in await _categories() if c.slug == "food")
    await expenses.category_chosen(_any(tap(f"pick:{food.id}")), _any(context))

    update, context = command("/report"), FakeContext()
    await reports.report_command(_any(update), _any(context))

    assert update.message is not None
    summary, chart = update.message.sent[0], update.message.sent[1]
    assert "25,000" in text_of(summary)
    assert chart.photo is not None and chart.photo[:4] == b"\x89PNG"
    # Chart rendering is slow enough to look like a stall without feedback.
    assert context.bot.actions == ["upload_photo"]


async def test_expensive_commands_are_rate_limited() -> None:
    await reports.report_command(_any(command("/report")), _any(FakeContext()))

    second = command("/report")
    await reports.report_command(_any(second), _any(FakeContext()))

    assert second.message is not None
    assert second.message.sent[0].text == LOCALES["en"].messages["rate_limited"]


# --------------------------------------------------------------------- export


async def test_export_is_excel_safe_and_keeps_persian_intact() -> None:
    context = FakeContext()
    await expenses.freeform(_any(command("25000 ناهار")), _any(context))
    food = next(c for c in await _categories() if c.slug == "food")
    await expenses.category_chosen(_any(tap(f"pick:{food.id}")), _any(context))

    update, context = command("/export"), FakeContext()
    await export.export_command(_any(update), _any(context))

    assert update.message is not None
    assert context.bot.actions == ["upload_document"]
    payload = update.message.sent[0].document
    assert payload.startswith(b"\xef\xbb\xbf"), "Excel needs a BOM to read UTF-8"
    assert "ناهار" in payload.decode("utf-8-sig")
    assert update.message.sent[0].filename == "expenses.csv"


async def test_export_of_an_empty_history_explains_rather_than_sending_a_file() -> None:
    update = command("/export")

    await export.export_command(_any(update), _any(FakeContext()))

    assert update.message is not None
    assert update.message.sent[0].document is None
    assert update.message.sent[0].text == LOCALES["en"].messages["export_empty"]
