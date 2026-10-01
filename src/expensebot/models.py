"""Database tables.

Money is stored as ``Numeric`` rather than a float: binary floating point cannot
represent decimal fractions exactly, and the error accumulates once values are
summed over a month. Timestamps are stored timezone-aware in UTC and converted
to the user's timezone only when a value is displayed.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class User(Base):
    """A Telegram user, keyed by their Telegram id rather than a surrogate key."""

    __tablename__ = "users"

    # Telegram ids exceed 32 bits, so BigInteger is required on Postgres.
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    locale: Mapped[str] = mapped_column(String(8), default="en")
    timezone: Mapped[str] = mapped_column(String(64), default="UTC")
    currency: Mapped[str] = mapped_column(String(3), default="IRR")

    reminder_hour: Mapped[int | None] = mapped_column(default=None)
    reminder_minute: Mapped[int | None] = mapped_column(default=None)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    categories: Mapped[list[Category]] = relationship(
        back_populates="user", cascade="all, delete-orphan", lazy="selectin"
    )

    @property
    def reminder_enabled(self) -> bool:
        return self.reminder_hour is not None


class Category(Base):
    """A spending category.

    Every user receives their own copy of the built-in categories at onboarding,
    so renaming one affects nobody else. ``is_builtin`` rows may be hidden but
    not deleted, which guarantees a destination always exists for reassignment.
    """

    __tablename__ = "categories"
    __table_args__ = (UniqueConstraint("user_id", "slug", name="uq_category_user_slug"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )

    # Stable identifier used by code and by chart labels; never shown translated.
    slug: Mapped[str] = mapped_column(String(32))
    name: Mapped[str] = mapped_column(String(64))
    emoji: Mapped[str] = mapped_column(String(8), default="•")
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=False)
    is_hidden: Mapped[bool] = mapped_column(Boolean, default=False)

    user: Mapped[User] = relationship(back_populates="categories")
    expenses: Mapped[list[Expense]] = relationship(back_populates="category")

    def label(self) -> str:
        return f"{self.emoji} {self.name}".strip()


class Expense(Base):
    __tablename__ = "expenses"
    __table_args__ = (
        # Every report and listing filters by user and date range.
        Index("ix_expense_user_spent_at", "user_id", "spent_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL"), default=None, index=True
    )

    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    note: Mapped[str | None] = mapped_column(String(256), default=None)

    spent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    category: Mapped[Category | None] = relationship(back_populates="expenses", lazy="joined")
