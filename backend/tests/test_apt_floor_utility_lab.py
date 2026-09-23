"""아파트·오피스텔 층 효용 0차 — 칸·계층·게이트. 가격 없음."""
from __future__ import annotations

import numpy as np
import pandas as pd

from app.apt_floor_lab.fit import (
    _band_floor_columns,
    _floor_main_columns,
    _height_floor_columns,
    _region_floor_columns,
    fit_building_index,
    weighted_median,
)
from app.apt_floor_lab.screen import (
    build_screen_sql,
    experiment_floor_bin,
    height_band,
    is_eligible,
    place_name,
    region_tier,
    summarize,
)
from app.collective.regression.engine import relative_floor_group


def test_bins_match_product_relative_for_above_ground():
    assert experiment_floor_bin(1, 30) == "f1"
    assert experiment_floor_bin(30, 30) == "top"
    assert experiment_floor_bin(5, 30) == "low"
    assert experiment_floor_bin(15, 30) == "mid"
    assert experiment_floor_bin(25, 30) == "high"
    assert relative_floor_group(5, 30) == "floor_rel_low"
    assert relative_floor_group(15, 30) == "floor_rel_mid"
    assert relative_floor_group(25, 30) == "floor_rel_high"
    assert relative_floor_group(30, 30) == "floor_rel_top"


def test_basement_is_out_of_experiment_bins():
    assert experiment_floor_bin(0, 15) is None
    assert experiment_floor_bin(-1, 15) is None
    assert relative_floor_group(-1, 15) == "floor_rel_mid"


def test_region_cascade_keeps_gyeonggi_eup_in_metro():
    assert region_tier("경기도", "향남읍") == "metro"
    assert region_tier("서울특별시", "역삼동") == "metro"
    assert region_tier("부산광역시", "기장읍") == "metro_city"
    assert region_tier("충청북도", "가경동") == "other_urban"
    assert place_name("흥덕구", "가경동") == "가경동"
    assert region_tier("충청북도", place_name("흥덕구", "가경동")) == "other_urban"
    assert region_tier("충청북도", place_name("흥덕구", "강내면")) == "nonurban"
    assert region_tier("경기도", place_name("수지구", "풍덕천동")) == "metro"
    assert region_tier("충청북도", "강내면") == "nonurban"
    assert region_tier("세종특별자치시", "부강면") == "sejong"
    assert region_tier("전라북도", "모현동1가") == "other_urban"
    assert region_tier("전라북도", "") == "unknown"


def test_height_bands_are_labels_not_a_break():
    assert height_band(15) == "le15"
    assert height_band(16) == "m16_25"
    assert height_band(25) == "m16_25"
    assert height_band(26) == "ge26"


def test_gate_needs_first_floor_and_another_bin():
    assert is_eligible(n=50, n_1=5, n_low=0, n_mid=10, n_high=0, n_top=5, max_floor=15)
    assert not is_eligible(n=49, n_1=5, n_low=0, n_mid=10, n_high=0, n_top=5, max_floor=15)
    assert not is_eligible(n=80, n_1=4, n_low=0, n_mid=20, n_high=0, n_top=10, max_floor=15)
    assert not is_eligible(n=80, n_1=80, n_low=0, n_mid=0, n_high=0, n_top=0, max_floor=15)
    assert not is_eligible(n=80, n_1=10, n_low=0, n_mid=10, n_high=0, n_top=5, max_floor=1)


def test_summarize_closes_thin_nonurban_and_ignores_price():
    def row(tier: str, band: str, n: int = 60) -> dict:
        return {
            "eligible": True,
            "tier": tier,
            "band": band,
            "band_alt": "le20",
            "legal_kind": "dong",
            "n": n,
            "n_1": 10,
            "max_floor": 15,
        }

    rows = [row("metro", "le15") for _ in range(30)]
    rows.append(row("nonurban", "le15", n=55))
    out = summarize(rows)
    assert out["funnel"]["eligible"] == 31
    assert out["nonurban_open"] is False
    assert out["tiers"][0]["reportable"] is True
    nonurban = next(c for c in out["tiers"] if c["key"] == "nonurban")
    assert nonurban["reportable"] is False
    assert "unit_price" not in out


def test_screen_sql_does_not_aggregate_price_or_use_any():
    sql = build_screen_sql()
    upper = sql.upper()
    assert "ANY" not in upper
    assert "UNIT_PRICE" in upper
    assert "AVG" not in upper
    assert "PERCENTILE" not in upper
    assert "FLOOR >= 1" in upper
    assert "0.30" in sql
    assert "0.70" in sql


def test_building_index_is_top_over_first_floor_not_a_pooled_mean():
    n = 10
    floor = np.array([1] * n + [1] * n + [10] * n + [10] * n, dtype=float)
    area = np.full(n * 4, 84.0)
    year = np.array([2024] * n + [2025] * n + [2024] * n + [2025] * n)
    month = np.array([3] * n + [9] * n + [3] * n + [9] * n)
    price = np.array([100.0] * n + [110.0] * n + [110.0] * n + [121.0] * n)
    fitted = fit_building_index(floor, area, price, year, month, max_floor=10)
    assert fitted["ok"]
    assert abs(fitted["top"] - 110.0) < 0.05
    assert fitted["low"] is None


def test_thin_bin_does_not_join_the_first_floor():
    floor = np.array([1] * 10 + [2] * 4 + [20] * 10, dtype=float)
    area = np.full(24, 84.0)
    price = np.array([100.0] * 10 + [40.0] * 4 + [110.0] * 10)
    year = np.full(24, 2024)
    month = np.full(24, 5)
    fitted = fit_building_index(floor, area, price, year, month, max_floor=20)
    assert fitted["ok"]
    assert fitted["low"] is None
    assert abs(fitted["top"] - 110.0) < 0.05


def test_weighted_median_follows_trades_not_buildings():
    assert weighted_median(np.array([100.0, 100.0, 130.0]), np.array([1.0, 1.0, 10.0])) == 130.0


def test_joint_spec_has_interactions_only():
    work = pd.DataFrame(
        {
            "bin": ["f1", "top", "top"],
            "tier": ["metro", "nonurban", "metro"],
            "band": ["le15", "ge26", "m16_25"],
            "max_floor": [15.0, 30.0, 20.0],
        }
    )
    band_cols = _floor_main_columns(work) + _region_floor_columns(work) + _band_floor_columns(work)
    assert "d_top__nonurban" in band_cols
    assert "d_top__ge26" in band_cols
    assert "tier_nonurban" not in band_cols
    assert "d_top__h" not in band_cols
    height_cols = _height_floor_columns(work)
    assert "d_top__h" in height_cols
    assert "d_top__ge26" not in height_cols
