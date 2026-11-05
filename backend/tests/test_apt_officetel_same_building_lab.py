"""같은 지번 아파트·오피스텔 가격비율 실험의 분류·매칭 문턱."""

import numpy as np
import pandas as pd

from app.collective.apt_officetel_same_building_lab import (
    STOP_MIN_PAIRS,
    assign_floor_bands,
    classify_title_years,
    classify_years,
    distribution,
    fit_pair_percent,
    floors_within_20,
    match_trades,
    match_trades_window,
    open_pnu,
    pair_ratio,
    prepare_trades,
    sign_flipped,
    stage1,
    strict_summary,
    stratum_of,
    vintage_of,
)


def test_year_gap_classifies_without_dong_names():
    assert classify_years(1, 1, 2010, 2011) == "same_building"
    assert classify_years(1, 1, 2010, 2010) == "same_building"
    assert classify_years(1, 1, 2010, 2012) == "different_building"
    assert classify_years(1, 1, None, 2010) == "year_unknown"
    assert classify_years(1, 1, 2010, None) == "year_unknown"
    assert classify_years(2, 1, 2010, 2010) == "multi_key"


def test_floor_number_is_not_the_band():
    frame = pd.DataFrame(
        {
            "building_key": ["apt"] * 3 + ["off"] * 3,
            "asset_type": ["apartment"] * 3 + ["officetel"] * 3,
            "price": [6000.0] * 6,
            "area": [60.0] * 6,
            "floor": [1, 2, 15, 15, 20, 30],
            "contract_date": ["2024-06-01"] * 6,
            "dong": ["101"] * 3 + ["201"] * 3,
            "bj": ["1111010100"] * 6,
            "lot": ["1"] * 6,
            "addr1": ["서울특별시"] * 6,
            "addr2": ["강남구"] * 6,
        }
    )
    out = prepare_trades(frame)
    apt15 = out[(out.building_key == "apt") & (out.floor == 15)].iloc[0].band
    off15 = out[(out.building_key == "off") & (out.floor == 15)].iloc[0].band
    assert apt15 == "high"
    assert off15 == "low"
    apt = out[out.building_key == "apt"]
    off_low = out[(out.building_key == "off") & (out.floor == 15)]
    _, _, reuse_low = match_trades(apt, off_low, area_lo=0.85, area_hi=1.15, time_col="year", floor_mode="band")
    assert apt.loc[reuse_low > 0, "floor"].tolist() == [1]
    off_high = out[(out.building_key == "off") & (out.floor == 30)]
    _, _, reuse_high = match_trades(apt, off_high, area_lo=0.85, area_hi=1.15, time_col="year", floor_mode="band")
    assert apt.loc[reuse_high > 0, "floor"].tolist() == [15]


def test_area_ratio_bounds_are_inclusive():
    apt = pd.DataFrame({"area": [100.0], "year": [2024], "band": ["mid"], "floor": [5.0], "unit": [10.0]})
    on_edge = pd.DataFrame({"area": [85.0], "year": [2024], "band": ["mid"], "floor": [8.0], "unit": [8.0]})
    inside_hi = pd.DataFrame({"area": [115.0], "year": [2024], "band": ["mid"], "floor": [1.0], "unit": [8.0]})
    outside = pd.DataFrame({"area": [84.9], "year": [2024], "band": ["mid"], "floor": [8.0], "unit": [8.0]})
    used_a, used_o, _ = match_trades(apt, on_edge, area_lo=0.85, area_hi=1.15, time_col="year", floor_mode="band")
    assert used_a[0] and used_o[0]
    _, used_hi, _ = match_trades(apt, inside_hi, area_lo=0.85, area_hi=1.15, time_col="year", floor_mode="band")
    assert used_hi[0]
    _, used_out, _ = match_trades(apt, outside, area_lo=0.85, area_hi=1.15, time_col="year", floor_mode="band")
    assert not used_out[0]


def test_apartment_trade_reuse_flag():
    apt = pd.DataFrame(
        {"area": [50.0] * 10, "year": [2024] * 10, "band": ["mid"] * 10, "floor": [3.0] * 10, "unit": [10.0] * 10}
    )
    off = pd.DataFrame(
        {"area": [50.0] * 10, "year": [2024] * 10, "band": ["mid"] * 10, "floor": [9.0] * 10, "unit": [8.0] * 10}
    )
    apt_used, off_used, reuse = match_trades(apt, off, area_lo=0.85, area_hi=1.15, time_col="year", floor_mode="band")
    result = pair_ratio(apt, off, apt_used, off_used, reuse)
    assert result["reuse_flag"] is True
    assert result["ratio"] == 0.8
    apt2 = apt.copy()
    apt2["year"] = list(range(2015, 2025))
    off2 = off.copy()
    off2["year"] = list(range(2015, 2025))
    apt_used, off_used, reuse = match_trades(apt2, off2, area_lo=0.85, area_hi=1.15, time_col="year", floor_mode="band")
    paired = pair_ratio(apt2, off2, apt_used, off_used, reuse)
    assert paired["reuse_flag"] is False
    assert paired["median_reuse"] == 1


def test_cell_under_15_hides_median_and_middle_vintage_is_count_only():
    thin = distribution([0.8] * 14, min_n=15)
    assert thin["n"] == 14 and thin["median"] is None
    enough = distribution([0.8] * 15, min_n=15)
    assert enough["median"] == 0.8
    middle = distribution([0.8] * 20, force_count_only=True)
    assert middle["n"] == 20 and middle["median"] is None


def test_sign_and_floor_and_place_rules():
    assert sign_flipped(0.9, 1.1) is True
    assert sign_flipped(0.9, 0.8) is False
    assert sign_flipped(1.0, 0.8) is False
    assert floors_within_20(10, 12.5) is True
    assert floors_within_20(10, 13) is False
    assert floors_within_20(None, 10) is False
    assert stratum_of("서울특별시", "강남구") == "서울"
    assert stratum_of("광주광역시", "서구") == "광역시"
    assert stratum_of("경기도", "수원시") == "시"
    assert stratum_of("강원특별자치도", "홍천군") == "군"
    assert stratum_of("세종특별자치시", "") == "시"
    assert vintage_of(2024, 2026) == "5년 이하"
    assert vintage_of(2020, 2026) == "그 밖"
    assert vintage_of(2000, 2026) == "20년 이상"
    assert vintage_of(2027, 2026) == "그 밖"
    assert vintage_of(None, 2026) == "그 밖"


def test_stop_rule_stays_at_30():
    assert STOP_MIN_PAIRS == 30
    rows = pd.DataFrame(
        {
            "klass": ["same_building"],
            "n_apt": [20],
            "n_off": [20],
            "kapt_same_pnu": [False],
            "apt_key": ["a"],
            "off_key": ["o"],
        }
    )
    assert stage1(rows, pd.DataFrame(), 29)["stop"] is True
    assert stage1(rows, pd.DataFrame(), 30)["stop"] is False


def test_pair_regression_recovers_price_gap():
    area = np.linspace(40, 80, 20)
    year = np.array([2022] * 10 + [2024] * 10)
    frame = pd.concat(
        [
            pd.DataFrame({"area": area, "year": year, "band": "mid", "officetel": 0.0}),
            pd.DataFrame({"area": area, "year": year, "band": "mid", "officetel": 1.0}),
        ],
        ignore_index=True,
    )
    frame["price"] = np.where(frame["officetel"] == 1, 80.0, 100.0) * frame["area"]
    fitted = fit_pair_percent(frame)
    assert fitted["ok"] is True
    assert fitted["cov"] == "HC3"
    assert abs(fitted["percent"] - (-20)) < 0.05


def test_tied_floors_share_one_band():
    bands = assign_floor_bands(pd.Series([5, 5, 5]))
    assert set(bands.tolist()) == {"mid"}


def test_strict_window_keeps_area_and_92_days_together():
    apt = pd.DataFrame({"area": [50.0], "band": ["mid"], "date_ord": [10_000], "floor": [3.0], "unit": [10.0]})
    near = pd.DataFrame({"area": [45.0], "band": ["mid"], "date_ord": [10_092], "floor": [8.0], "unit": [8.0]})
    far = pd.DataFrame({"area": [45.0], "band": ["mid"], "date_ord": [10_093], "floor": [8.0], "unit": [8.0]})
    small = pd.DataFrame({"area": [44.0], "band": ["mid"], "date_ord": [10_010], "floor": [8.0], "unit": [8.0]})
    other_band = pd.DataFrame({"area": [50.0], "band": ["low"], "date_ord": [10_010], "floor": [1.0], "unit": [8.0]})
    _, used_near, _ = match_trades_window(apt, near, area_lo=0.90, area_hi=1.10, window_days=92)
    _, used_far, _ = match_trades_window(apt, far, area_lo=0.90, area_hi=1.10, window_days=92)
    _, used_small, _ = match_trades_window(apt, small, area_lo=0.90, area_hi=1.10, window_days=92)
    _, used_band, _ = match_trades_window(apt, other_band, area_lo=0.90, area_hi=1.10, window_days=92)
    assert used_near[0]
    assert not used_far[0]
    assert not used_small[0]
    assert not used_band[0]


def test_strict_under_30_hides_the_median():
    rows = [{"pair_id": f"p{i}", "ratio": 0.5} for i in range(29)]
    summary = strict_summary(rows, 0.62, set())
    assert summary["pass_n"] == 29
    assert summary["distribution"]["median"] is None
    assert summary["replaces_headline"] is False


def test_open_lot_and_title_year_cluster():
    assert open_pnu("1111010100", "12-3") == "1111010100100120003"
    assert open_pnu("1111010100", "산12") == "1111010100200120000"
    assert open_pnu("1111010100", "12*") is None
    assert open_pnu("1111010100", "12345-1") is None
    assert classify_title_years([2010, 2011], 2010, 2011) == "verified"
    assert classify_title_years([2010], 2010, 2011) == "verified"
    assert classify_title_years([2009, 2012], 2010, 2011) == "ambiguous"
    assert classify_title_years([2000], 2010, 2011) == "year_miss"
    assert classify_title_years([], 2010, 2011) == "no_title_year"
