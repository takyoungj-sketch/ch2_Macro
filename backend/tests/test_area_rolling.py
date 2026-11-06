"""롤링 면적형 눈금. DB 없이 반올림과 구간 묶음만 확인한다."""

from datetime import date

from app.collective.area_rolling import (
    build_area_series,
    commercial_area_rule,
    commercial_area_type,
    residential_area_type,
)
from app.product_gate import needs_macro


def test_residential_area_rounds_to_5():
    assert residential_area_type(84.97) == ("85㎡", 85)
    assert residential_area_type(59.96) == ("60㎡", 60)
    assert residential_area_type(74.2) == ("75㎡", 75)
    assert residential_area_type(49.0) == ("50㎡", 50)
    assert residential_area_type(101.2) == ("100㎡", 100)
    assert residential_area_type(82.5) == ("85㎡", 85)
    assert residential_area_type(2.4) is None
    assert residential_area_type(0) is None
    assert residential_area_type(None) is None


def test_commercial_area_uses_utility_bands():
    assert commercial_area_type("collective_shop", 42) == ("35~50㎡", 35)
    assert commercial_area_type("collective_factory", 42) == ("100㎡ 미만", 0)
    assert commercial_area_type("collective_shop", 0) is None
    assert commercial_area_type("apartment", 80) is None
    assert "5㎡ 단위" not in commercial_area_rule({"collective_shop"})
    assert "1000㎡" in commercial_area_rule({"collective_factory"})


def test_series_keeps_one_trade_and_skips_empty_bucket():
    buckets = [
        (date(2024, 1, 1), date(2024, 12, 31), 1),
        (date(2025, 1, 1), date(2025, 12, 31), 2),
    ]
    labeled = [
        (date(2024, 6, 1), 100.0, "85㎡", 85.0),
        (date(2024, 7, 1), 110.0, "60㎡", 60.0),
        (date(2025, 3, 1), 120.0, "85㎡", 85.0),
    ]
    series = build_area_series(labeled, buckets)
    by_label = {item["area_label"]: item for item in series}
    assert [item["area_label"] for item in series] == ["60㎡", "85㎡"]
    assert by_label["60㎡"]["points"][0]["count"] == 1
    assert by_label["60㎡"]["points"][0]["bucket_index"] == 1
    assert [point["bucket_index"] for point in by_label["85㎡"]["points"]] == [1, 2]
    assert by_label["85㎡"]["points"][0]["median"] == 100.0


def test_rolling_by_area_follows_the_five_year_gate():
    assert needs_macro(
        "GET",
        "/api/collective/buildings/abc/stats/rolling-by-area",
        {"window_years": "5"},
    ) is False
    assert needs_macro(
        "GET",
        "/api/collective/buildings/abc/stats/rolling-by-area",
        {"window_years": "3"},
    ) is True
    assert needs_macro(
        "GET",
        "/api/collective/commercial/clusters/abc/stats/rolling-by-area",
        {"window_years": "5"},
    ) is False
