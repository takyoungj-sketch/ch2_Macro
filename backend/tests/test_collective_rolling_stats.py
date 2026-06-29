"""집합 롤링 버킷 — window_years 슬롯 수·빈 버킷 보존."""

from datetime import date

from app.collective.building_stats_query import (
    _merge_rolling_points,
    _rolling_bucket_slots,
)
from app.v2_stats_windows import iter_rolling_year_buckets_old_first, period_bounds_for_window


def test_rolling_slots_count_3_vs_5():
    as_of = date(2026, 5, 1)
    _, end = period_bounds_for_window(as_of, 5)
    assert len(_rolling_bucket_slots(as_of, 3)) == 3
    assert len(_rolling_bucket_slots(as_of, 5)) == 5
    assert len(iter_rolling_year_buckets_old_first(end, 5)) == 5


def test_merge_rolling_points_pads_empty_buckets():
    slots = _rolling_bucket_slots(date(2026, 5, 1), 5)
    filled = {
        3: {
            "bucket_index": 3,
            "period_start": "x",
            "period_end": "y",
            "label": "a",
            "count": 10,
            "mean": 100.0,
        },
        5: {
            "bucket_index": 5,
            "period_start": "p",
            "period_end": "q",
            "label": "b",
            "count": 5,
            "mean": 200.0,
        },
    }
    points = _merge_rolling_points(slots, filled)
    assert len(points) == 5
    assert points[0]["count"] == 0 and points[0]["mean"] is None
    assert points[2]["count"] == 10
    assert points[4]["count"] == 5


def test_five_year_tail_buckets_align_with_three_year_window():
    as_of = date(2026, 5, 1)
    slots3 = _rolling_bucket_slots(as_of, 3)
    slots5 = _rolling_bucket_slots(as_of, 5)
    assert slots3[-1][:2] == slots5[-1][:2]
    assert slots3[0][:2] == slots5[-3][:2]
