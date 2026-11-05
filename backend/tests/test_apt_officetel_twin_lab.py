"""아파트·오피스텔 거리 결합. DB 없음."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.collective.regional_regression.apt_officetel_twin_lab import (
    W_CAP,
    anchor_weight,
    combine_distances,
    rank_joint_twins,
)
from app.collective.regional_regression.apt_twin_lab import PRICE_DIST_COLS, STRUCT_COLS, rank_display_twins


def _row(**overrides: float) -> dict[str, float]:
    base = {col: 0.0 for col in STRUCT_COLS + PRICE_DIST_COLS}
    base["n_complexes"] = 25
    base.update(overrides)
    return base


def _off(**overrides: float) -> dict[str, float]:
    base = {
        "n_complexes": 8,
        "n_tx": 40,
        "age_median": 10,
        "age_iqr": 4,
        "floor_median": 15,
        "floor_iqr": 3,
    }
    base.update(overrides)
    return base


def test_share_weight_uses_anchor_counts_and_caps_at_half():
    assert anchor_weight(100, 10, "share") == pytest.approx(10 / 110)
    assert anchor_weight(10, 100, "share") == W_CAP
    assert anchor_weight(100, 10, "half") == 0.5
    assert anchor_weight(100, 10, "sqrt") == pytest.approx(np.sqrt(10) / (10 + np.sqrt(10)))
    assert anchor_weight(100, 10, "apartment") == 0.0


def test_missing_officetel_distance_keeps_apartment_score():
    d_apt = pd.Series([1.0, 3.0, 2.0], index=list("abc"))
    d_off = pd.Series([5.0, np.nan, 0.0], index=list("abc"))
    mixed = combine_distances(d_apt, d_off, 0.5)
    z_apt = (d_apt - d_apt.mean()) / d_apt.std(ddof=0)
    assert mixed["b"] == pytest.approx(z_apt["b"])
    assert mixed["a"] != pytest.approx(z_apt["a"])


def test_zero_weight_matches_product_rank():
    frame = pd.DataFrame(
        [
            _row(age_median=0, price_p50=0),
            _row(age_median=1, price_p50=60),
            _row(age_median=2, price_p50=50),
            _row(age_median=3, price_p50=40),
            _row(age_median=4, price_p50=30),
            _row(age_median=5, price_p50=20),
            _row(age_median=6, price_p50=10),
        ],
        index=list("ABCDEFG"),
    )
    off = pd.DataFrame([_off(age_median=float(i)) for i in range(len(frame))], index=frame.index)
    assert rank_joint_twins(frame, off, "A", w=0.0) == rank_display_twins(frame, "A", keep=5)


def test_zero_floor_is_excluded_from_officetel_twin_eligibility():
    from app.collective.regional_regression.apt_officetel_twin_lab import OFF_VARS, _null_nonpositive_scale
    from app.collective.regional_regression.engine import _eligible_mask

    df = pd.DataFrame({
        "median": [100.0] * 20,
        "households": [10.0] * 20,
        "max_floor": [0.0] + [12.0] * 19,
        "building_age": [8.0] * 20,
        "assessed_land_price": [1000.0] * 20,
        "n_tx": [6] * 20,
        "match_tier": ["T"] * 20,
        "match_rule": [""] * 20,
        "asset_type": ["officetel"] * 20,
    })
    assert int(_eligible_mask(df, OFF_VARS, min_tx=5).sum()) == 20
    _null_nonpositive_scale(df)
    assert int(_eligible_mask(df, OFF_VARS, min_tx=5).sum()) == 19


def test_officetel_national_cache_loads_the_frame_once(monkeypatch):
    from datetime import date

    from app.collective.regional_regression import apt_officetel_twin_lab as lab

    lab._OFF_TWIN_CACHE.clear()
    calls = {"n": 0}

    def load(_conn):
        calls["n"] += 1
        df = pd.DataFrame({
            "region_id": ["1168010100"],
            "label": ["서울특별시 강남구 역삼동"],
            "addr1": ["서울특별시"],
            "addr2": ["강남구"],
            "addr4": ["역삼동"],
            "median": [100.0],
            "households": [10.0],
            "max_floor": [12.0],
            "building_age": [8.0],
            "assessed_land_price": [1000.0],
            "n_tx": [6],
            "match_tier": ["T"],
            "match_rule": [""],
            "asset_type": ["officetel"],
        })
        return df, {"as_of_label": "2026년 10월 말 기준", "snapshot_ym": "202610"}

    monkeypatch.setattr(lab, "load_officetel_frame", load)
    monkeypatch.setattr(lab, "latest_mart_snapshot", lambda _conn: (date(2026, 10, 31), {}))
    monkeypatch.setattr(lab, "_latest_snapshot_ym", lambda _conn: "202610")
    monkeypatch.setattr(lab, "_fill_eup_names", lambda _conn, _df: None)
    lab._officetel_twin_national(None)
    lab._officetel_twin_national(None)
    assert calls["n"] == 1
    lab._OFF_TWIN_CACHE.clear()
