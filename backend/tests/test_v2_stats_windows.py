"""롤링 버킷 — pipeline 과 backend 공유 규칙."""

from datetime import date

from app.v2_stats_windows import iter_rolling_year_buckets_old_first, period_bounds_for_window


def test_rolling_buckets_count_matches_window():
    as_of = date(2026, 5, 1)
    _, period_end = period_bounds_for_window(as_of, 5)
    buckets = iter_rolling_year_buckets_old_first(period_end, 5)
    assert len(buckets) == 5
    assert buckets[0][2] == 1
    assert buckets[-1][2] == 5
    assert buckets[0][0] <= buckets[0][1]
    assert buckets[-1][1] == period_end
