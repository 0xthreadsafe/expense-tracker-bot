from __future__ import annotations

from datetime import UTC, datetime

from expensebot.periods import day_period, get_zone, month_period, parse_month, to_local

TEHRAN = "Asia/Tehran"


def test_month_boundaries_follow_the_users_timezone_not_utc() -> None:
    # Tehran is UTC+3:30, so its March starts before UTC's March does.
    period = month_period(TEHRAN, reference=datetime(2026, 3, 15, tzinfo=UTC))

    assert period.start == datetime(2026, 2, 28, 20, 30, tzinfo=UTC)
    assert period.end == datetime(2026, 3, 31, 20, 30, tzinfo=UTC)


def test_spending_just_after_local_midnight_belongs_to_the_new_month() -> None:
    """The bug this guards: 00:30 Tehran on 1 March is still February in UTC."""
    march = month_period(TEHRAN, reference=datetime(2026, 3, 15, tzinfo=UTC))
    just_after_local_midnight = datetime(2026, 2, 28, 21, 0, tzinfo=UTC)  # 00:30 local, 1 Mar

    assert march.contains(just_after_local_midnight)


def test_periods_are_half_open() -> None:
    period = month_period(TEHRAN, reference=datetime(2026, 3, 15, tzinfo=UTC))

    assert period.contains(period.start)
    assert not period.contains(period.end)


def test_consecutive_months_leave_no_gap_and_no_overlap() -> None:
    current = month_period(TEHRAN, reference=datetime(2026, 3, 15, tzinfo=UTC))
    previous = month_period(TEHRAN, reference=datetime(2026, 3, 15, tzinfo=UTC), offset=-1)

    assert previous.end == current.start


def test_offset_crosses_year_boundaries() -> None:
    january = datetime(2026, 1, 10, tzinfo=UTC)

    assert month_period("UTC", reference=january, offset=-1).label.year == 2025
    assert month_period("UTC", reference=january, offset=-1).label.month == 12
    assert month_period("UTC", reference=january, offset=12).label.year == 2027
    assert month_period("UTC", reference=january, offset=-13).label.month == 12


def test_december_rolls_into_january() -> None:
    period = month_period("UTC", reference=datetime(2026, 12, 5, tzinfo=UTC))

    assert period.end == datetime(2027, 1, 1, tzinfo=UTC)


def test_day_period_is_a_local_day() -> None:
    period = day_period(TEHRAN, reference=datetime(2026, 3, 15, 12, 0, tzinfo=UTC))

    assert (period.end - period.start).total_seconds() == 24 * 3600
    assert period.label.hour == 0


def test_parse_month_accepts_valid_input_and_rejects_the_rest() -> None:
    assert parse_month("2026-03", TEHRAN) is not None
    assert parse_month("2026-3", TEHRAN) is not None

    for bad in ["", "2026", "2026-13", "2026-00", "abcd-ef", "1800-01"]:
        assert parse_month(bad, TEHRAN) is None, bad


def test_unknown_timezone_falls_back_to_utc_rather_than_failing() -> None:
    assert get_zone("Mars/Olympus") == get_zone("UTC")


def test_to_local_assumes_utc_for_naive_timestamps() -> None:
    # SQLite can return naive datetimes; treating them as local would shift data.
    naive = datetime(2026, 3, 15, 12, 0)
    assert to_local(naive, TEHRAN).hour == 15
