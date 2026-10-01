from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from expensebot import repository as repo
from expensebot.models import Expense

NAMES = {"food": "Food", "transport": "Transport", "other": "Other"}


async def _user(session: AsyncSession, user_id: int = 42):
    return await repo.create_user(
        session,
        user_id,
        locale="en",
        timezone="Asia/Tehran",
        currency="IRR",
        category_names=NAMES,
    )


async def test_create_user_seeds_builtin_categories(session: AsyncSession) -> None:
    user = await _user(session)

    categories = await repo.list_categories(session, user.id)

    assert len(categories) == len(repo.DEFAULT_CATEGORIES)
    assert all(c.is_builtin for c in categories)
    # Names come from the caller's translation table; slugs stay stable.
    by_slug = {c.slug: c for c in categories}
    assert by_slug["food"].name == "Food"
    assert by_slug["housing"].name == "housing"  # not supplied, falls back to slug


async def test_add_and_read_back_expense(session: AsyncSession) -> None:
    user = await _user(session)
    food = next(c for c in await repo.list_categories(session, user.id) if c.slug == "food")

    expense = await repo.add_expense(
        session,
        user.id,
        amount=Decimal("25000.50"),
        category_id=food.id,
        note="lunch",
        spent_at=datetime(2026, 3, 10, 12, 0, tzinfo=UTC),
    )

    fetched = await repo.get_expense(session, user.id, expense.id)
    assert fetched is not None
    # Stored as Numeric, so the decimal survives the round trip exactly.
    assert fetched.amount == Decimal("25000.50")
    assert fetched.note == "lunch"
    assert fetched.category is not None and fetched.category.slug == "food"


async def test_expenses_are_scoped_to_their_owner(session: AsyncSession) -> None:
    owner = await _user(session, 1)
    intruder = await _user(session, 2)
    expense = await repo.add_expense(
        session,
        owner.id,
        amount=Decimal("100"),
        category_id=None,
        note=None,
        spent_at=datetime.now(UTC),
    )

    assert await repo.get_expense(session, intruder.id, expense.id) is None


async def test_period_queries_respect_boundaries(session: AsyncSession) -> None:
    user = await _user(session)
    start = datetime(2026, 3, 1, tzinfo=UTC)
    end = datetime(2026, 4, 1, tzinfo=UTC)

    for when, amount in [
        (start - timedelta(seconds=1), "999"),  # just before the window
        (start, "10"),  # inclusive lower bound
        (datetime(2026, 3, 15, tzinfo=UTC), "20"),
        (end, "888"),  # exclusive upper bound
    ]:
        await repo.add_expense(
            session,
            user.id,
            amount=Decimal(amount),
            category_id=None,
            note=None,
            spent_at=when,
        )

    assert await repo.total_for_period(session, user.id, start=start, end=end) == Decimal("30")
    assert await repo.count_expenses(session, user.id, start=start, end=end) == 2


async def test_totals_by_category_sorted_desc(session: AsyncSession) -> None:
    user = await _user(session)
    cats = {c.slug: c for c in await repo.list_categories(session, user.id)}
    start, end = datetime(2026, 3, 1, tzinfo=UTC), datetime(2026, 4, 1, tzinfo=UTC)

    for slug, amount in [("food", "10"), ("food", "15"), ("transport", "40")]:
        await repo.add_expense(
            session,
            user.id,
            amount=Decimal(amount),
            category_id=cats[slug].id,
            note=None,
            spent_at=datetime(2026, 3, 5, tzinfo=UTC),
        )

    totals = await repo.totals_by_category(session, user.id, start=start, end=end)

    assert [(t.slug, t.total) for t in totals] == [
        ("transport", Decimal("40")),
        ("food", Decimal("25")),
    ]


async def test_deleting_custom_category_keeps_its_expenses(session: AsyncSession) -> None:
    user = await _user(session)
    custom = await repo.create_category(session, user.id, slug="pets", name="Pets", emoji="🐱")
    expense = await repo.add_expense(
        session,
        user.id,
        amount=Decimal("50"),
        category_id=custom.id,
        note="food",
        spent_at=datetime.now(UTC),
    )

    await repo.delete_category(session, custom)

    survivor = await session.get(Expense, expense.id)
    assert survivor is not None, "deleting a category must not delete spending history"
    assert survivor.category_id is None


async def test_builtin_category_is_hidden_not_deleted(session: AsyncSession) -> None:
    user = await _user(session)
    food = next(c for c in await repo.list_categories(session, user.id) if c.slug == "food")

    await repo.delete_category(session, food)

    visible = await repo.list_categories(session, user.id)
    assert food.slug not in {c.slug for c in visible}
    assert food.slug in {
        c.slug for c in await repo.list_categories(session, user.id, include_hidden=True)
    }
