"""Chart rendering.

Labels are English in every locale. matplotlib performs no Arabic shaping or
bidirectional reordering, so Persian text would render as disconnected,
reversed glyphs; supporting it properly needs a reshaper and a bundled font,
which is deferred. Built-in categories therefore chart under their English
names, and a category whose name cannot be rendered falls back to its slug.

Rendering is synchronous and CPU-bound, so callers must run :func:`render_breakdown`
in a worker thread to avoid blocking the event loop for every other user.
"""

from __future__ import annotations

import io
import logging
from collections.abc import Sequence

import matplotlib

# Must be selected before pyplot is imported: there is no display on a server.
matplotlib.use("Agg")

import matplotlib.pyplot as plt

from expensebot.i18n import category_name
from expensebot.repository import DEFAULT_CATEGORIES, CategoryTotal

logger = logging.getLogger(__name__)

MAX_SLICES = 8

_BUILTIN_SLUGS = {slug for slug, _ in DEFAULT_CATEGORIES}

# Chosen to stay distinguishable in both light and dark chat themes, and
# ordered so neighbouring bars never rely on hue alone to be told apart.
PALETTE = (
    "#4C78A8",
    "#F58518",
    "#54A24B",
    "#E45756",
    "#72B7B2",
    "#B279A2",
    "#EECA3B",
    "#9D755D",
)


def compact_number(value: float, _position: int | None = None) -> str:
    """Abbreviate an axis value, e.g. 317500000 -> '317.5M'."""
    for threshold, suffix in ((1_000_000_000, "B"), (1_000_000, "M"), (1_000, "K")):
        if abs(value) >= threshold:
            scaled = value / threshold
            # Drop a trailing .0 so round numbers stay short.
            text = f"{scaled:.1f}".rstrip("0").rstrip(".")
            return f"{text}{suffix}"
    return f"{value:,.0f}"


def _is_renderable(text: str) -> bool:
    """True when every character is Latin-1, which matplotlib renders reliably."""
    try:
        text.encode("latin-1")
    except UnicodeEncodeError:
        return False
    return True


def chart_label(total: CategoryTotal) -> str:
    """An always-renderable English label for a category.

    Built-in categories have a translation keyed by slug; custom categories
    keep their own name when it is Latin, and otherwise fall back to the slug,
    which is Latin by construction.
    """
    # Probing the catalog directly would log a miss for every custom category,
    # so built-in membership is checked first.
    if total.slug in _BUILTIN_SLUGS:
        english = category_name(total.slug, "en")
        if _is_renderable(english):
            return english
    if _is_renderable(total.name):
        return total.name
    return total.slug.replace("-", " ").title()


def render_breakdown(totals: Sequence[CategoryTotal], *, title: str, currency: str) -> bytes:
    """Draw a horizontal bar chart and return it as PNG bytes.

    Horizontal bars are used rather than a pie chart because comparing lengths
    is more accurate than comparing angles, and long category names fit.
    """
    ranked = sorted(totals, key=lambda c: c.total, reverse=True)
    head = ranked[:MAX_SLICES]
    # Collapse the tail so the chart stays legible with many categories.
    if len(ranked) > MAX_SLICES:
        remainder = sum(c.total for c in ranked[MAX_SLICES:])
        labels = [chart_label(c) for c in head] + [f"Other ({len(ranked) - MAX_SLICES})"]
        values = [float(c.total) for c in head] + [float(remainder)]
    else:
        labels = [chart_label(c) for c in head]
        values = [float(c.total) for c in head]

    figure, axes = plt.subplots(figsize=(7, 0.6 * len(labels) + 1.6), dpi=160)
    try:
        positions = range(len(labels))
        axes.barh(
            list(positions),
            values,
            color=[PALETTE[i % len(PALETTE)] for i in positions],
        )
        axes.set_yticks(list(positions), labels)
        axes.invert_yaxis()  # largest at the top, matching the text report
        axes.set_title(title)
        axes.set_xlabel(currency)

        # Value labels remove the need to read values off the axis.
        largest = max(values) if values else 0
        for index, value in enumerate(values):
            axes.text(
                value + largest * 0.01,
                index,
                compact_number(value) if largest >= 1_000_000 else f"{value:,.0f}",
                va="center",
                fontsize=9,
            )

        # Match the grouping used by the value labels and the text report.
        # Nine-digit values make fully grouped tick labels collide, so ticks are
        # thinned and abbreviated; exact figures stay on the value labels.
        axes.xaxis.set_major_locator(matplotlib.ticker.MaxNLocator(nbins=5, prune="lower"))
        axes.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(compact_number))
        axes.spines[["top", "right"]].set_visible(False)
        axes.grid(axis="x", color="#E6E6E6", linewidth=0.8)
        axes.set_axisbelow(True)
        axes.set_xlim(0, largest * 1.15 if largest else 1)
        figure.tight_layout()

        buffer = io.BytesIO()
        figure.savefig(buffer, format="png", transparent=False, facecolor="white")
        return buffer.getvalue()
    finally:
        # Figures are retained by pyplot until closed; leaking them grows memory
        # on every report.
        plt.close(figure)
