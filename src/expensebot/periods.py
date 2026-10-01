"""Date ranges.

A month means the user's month, not UTC's. Boundaries are therefore computed in
the user's timezone and converted back to UTC for querying, because that is how
the rows are stored. Getting this wrong shifts spending between months for
anyone not living on UTC.

All calendars here are Gregorian; see the deferred Jalali work.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


@dataclass(frozen=True)
class Period:
    """A half-open range: ``start`` is included, ``end`` is not.

    Half-open ranges are used so that consecutive periods neither overlap nor
    leave a gap, which closed ranges cannot guarantee at midnight.
    """

    start: datetime
    end: datetime
    label: datetime  # a date inside the period, for naming it

    def contains(self, moment: datetime) -> bool:
        return self.start <= moment < self.end


def get_zone(name: str) -> ZoneInfo:
    """Resolve a timezone, falling back to UTC rather than failing a report."""
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("UTC")


def month_period(timezone: str, *, reference: datetime | None = None, offset: int = 0) -> Period:
    """The user's calendar month containing ``reference``, shifted by ``offset``.

    ``offset=-1`` yields the previous month.
    """
    zone = get_zone(timezone)
    local = (reference or datetime.now(UTC)).astimezone(zone)

    year, month = local.year, local.month + offset
    # Normalise an offset that crossed a year boundary.
    year += (month - 1) // 12
    month = (month - 1) % 12 + 1

    start_local = datetime(year, month, 1, tzinfo=zone)
    next_year, next_month = (year + 1, 1) if month == 12 else (year, month + 1)
    end_local = datetime(next_year, next_month, 1, tzinfo=zone)

    return Period(
        start=start_local.astimezone(UTC),
        end=end_local.astimezone(UTC),
        label=start_local,
    )


def parse_month(value: str, timezone: str) -> Period | None:
    """Parse a ``YYYY-MM`` argument into a period, or return None."""
    try:
        year_text, month_text = value.strip().split("-", 1)
        year, month = int(year_text), int(month_text)
        if not 1 <= month <= 12 or not 1970 <= year <= 2999:
            return None
    except ValueError:
        return None

    zone = get_zone(timezone)
    return month_period(timezone, reference=datetime(year, month, 15, tzinfo=zone))


def day_period(timezone: str, *, reference: datetime | None = None) -> Period:
    """The user's current calendar day."""
    zone = get_zone(timezone)
    local = (reference or datetime.now(UTC)).astimezone(zone)
    start_local = datetime(local.year, local.month, local.day, tzinfo=zone)
    return Period(
        start=start_local.astimezone(UTC),
        end=(start_local + timedelta(days=1)).astimezone(UTC),
        label=start_local,
    )


def to_local(moment: datetime, timezone: str) -> datetime:
    """Render a stored UTC timestamp in the user's timezone."""
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return moment.astimezone(get_zone(timezone))
