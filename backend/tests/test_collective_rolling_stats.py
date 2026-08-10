"""집합 롤링 버킷 — window_years 슬롯 수·3/5/7년 정렬."""

from datetime import date

from app.v2_stats_windows import iter_rolling_year_buckets_old_first, period_bounds_for_window


def _bucket_slots(as_of: date, window_years: int) -> list[tuple[date, date, int]]:
    _, period_end = period_bounds_for_window(as_of, window_years)
    return iter_rolling_year_buckets_old_first(period_end, window_years)


def test_rolling_slots_count_3_vs_5_and_7():
    as_of = date(2026, 5, 1)
    _, end = period_bounds_for_window(as_of, 5)
    assert len(_bucket_slots(as_of, 3)) == 3
    assert len(_bucket_slots(as_of, 5)) == 5
    assert len(_bucket_slots(as_of, 7)) == 7
    assert len(iter_rolling_year_buckets_old_first(end, 5)) == 5
    assert len(iter_rolling_year_buckets_old_first(end, 7)) == 7


def test_five_year_tail_buckets_align_with_three_year_window():
    as_of = date(2026, 5, 1)
    slots3 = _bucket_slots(as_of, 3)
    slots5 = _bucket_slots(as_of, 5)
    assert slots3[-1][:2] == slots5[-1][:2]
    assert slots3[0][:2] == slots5[-3][:2]


def test_seven_year_window_extends_five_year_tail():
    as_of = date(2026, 5, 1)
    slots5 = _bucket_slots(as_of, 5)
    slots7 = _bucket_slots(as_of, 7)
    assert slots5[-1][:2] == slots7[-1][:2]
    assert slots5[0][:2] == slots7[-5][:2]
    assert len(slots7) - len(slots5) == 2
