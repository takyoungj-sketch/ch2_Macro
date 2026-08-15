import pytest

from app.rent.sangkwon_query import excel_sido
from app.rent.sangkwon_agg import (
    MAIN_METRICS,
    SKIP_SHEETS,
    annual_value,
    compound_annual,
    is_aggregate_name,
    metric_from_item,
    parse_quarter_header,
)


def test_skip_office_seoul_scale_sheets():
    assert "104" in SKIP_SHEETS
    assert "106" in SKIP_SHEETS
    assert "103" not in SKIP_SHEETS
    assert "105" not in SKIP_SHEETS
    assert "109" not in SKIP_SHEETS


def test_aggregate_names():
    assert is_aggregate_name("합계")
    assert is_aggregate_name("계")
    assert is_aggregate_name("소계(도심지역)")
    assert not is_aggregate_name("광화문")


def test_metric_from_item():
    assert metric_from_item("동수(동)") == "building_count"
    assert metric_from_item("호수(호)") == "building_count"
    assert metric_from_item("임대가격지수(2024.2Q=100)") == "rent_index"
    assert metric_from_item("임대료(천원/㎡)") == "rent"
    assert metric_from_item("층별임대료(천원/㎡)") == "floor_rent"
    assert metric_from_item("순영업소득(%)") == "noi_pct"
    assert metric_from_item("순영업소득(천원/㎡)") == "noi_per_m2"
    assert metric_from_item("임대수입(%)") == "rent_income_share"
    assert metric_from_item("기타수입(%)") == "other_income_share"
    assert metric_from_item("운영경비(%)") == "opex_share"


def test_main_metrics_group_order():
    assert MAIN_METRICS[:3] == ("building_count", "avg_floors", "avg_area")
    assert MAIN_METRICS[3:6] == ("rent", "rent_index", "noi_per_m2")
    assert "vacancy" in MAIN_METRICS
    assert MAIN_METRICS.index("vacancy") > MAIN_METRICS.index("noi_pct")
    assert MAIN_METRICS[-1] == "conversion"


def test_quarter_header():
    assert parse_quarter_header("2013.1Q") == (2013, 1)
    assert parse_quarter_header("2025.4Q") == (2025, 4)
    assert parse_quarter_header("구분") is None


def test_annual_rent_is_mean_times_12_in_manwon():
    # 월 단가 천원/㎡ → 연간 만원/㎡ = 평균×12÷10
    got = annual_value("rent", {1: 10, 2: 11, 3: 12, 4: 13})
    assert got is not None
    assert abs(got - 13.8) < 1e-9
    assert annual_value("rent", {1: 10, 2: 11, 3: 12}) is None
    assert annual_value("floor_rent", {1: 1, 2: 1, 3: 1, 4: 1}) == pytest.approx(1.2)


def test_gwanghwamun_2025_small_retail_annual():
    rent = annual_value("rent", {1: 91.4, 2: 91.3, 3: 91.4, 4: 91.6})
    noi = annual_value("noi_per_m2", {1: 210.9, 2: 209.8, 3: 123.8, 4: 209.9})
    noi_pct = annual_value("noi_pct", {1: 93.6, 2: 93.6, 3: 55.7, 4: 93.6})
    assert rent is not None and abs(rent - 109.71) < 1e-9
    assert noi is not None and abs(noi - 75.44) < 1e-9
    assert noi_pct is not None and abs(noi_pct - 84.125) < 1e-9


def test_compound_yield_matches_reb_product():
    assert compound_annual({1: 1.0, 2: 1.0, 3: 1.0, 4: 1.0}) == ((1.01**4) - 1) * 100
    assert annual_value("income_yield", {1: 1.0, 2: 1.0, 3: 1.0}) is None
    got = annual_value("investment_yield", {1: 2.0, 2: -1.0, 3: 1.5, 4: 0.5})
    expect = (1.02 * 0.99 * 1.015 * 1.005 - 1) * 100
    assert got is not None and abs(got - expect) < 1e-9


def test_excel_sido_aliases():
    assert excel_sido("충청북도") == "충북"
    assert excel_sido("충청남도") == "충남"
    assert excel_sido("서울특별시") == "서울"


def test_annual_vacancy_mean_and_stock_last():
    assert annual_value("vacancy", {1: 8, 2: 10, 3: 12, 4: 6}) == 9
    assert annual_value("building_count", {1: 10, 2: 11, 3: 12, 4: 13}) == 13
    assert annual_value("avg_floors", {1: 9.0, 2: None, 3: None, 4: None}) == 9.0
