"""오피스텔 저층=100 비율. 가격 원자료 없음."""
from __future__ import annotations

from app.officetel_floor_lab.ratio import (
    compare_assets,
    phase2_open,
    rows_to_buildings,
    summarize_asset,
    weighted_median,
)
import numpy as np


def _bin(building_key, max_floor, bin_name, n_bin, med):
    return {
        "building_key": building_key,
        "max_floor": max_floor,
        "bin": bin_name,
        "n_bin": n_bin,
        "med": med,
    }


def test_low_100_profile_and_thin_top_dropped():
    rows = []
    for name, med in (("low", 1000), ("mid", 1050), ("high", 1090), ("top", 1070), ("f1", 900)):
        rows.append(_bin("a", 10, name, 10, med))
    rows.append(_bin("b", 30, "low", 20, 1000))
    rows.append(_bin("b", 30, "mid", 20, 1100))
    rows.append(_bin("b", 30, "high", 20, 1200))
    rows.append(_bin("b", 30, "top", 2, 1300))
    buildings = rows_to_buildings(rows)
    by_key = {b["building_key"]: b for b in buildings}
    assert by_key["a"]["idx_mid"] == 105
    assert by_key["a"]["idx_high"] == 109
    assert by_key["a"]["idx_top"] == 107
    assert round(by_key["a"]["idx_top_over_high"], 2) == round(100 * 1070 / 1090, 2)
    assert by_key["b"]["idx_top"] is None
    assert by_key["b"]["idx_high"] == 120
    assert "med" not in by_key["a"]


def test_weighted_median_puts_mass_on_the_larger_building():
    values = np.array([100.0, 130.0])
    weights = np.array([10.0, 90.0])
    assert weighted_median(values, weights) == 130.0


def test_ge26_top_stays_closed_and_phase2_needs_two_bands():
    def asset(gap_bin: str, gap_eq: float, gap_w: float):
        cells = []
        for band in ("le15", "m16_25", "ge26"):
            for name in ("mid", "high", "top", "top_over_high"):
                cells.append(
                    {
                        "band": band,
                        "band_label": band,
                        "bin": name,
                        "bin_label": name,
                        "n": 20 if band == "ge26" and name.startswith("top") else 100,
                        "equal": gap_eq if name == gap_bin else 100,
                        "weighted": gap_w if name == gap_bin else 100,
                    }
                )
        return {"cells": cells}

    rows = compare_assets(asset("high", 120, 121), asset("high", 100, 100))
    flags = {(r["band"], r["bin"]): r["flag"] for r in rows}
    assert flags[("ge26", "top")] == "closed"
    assert flags[("ge26", "top_over_high")] == "closed"
    assert flags[("le15", "high")] == "notable"
    assert flags[("m16_25", "high")] == "notable"
    assert "high" in phase2_open(rows)
    assert "top" not in phase2_open(rows)


def test_one_weight_over_10_is_not_notable():
    off = summarize_asset(
        [
            {"building_key": f"o{i}", "max_floor": 10, "band": "le15", "n": 50, "n_low": 10,
             "n_mid": 10, "n_high": 10, "n_top": 10,
             "idx_mid": 110, "idx_high": 112, "idx_top": 108, "idx_top_over_high": 96}
            for i in range(30)
        ]
    )
    apt = summarize_asset(
        [
            {
                "building_key": f"a{i}",
                "max_floor": 10,
                "band": "le15",
                "n": 5000 if i == 0 else 50,
                "n_low": 10,
                "n_high": 10,
                "n_mid": 10,
                "n_top": 10,
                "idx_mid": 108,
                "idx_high": 112 if i == 0 else 100,
                "idx_top": 107,
                "idx_top_over_high": 99,
            }
            for i in range(30)
        ]
    )
    compared = compare_assets(off, apt)
    high = next(r for r in compared if r["band"] == "le15" and r["bin"] == "high")
    assert high["flag"] == "record"
    assert abs(high["diff_equal"]) >= 10
    assert abs(high["diff_weighted"]) < 10
