"""V2 롤링 통계 기간 계산 (pipeline/build_stats_v2.py 와 동일 규칙).

docs/V2_STATS_DESIGN.md §3–4:
  - period_end = as_of_month 달의 말일 (배치는 직전 월 말까지 반영하도록 as_of 맞춤).
  - period_start = period_end에서 달력 window_years년 전(월·일 클램프)의 익일.
"""

from __future__ import annotations

import calendar
from datetime import date, timedelta

# docs/ROLLING_WINDOW_7Y_PLAN.md — UI 3·5(기본)·7, DDL·API 상한
MAX_WINDOW_YEARS = 7
UI_WINDOW_YEARS = (3, 5, 7)


def last_day_of_month(any_date_in_month: date) -> date:
    y, m = any_date_in_month.year, any_date_in_month.month
    return date(y, m, calendar.monthrange(y, m)[1])


def _anchor_n_calendar_years_before(period_end: date, window_years: int) -> date:
    """period_end와 같은 월·일에서 연도만 window_years 만큼 뺀 날(윤달/말일 클램프)."""
    y = period_end.year - window_years
    last = calendar.monthrange(y, period_end.month)[1]
    day = min(period_end.day, last)
    return date(y, period_end.month, day)


def default_as_of_month_for_service(today: date | None = None) -> date:
    """
    §3 배치·API 공통: 서버 «오늘»이 속한 달의 직전 달 1일 (그 직전 달 말까지 반영 스냅샷 키).
    """
    today = today or date.today()
    first_this = today.replace(day=1)
    last_prev = first_this - timedelta(days=1)
    return last_prev.replace(day=1)


def stats_ui_reference_date(as_of_month: date) -> date:
    """
    사용자에게 보이는 기준일: 스냅샷 월(as_of_month) 바로 다음 달 1일.
    (배치가 U월에 돌면 as_of는 U-1월 1일 → 표시는 U월 1일.)
    """
    if as_of_month.day != 1:
        raise ValueError("as_of_month 는 해당 월 1일이어야 합니다.")
    if as_of_month.month == 12:
        return date(as_of_month.year + 1, 1, 1)
    return date(as_of_month.year, as_of_month.month + 1, 1)


def period_bounds_for_window(as_of_month: date, window_years: int) -> tuple[date, date]:
    if as_of_month.day != 1:
        raise ValueError("as_of_month 는 해당 월 1일이어야 합니다.")
    if window_years < 1 or window_years > MAX_WINDOW_YEARS:
        raise ValueError(f"window_years 는 1~{MAX_WINDOW_YEARS} 만 허용됩니다.")
    period_end = last_day_of_month(as_of_month)
    anchor = _anchor_n_calendar_years_before(period_end, window_years)
    period_start = anchor + timedelta(days=1)
    return period_start, period_end


def _bucket_range_closed_ending(bucket_end: date) -> tuple[date, date]:
    """12개월 버킷 [start, end] — end 포함, start는 anchor+1일."""
    anchor = _anchor_n_calendar_years_before(bucket_end, 1)
    start = anchor + timedelta(days=1)
    return start, bucket_end


def iter_rolling_year_buckets_old_first(
    period_end: date, bucket_count: int
) -> list[tuple[date, date, int]]:
    """과거→최근 12개월 버킷 (bucket_index 1..N). pipeline/build_collective_building_rolling_stats 와 동일."""
    if bucket_count < 1:
        return []
    ends: list[date] = []
    cur = period_end
    ends.append(cur)
    for _ in range(1, bucket_count):
        cur = _anchor_n_calendar_years_before(cur, 1)
        ends.append(cur)
    ends.reverse()
    return [
        (*_bucket_range_closed_ending(e), idx + 1)
        for idx, e in enumerate(ends)
    ]
