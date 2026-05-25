"""용도×지목 매트릭스 칸 롤링 12개월 트렌드 버킷 (V2 창 종료월 기준).

버킷 k(최종=최근): 종료월 `bucket_end`에 대해
  시작일 = `_anchor_n_calendar_years_before(bucket_end, 1) + 1일`
  포함 구간 `[시작일, bucket_end]` — 사용자 예시(4/30 끝 → 5/1 시작)와 동일 패턴을 따른다.

`iter_rolling_year_buckets_old_first`: 과거→최근 순 (차트 좌→우).
"""

from __future__ import annotations

from datetime import date, timedelta

from app.v2_stats_windows import _anchor_n_calendar_years_before


def _prev_year_month_day_same(d: date) -> date:
    return _anchor_n_calendar_years_before(d, 1)


def bucket_range_closed_ending(bucket_end: date) -> tuple[date, date]:
    pb = _prev_year_month_day_same(bucket_end)
    start = pb + timedelta(days=1)
    return start, bucket_end


def iter_rolling_year_buckets_old_first(
    period_end: date, bucket_count: int
) -> list[tuple[date, date]]:
    if bucket_count < 1:
        return []
    ends: list[date] = []
    cur = period_end
    ends.append(cur)
    for _ in range(1, bucket_count):
        cur = _prev_year_month_day_same(cur)
        ends.append(cur)
    ends.reverse()
    return [bucket_range_closed_ending(e) for e in ends]


def chart_bucket_labels_old_first_for_ref_month(
    _stats_reference_date: date | None,
    bucket_pairs_old_first: list[tuple[date, date]],
) -> list[str]:
    """
    x축 라벨(과거→최근): 전 버킷 `YY.MM~YY.MM` 기간형으로 통일.
    `_stats_reference_date` 는 호출 시그니처 하위 호환용(미사용).
    """
    return [
        f"{bs.year % 100:02d}.{bs.month:02d}~{be.year % 100:02d}.{be.month:02d}"
        for bs, be in bucket_pairs_old_first
    ]
