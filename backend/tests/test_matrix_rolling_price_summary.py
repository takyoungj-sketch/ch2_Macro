"""롤링 구간 단가 요약: 평균과 같은 목록의 선형 25%·중앙값·75%."""

from app.routers.paid import bucket_unit_price_summary, sample_price_box


def test_bucket_summary_empty():
    assert bucket_unit_price_summary([]) == (None, None, None, None)


def test_bucket_summary_single_trade():
    assert bucket_unit_price_summary([7.0]) == (7.0, 7.0, 7.0, 7.0)


def test_bucket_summary_linear_percentiles_match_mean():
    mean, p25, med, p75 = bucket_unit_price_summary([10, 20, 30, 40, 50])
    assert (mean, p25, med, p75) == (30.0, 20.0, 30.0, 40.0)


def test_sample_price_box_matches_linear_percentiles():
    assert sample_price_box([10, 20, 30, 40, 50]) == (10.0, 20.0, 30.0, 40.0, 50.0)


def test_sample_price_box_single_trade():
    assert sample_price_box([7.0]) == (7.0, 7.0, 7.0, 7.0, 7.0)
