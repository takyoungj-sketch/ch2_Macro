"""built time_scope 단위 테스트."""

from datetime import date

import pytest

from app.built.time_scope import (
    default_as_of_month,
    last_day_of_month,
    parse_as_of_month,
    period_bounds_for_window,
)


def test_last_day_of_month():
    assert last_day_of_month(date(2024, 2, 1)) == date(2024, 2, 29)


def test_parse_as_of_month():
    assert parse_as_of_month("2024-06") == date(2024, 6, 1)


def test_period_bounds_3y():
    start, end = period_bounds_for_window(date(2026, 6, 1), 3)
    assert end == date(2026, 6, 30)
    assert start == date(2023, 7, 1)


def test_period_bounds_5y():
    start, end = period_bounds_for_window(date(2026, 6, 1), 5)
    assert end == date(2026, 6, 30)
    assert start == date(2021, 7, 1)


def test_default_as_of_month():
    d = default_as_of_month(date(2026, 6, 21))
    assert d == date(2026, 5, 1)


def test_parse_as_of_month_invalid():
    with pytest.raises(ValueError):
        parse_as_of_month("2024")
