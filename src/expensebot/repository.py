"""Data access.

Functions here are named for what the application wants, not for the SQL they
emit. Handlers call these and never build queries themselves, which keeps the
Telegram layer free of persistence details and makes this module testable on
its own.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from expensebot.models import Category, Expense, User

# Seeded for every new user. ``slug`` is stable and locale-independent: it keys
# the translations and labels charts, so it must never be translated in place.
DEFAULT_CATEGORIES: tuple[tuple[str, str], ...] = (
    ("food", "🍔"),
    ("transport", "🚌"),
    ("housing", "🏠"),
    ("bills", "💡"),
    ("health", "💊"),
    ("shopping", "🛍️"),
    ("fun", "🎬"),
    ("other", "📦"),
)


@dataclass(frozen=True)
class CategoryTotal:
    """One row of a report breakdown."""

    slug: str
    name: str
    emoji: str
    total: Decimal


# --------------------------------------------------------------------------- users


async def get_user(session: AsyncSession, user_id: int) -> User | None:
    return await session.get(User, user_id)


async def create_user(
    session: AsyncSession,
    user_id: int,
    *,
    locale: str,
    timezone: str,
    currency: str,
    category_names: dict[str, str],
) -> User:
    """Create a user and seed their own copy of the built-in categories.

    ``category_names`` maps slug -> localized name, supplied by the caller so
    that this module stays independent of the translation layer.
    """
    user = User(id=user_id, locale=locale, timezone=timezone, currency=currency)
    session.add(user)
    await session.flush()

    session.add_all(
        [
            Category(
                user_id=user.id,
                slug=slug,
                name=category_names.get(slug, slug),
                emoji=emoji,
                is_builtin=True,
            )
            for slug, emoji in DEFAULT_CATEGORIES
        ]
    )
    await session.flush()
    return user


async def set_locale(session: AsyncSession, user: User, locale: str) -> None:
    user.locale = locale
    await session.flush()


async def set_reminder(
    session: AsyncSession, user: User, hour: int | None, minute: int | None
) -> None:
    user.reminder_hour = hour
    user.reminder_minute = minute
    await session.flush()


async def users_with_reminders(session: AsyncSession) -> Sequence[User]:
    """Used at startup to re-register reminder jobs after a restart."""
    result = await session.scalars(select(User).where(User.reminder_hour.is_not(None)))
    return result.all()


# ---------------------------------------------------------------------- categories


async def list_categories(
    session: AsyncSession, user_id: int, *, include_hidden: bool = False
) -> Sequence[Category]:
    stmt = select(Category).where(Category.user_id == user_id)
    if not include_hidden:
        stmt = stmt.where(Category.is_hidden.is_(False))
    result = await session.scalars(stmt.order_by(Category.is_builtin.desc(), Category.name))
    return result.all()


async def get_category(session: AsyncSession, user_id: int, category_id: int) -> Category | None:
    """Scoped by user so one user can never address another user's category."""
    return await session.scalar(
        select(Category).where(Category.id == category_id, Category.user_id == user_id)
    )


async def create_category(
    session: AsyncSession, user_id: int, *, slug: str, name: str, emoji: str
) -> Category:
    category = Category(user_id=user_id, slug=slug, name=name, emoji=emoji, is_builtin=False)
    session.add(category)
    await session.flush()
    return category


async def rename_category(session: AsyncSession, category: Category, name: str) -> None:
    category.name = name
    await session.flush()


async def delete_category(session: AsyncSession, category: Category) -> None:
    """Remove a custom category, detaching its expenses rather than deleting them.

    Built-in categories are hidden instead, so a reassignment target always
    remains available.
    """
    if category.is_builtin:
        category.is_hidden = True
        await session.flush()
        return

    await session.execute(
        update(Expense).where(Expense.category_id == category.id).values(category_id=None)
    )
    await session.execute(delete(Category).where(Category.id == category.id))
    await session.flush()


# ------------------------------------------------------------------------ expenses


async def add_expense(
    session: AsyncSession,
    user_id: int,
    *,
    amount: Decimal,
    category_id: int | None,
    note: str | None,
    spent_at: datetime,
) -> Expense:
    expense = Expense(
        user_id=user_id,
        amount=amount,
        category_id=category_id,
        note=note,
        spent_at=spent_at,
    )
    session.add(expense)
    await session.flush()
    return expense


async def get_expense(session: AsyncSession, user_id: int, expense_id: int) -> Expense | None:
    return await session.scalar(
        select(Expense).where(Expense.id == expense_id, Expense.user_id == user_id)
    )


async def delete_expense(session: AsyncSession, expense: Expense) -> None:
    await session.delete(expense)
    await session.flush()


async def list_expenses(
    session: AsyncSession,
    user_id: int,
    *,
    start: datetime | None = None,
    end: datetime | None = None,
    limit: int = 10,
    offset: int = 0,
) -> Sequence[Expense]:
    stmt = select(Expense).where(Expense.user_id == user_id)
    if start is not None:
        stmt = stmt.where(Expense.spent_at >= start)
    if end is not None:
        stmt = stmt.where(Expense.spent_at < end)
    stmt = stmt.order_by(Expense.spent_at.desc(), Expense.id.desc()).limit(limit).offset(offset)
    result = await session.scalars(stmt)
    return result.all()


async def count_expenses(
    session: AsyncSession,
    user_id: int,
    *,
    start: datetime | None = None,
    end: datetime | None = None,
) -> int:
    """Needed to decide whether a pagination keyboard should offer a next page."""
    stmt = select(func.count(Expense.id)).where(Expense.user_id == user_id)
    if start is not None:
        stmt = stmt.where(Expense.spent_at >= start)
    if end is not None:
        stmt = stmt.where(Expense.spent_at < end)
    return await session.scalar(stmt) or 0


# ------------------------------------------------------------------------- reports


async def total_for_period(
    session: AsyncSession, user_id: int, *, start: datetime, end: datetime
) -> Decimal:
    stmt = select(func.coalesce(func.sum(Expense.amount), 0)).where(
        Expense.user_id == user_id, Expense.spent_at >= start, Expense.spent_at < end
    )
    return Decimal(str(await session.scalar(stmt) or 0))


async def totals_by_category(
    session: AsyncSession, user_id: int, *, start: datetime, end: datetime
) -> list[CategoryTotal]:
    """Breakdown for a period, largest first.

    Uses an outer join so that expenses whose category was deleted still appear,
    grouped under a null slug the caller can label as 'uncategorized'.
    """
    stmt = (
        select(
            Category.slug,
            Category.name,
            Category.emoji,
            func.sum(Expense.amount).label("total"),
        )
        .select_from(Expense)
        .outerjoin(Category, Expense.category_id == Category.id)
        .where(Expense.user_id == user_id, Expense.spent_at >= start, Expense.spent_at < end)
        .group_by(Category.slug, Category.name, Category.emoji)
        .order_by(func.sum(Expense.amount).desc())
    )
    rows = await session.execute(stmt)
    return [
        CategoryTotal(
            slug=row.slug or "uncategorized",
            name=row.name or "Uncategorized",
            emoji=row.emoji or "❓",
            total=Decimal(str(row.total)),
        )
        for row in rows
    ]


async def has_expense_on_day(
    session: AsyncSession, user_id: int, *, start: datetime, end: datetime
) -> bool:
    """Supports the reminder job: skip users who already logged something today."""
    stmt = (
        select(Expense.id)
        .where(Expense.user_id == user_id, Expense.spent_at >= start, Expense.spent_at < end)
        .limit(1)
    )
    return await session.scalar(stmt) is not None
