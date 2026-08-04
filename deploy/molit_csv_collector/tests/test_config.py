"""iter_download_periods — 기간 분할 규칙."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from molit_csv_collector.config import iter_download_periods  # noqa: E402


def test_cross_year_partial_range_single_file():
    periods = iter_download_periods(2025, 7, 2026, 6)
    assert len(periods) == 1
    assert periods[0].key == "20250701_20260630"
    assert periods[0].from_date == "2025-07-01"
    assert periods[0].to_date == "2026-06-30"


def test_single_full_calendar_year():
    periods = iter_download_periods(2020, 1, 2020, 12)
    assert len(periods) == 1
    assert periods[0].key == "2020"


def test_multi_year_full_calendar_range_single_file():
    periods = iter_download_periods(2010, 1, 2012, 12)
    assert len(periods) == 1
    assert periods[0].key == "20100101_20121231"
    assert periods[0].from_date == "2010-01-01"
    assert periods[0].to_date == "2012-12-31"


def test_partial_multi_year_single_file():
    periods = iter_download_periods(2025, 8, 2026, 7)
    assert len(periods) == 1
    assert periods[0].key == "20250801_20260731"
    assert periods[0].from_date == "2025-08-01"
    assert periods[0].to_date == "2026-07-31"
