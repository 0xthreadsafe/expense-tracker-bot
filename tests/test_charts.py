from __future__ import annotations

from decimal import Decimal

import pytest

from expensebot.charts import chart_label, compact_number, render_breakdown
from expensebot.repository import CategoryTotal


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (0, "0"),
        (950, "950"),
        (10_000_000, "10M"),
        (317_500_000, "317.5M"),
        (2_400_000_000, "2.4B"),
        (50_000, "50K"),
    ],
)
def test_axis_values_are_abbreviated(value: float, expected: str) -> None:
    """Fully grouped nine-digit labels collide on the axis."""
    assert compact_number(value) == expected


def test_labels_fall_back_to_something_renderable() -> None:
    # matplotlib cannot shape Arabic, so a Persian name must never reach it.
    assert chart_label(CategoryTotal("food", "خوراک", "🍔", Decimal(1))) == "Food"
    assert chart_label(CategoryTotal("pets", "گربه", "🐱", Decimal(1))) == "Pets"
    assert chart_label(CategoryTotal("books", "Books", "📚", Decimal(1))) == "Books"


def test_render_returns_a_png() -> None:
    totals = [CategoryTotal("food", "Food", "🍔", Decimal("317500000"))]

    png = render_breakdown(totals, title="October 2026", currency="IRR")

    assert png[:4] == b"\x89PNG"
