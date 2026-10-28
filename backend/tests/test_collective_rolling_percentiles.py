"""집합 롤링 분위수와 히스토그램 박스는 같은 목록에서 계산한다."""

from datetime import date

from app.stats_utils import attach_rolling_percentiles, histogram_box_fields


def test_attach_keeps_prices_inside_the_span():
    points = [
        {
            "period_start": date(2021, 10, 1),
            "period_end": date(2022, 9, 30),
        }
    ]
    dated = [
        (date(2021, 9, 30), 1.0),
        (date(2021, 10, 1), 10.0),
        (date(2022, 1, 1), 20.0),
        (date(2022, 6, 1), 30.0),
        (date(2022, 8, 1), 40.0),
        (date(2022, 9, 30), 50.0),
        (date(2022, 10, 1), 99.0),
    ]
    attach_rolling_percentiles(points, dated)
    assert points[0]["p25"] == 20.0
    assert points[0]["median"] == 30.0
    assert points[0]["p75"] == 40.0


def test_attach_skips_empty_span():
    points = [{"period_start": "2020-01-01", "period_end": "2020-12-31"}]
    attach_rolling_percentiles(points, [(date(2021, 1, 1), 10.0)])
    assert "median" not in points[0]


def test_histogram_box_matches_the_sample():
    box = histogram_box_fields([10, 20, 30, 40, 50])
    assert box == {
        "min_unit_price": 10.0,
        "p25_unit_price": 20.0,
        "median_unit_price": 30.0,
        "p75_unit_price": 40.0,
        "max_unit_price": 50.0,
    }


def test_histogram_box_collapses_a_single_price():
    box = histogram_box_fields([7.0])
    assert box["min_unit_price"] == box["p25_unit_price"] == box["median_unit_price"]
    assert box["median_unit_price"] == box["p75_unit_price"] == box["max_unit_price"] == 7.0
