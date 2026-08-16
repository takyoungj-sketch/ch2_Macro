"""iter_download_periods — 국토부 1회 최대 12개월 분할."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from molit_csv_collector.config import (  # noqa: E402
    MOLIT_MAX_PERIOD_MONTHS,
    iter_download_periods,
)
from molit_csv_collector.downloader import _is_fatal_molit_alert  # noqa: E402


def test_cross_year_rolling_12m_single_file():
    periods = iter_download_periods(2025, 7, 2026, 6)
    assert len(periods) == 1
    assert periods[0].key == "20250701_20260630"
    assert periods[0].from_date == "2025-07-01"
    assert periods[0].to_date == "2026-06-30"


def test_single_full_calendar_year():
    periods = iter_download_periods(2020, 1, 2020, 12)
    assert len(periods) == 1
    assert periods[0].key == "2020"


def test_multi_year_full_calendar_splits_by_year():
    periods = iter_download_periods(2010, 1, 2012, 12)
    assert [p.key for p in periods] == ["2010", "2011", "2012"]
    assert periods[0].from_date == "2010-01-01"
    assert periods[-1].to_date == "2012-12-31"


def test_partial_rolling_year_stays_one_file():
    periods = iter_download_periods(2025, 8, 2026, 7)
    assert len(periods) == 1
    assert periods[0].key == "20250801_20260731"
    assert periods[0].from_date == "2025-08-01"
    assert periods[0].to_date == "2026-07-31"


def test_historical_decade_splits_to_calendar_years():
    periods = iter_download_periods(2010, 1, 2020, 12)
    assert len(periods) == 11
    assert periods[0].key == "2010"
    assert periods[-1].key == "2020"


def test_mid_year_span_over_12_months_splits():
    periods = iter_download_periods(2010, 6, 2011, 6)
    assert len(periods) == 2
    assert periods[0].from_date == "2010-06-01"
    assert periods[0].to_date == "2011-05-31"
    assert periods[1].from_date == "2011-06-01"
    assert periods[1].to_date == "2011-06-30"


def test_each_chunk_at_most_12_months():
    periods = iter_download_periods(2006, 3, 2026, 7)
    assert MOLIT_MAX_PERIOD_MONTHS == 12
    for p in periods:
        y0, m0 = int(p.from_date[:4]), int(p.from_date[5:7])
        y1, m1 = int(p.to_date[:4]), int(p.to_date[5:7])
        span = (y1 * 12 + m1) - (y0 * 12 + m0) + 1
        assert span <= MOLIT_MAX_PERIOD_MONTHS, (p.key, span)


def test_fatal_alert_detects_one_year_limit():
    assert _is_fatal_molit_alert("조회기간은 1년을 초과할 수 없습니다.")
    assert _is_fatal_molit_alert("다운로드 실패")
    assert not _is_fatal_molit_alert("처리가 완료되었습니다.")
