"""집합 지역회귀 — 단지 그레인 OLS 단위 테스트 (DB 없음)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from app.collective.regional_regression.engine import (
    MIN_FIT_N,
    MIN_TX,
    WEIGHT_N0,
    _asset_type_ref,
    _collapse_dummy,
    _design,
    _eligible_mask,
    _fit_ols,
    _flags,
    _is_usable_tier,
    _split_hold,
    _tx_weights,
    build_sample_funnel,
)
from app.collective.regional_regression.schemas import RegionalRegressionVariables


def test_flags_split_csv():
    assert _flags("hh_zero,scale_inconsistent") == {"hh_zero", "scale_inconsistent"}
    assert _flags(None) == set()
    assert _flags(np.nan) == set()


def test_collapse_dummy_merges_rare():
    s = pd.Series(["철근"] * 10 + ["벽돌"] * 2 + ["목"] * 1)
    out = _collapse_dummy(s, min_n=5)
    assert (out == "철근").sum() == 10
    assert (out == "기타").sum() == 3


def test_eligible_mask_requires_usable_tier_and_selected_cols():
    df = pd.DataFrame(
        {
            "median": [800, 900, 0, 850],
            "match_tier": ["A", "Z", "A", "C"],
            "households": [200, 180, 90, np.nan],
            "max_floor": [15, 12, 10, 11],
            "building_age": [10, 8, 5, 7],
            "parking_per_household": [1.1, 1.0, 0.9, 1.2],
            "n_tx": [10, 10, 10, 10],
            "asset_type": ["apartment"] * 4,
        }
    )
    v = RegionalRegressionVariables()
    m = _eligible_mask(df, v)
    assert m.tolist() == [True, False, False, False]


def test_eligible_mask_drops_thin_tx():
    df = pd.DataFrame(
        {
            "median": [800, 900],
            "match_tier": ["A", "A"],
            "households": [200, 180],
            "max_floor": [15, 12],
            "building_age": [10, 8],
            "parking_per_household": [1.1, 1.0],
            "n_tx": [4, 5],
            "asset_type": ["apartment", "apartment"],
        }
    )
    v = RegionalRegressionVariables()
    assert _eligible_mask(df, v).tolist() == [False, True]


def test_rowhouse_title_tier_is_usable_apartment_t_is_not():
    assert _is_usable_tier("apartment", "T") is False
    assert _is_usable_tier("apartment", "A") is True
    assert _is_usable_tier("apartment", "D") is True
    assert _is_usable_tier("apartment", "F") is True
    assert _is_usable_tier("apartment", "E") is False
    assert _is_usable_tier("rowhouse", "T") is True
    assert _is_usable_tier("officetel", "T") is True
    assert _is_usable_tier("rowhouse", "Z") is False


def test_fit_ols_recovers_scale_signal():
    rng = np.random.default_rng(0)
    n = 80
    hh = rng.uniform(50, 800, n)
    age = rng.uniform(1, 30, n)
    y = np.exp(6.7 + 0.0004 * hh - 0.01 * age + rng.normal(0, 0.05, n))
    work = pd.DataFrame({"median": y, "households": hh, "building_age": age})
    x = pd.DataFrame({"households": hh, "building_age": age})
    train_idx = work.index[:60]
    hold_idx = work.index[60:]
    fit = _fit_ols(work, x, model_type="log", train_idx=train_idx, hold_idx=hold_idx)
    assert fit is not None
    assert fit["n"] >= MIN_FIT_N
    assert fit["adj_r_squared"] is not None and fit["adj_r_squared"] > 0.5
    assert fit["hold_mape"] is not None
    names = {c.name for c in fit["coefficients"]}
    assert "households" in names and "building_age" in names


def test_design_structure_dummies_drop_reference():
    work = pd.DataFrame(
        {
            "households": [100] * 14,
            "structure_group": ["철근콘크리트"] * 8 + ["벽돌"] * 6,
        }
    )
    v = RegionalRegressionVariables(
        households=True,
        max_floor=False,
        building_age=False,
        parking=False,
        structure=True,
        builder=False,
    )
    x, labels, _warn = _design(work, v)
    dummy_cols = [c for c in x.columns if c.startswith("struct_")]
    assert dummy_cols == ["struct_벽돌"]
    assert labels["_struct_ref"] == "철근콘크리트"
    assert "struct_철근콘크리트" not in x.columns


def test_design_builder_ref_is_most_frequent():
    work = pd.DataFrame(
        {
            "households": [100] * 19,
            "builder_group": ["현대"] * 8 + ["계룡"] * 6 + ["한화"] * 5,
        }
    )
    v = RegionalRegressionVariables(
        households=True,
        max_floor=False,
        building_age=False,
        parking=False,
        structure=False,
        builder=True,
    )
    x, labels, _warn = _design(work, v)
    assert labels["_builder_ref"] == "현대"
    assert "builder_현대" not in x.columns
    assert "builder_계룡" in x.columns and "builder_한화" in x.columns


def test_pick_dummy_ref_tie_breaks_alphabetically():
    from app.collective.regional_regression.engine import _pick_dummy_ref

    s = pd.Series(["금성"] * 4 + ["계룡"] * 4)
    assert _pick_dummy_ref(s) == "계룡"


def _funnel_frame() -> pd.DataFrame:
    """12단지: 적합 5 · 변수 탈락 4(한 행 한 사유) · 매칭 탈락 3."""
    n = 12
    df = pd.DataFrame(
        {
            "median": [800.0] * n,
            "match_tier": ["A"] * 9 + ["E", "Z", None],
            "households": [200.0] * n,
            "max_floor": [15.0] * n,
            "building_age": [10.0] * n,
            "parking_per_household": [1.1] * n,
            "structure_group": ["RC"] * n,
            "builder_group": ["한화"] * n,
            "quality_flags": [set() for _ in range(n)],
            "attr_quality_flags": [None] * n,
            "n_tx": [10] * n,
            "asset_type": ["apartment"] * n,
        }
    )
    df.at[5, "households"] = np.nan
    df.at[6, "max_floor"] = np.nan
    df.at[7, "parking_per_household"] = np.nan
    df.at[8, "households"] = np.nan
    df.at[8, "quality_flags"] = {"hh_zero"}
    df.at[8, "attr_quality_flags"] = "hh_zero"
    return df


def _step(sample, code: str):
    return next(s for s in sample.funnel if s.code == code)


def test_sample_funnel_exclusive_drop_reasons():
    df = _funnel_frame()
    v = RegionalRegressionVariables()
    elig = _eligible_mask(df, v)
    sample = build_sample_funnel(df, v, train_idx=df.index[elig], hold_idx=df.index[:0])

    assert sample.n_pool == 12
    assert sample.n_usable_tier == 9
    assert sample.n_analysis == 5
    assert _step(sample, "pool").n == 12
    assert _step(sample, "pool").label == "원본 단지"
    assert _step(sample, "usable").label == "K-apt 매칭 가능"
    assert _step(sample, "match_drop").label == "매칭 불확실·불가"
    assert _step(sample, "match_drop").delta is None
    assert _step(sample, "match_drop").n == 3
    assert _step(sample, "usable").n == 9
    assert _step(sample, "thin_tx").label == "최소 거래수 미달(<5)"
    assert _step(sample, "thin_tx").n == 0
    assert _step(sample, "var_drop").label == "선택 변수 결측"
    assert _step(sample, "var_drop").n == 4
    assert _step(sample, "analysis").n == 5
    assert _step(sample, "train").n == 5
    assert _step(sample, "hold").n == 0

    match_n = {r.code: r.n for r in _step(sample, "match_drop").reasons}
    assert match_n["tier_E"] == 1
    assert match_n["tier_Z"] == 1
    assert match_n["no_attr"] == 1
    assert sum(match_n.values()) == 3

    var_n = {r.code: r.n for r in _step(sample, "var_drop").reasons}
    assert var_n == {
        "households_missing": 1,
        "max_floor_missing": 1,
        "parking_missing": 1,
        "households_flag": 1,
    }


def test_sample_funnel_structure_adds_exclusive_drop():
    df = _funnel_frame()
    df.loc[0, "structure_group"] = ""
    v = RegionalRegressionVariables(structure=True)
    elig = _eligible_mask(df, v)
    sample = build_sample_funnel(df, v, train_idx=df.index[elig], hold_idx=df.index[:0])
    assert sample.n_analysis == 4
    var_n = {r.code: r.n for r in _step(sample, "var_drop").reasons}
    assert var_n["structure_missing"] == 1
    assert sum(var_n.values()) == 5
    assert _step(sample, "match_drop").n == 3


def test_sample_funnel_hold_is_split_not_drop():
    n = 50
    df = pd.DataFrame(
        {
            "median": [800.0] * n,
            "match_tier": ["A"] * n,
            "households": [200.0] * n,
            "max_floor": [15.0] * n,
            "building_age": [10.0] * n,
            "parking_per_household": [1.1] * n,
            "structure_group": ["RC"] * n,
            "builder_group": ["한화"] * n,
            "quality_flags": [set() for _ in range(n)],
            "n_tx": [10] * n,
            "asset_type": ["apartment"] * n,
        }
    )
    v = RegionalRegressionVariables()
    elig_idx = df.index[_eligible_mask(df, v)]
    train_idx, hold_idx = _split_hold(elig_idx)
    sample = build_sample_funnel(df, v, train_idx=train_idx, hold_idx=hold_idx)
    assert _step(sample, "var_drop").n == 0
    assert _step(sample, "thin_tx").n == 0
    assert sample.n_analysis == 50
    assert sample.n_hold > 0
    assert sample.n_fit + sample.n_hold == sample.n_analysis
    assert _step(sample, "hold").kind == "split"
    assert _step(sample, "train").n == sample.n_fit


def test_funnel_thin_tx_by_asset_type():
    df = _funnel_frame()
    df.loc[0, "n_tx"] = 2
    df.loc[1, "n_tx"] = 3
    df.loc[1, "asset_type"] = "rowhouse"
    df.loc[1, "match_tier"] = "T"
    v = RegionalRegressionVariables()
    elig = _eligible_mask(df, v)
    sample = build_sample_funnel(df, v, train_idx=df.index[elig], hold_idx=df.index[:0])
    thin = _step(sample, "thin_tx")
    assert thin.n == 2
    reasons = {r.code: r.n for r in thin.reasons}
    assert reasons["thin_apartment"] == 1
    assert reasons["thin_rowhouse"] == 1
    assert _step(sample, "usable").label == "매칭 가능"
    assert sample.n_analysis == 3


def test_design_atype_ref_is_apartment():
    work = pd.DataFrame(
        {
            "households": [100] * 20,
            "asset_type": ["officetel"] * 8 + ["apartment"] * 12,
        }
    )
    v = RegionalRegressionVariables(
        households=True,
        max_floor=False,
        building_age=False,
        parking=False,
        structure=False,
        builder=False,
        asset_type_dummy=True,
    )
    x, labels, warn = _design(work, v)
    assert labels["_atype_ref"] == "apartment"
    assert "atype_officetel" in x.columns
    assert "atype_apartment" not in x.columns
    assert _asset_type_ref(["officetel", "rowhouse"]) == "rowhouse"


def test_tx_weights_shrink_toward_n0():
    w = _tx_weights(pd.Series([5, 10, 90]))
    assert abs(w[0] - 5 / (5 + WEIGHT_N0)) < 1e-9
    assert abs(w[1] - 0.5) < 1e-9
    assert w[2] > w[1] > w[0]
    assert w[2] < 1.0


def test_fit_wls_differs_from_equal_when_n_tx_skewed():
    rng = np.random.default_rng(1)
    n = 40
    hh = rng.uniform(50, 400, n)
    # 거래 많은 단지가 더 비싸게 — equal은 신호를 약하게, tx는 강하게
    n_tx = np.array([5] * 20 + [80] * 20)
    y = np.exp(6.5 + 0.0002 * hh + 0.004 * (n_tx > 20) + rng.normal(0, 0.03, n))
    work = pd.DataFrame({"median": y, "households": hh, "n_tx": n_tx})
    x = pd.DataFrame({"households": hh})
    eq = _fit_ols(work, x, model_type="log", weight_mode="equal")
    tx = _fit_ols(work, x, model_type="log", weight_mode="tx")
    assert eq is not None and tx is not None
    assert tx["n_effective"] is not None
    assert tx["n_effective"] < tx["n"]
    assert eq["weight_mode"] == "equal"
    assert tx["weight_mode"] == "tx"


