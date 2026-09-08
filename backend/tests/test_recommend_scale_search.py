"""추천 척도 탐색 — 원척도 CV · 공통 표본 · log-log."""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pandas as pd

from app.built.regression.selection.best_subset import run_group_best_subset
from app.built.regression.selection.context import SelectionContext, with_complete_case
from app.built.regression.selection.fit import (
    fit_best_scale,
    fit_scale_candidates,
    orig_cv_sort_key,
    pick_explanatory_scale,
    pick_predictive_scale,
)
from app.built.schemas import RegressionCoeff, RegressionRunRequest, RegressionVariableSpec
from app.recommendation.coef_narrative import build_coefficient_narratives


def _df(n: int = 60, *, years: int = 5, zero_area_at: int | None = None) -> pd.DataFrame:
    rng = np.random.default_rng(1)
    rows = []
    for i in range(n):
        gross = 40.0 + i
        land = 25.0 + i * 0.4
        age = 3 + (i % 8)
        price = 80.0 * (gross**1.15) * (land**0.25) * np.exp(rng.normal(0, 0.04))
        if zero_area_at is not None and i == zero_area_at:
            land = 0.0
        rows.append(
            {
                "price": price,
                "gross_area": gross,
                "land_area": land,
                "building_age": age,
                "road_width_label": "8m" if i % 2 == 0 else "12m",
                "zone_type": ["Z1", "Z2", "Z3"][i % 3],
                "building_use": "근린",
                "asset_type": "commercial",
                "contract_year": 2019 + (i % years),
            }
        )
    return pd.DataFrame(rows)


def test_orig_cv_key_prefers_cv_over_aic():
    worse_cv = SimpleNamespace(cv_mape=48.0, mape=8.0, aic=10.0)
    better_cv = SimpleNamespace(cv_mape=22.0, mape=30.0, aic=999.0)
    assert orig_cv_sort_key(better_cv) < orig_cv_sort_key(worse_cv)


def test_pick_explanatory_scale_skips_linear():
    fits = {
        "linear": SimpleNamespace(aic=1.0, response_scale="linear"),
        "log": SimpleNamespace(aic=50.0, response_scale="log"),
        "loglog": SimpleNamespace(aic=40.0, response_scale="loglog"),
    }
    picked = pick_explanatory_scale(fits)  # type: ignore[arg-type]
    assert picked is not None
    assert picked.response_scale == "loglog"


def test_loglog_skipped_without_area_blocks():
    fits = fit_scale_candidates(
        _df(),
        ["building_age", "zone_type"],
        unified=False,
        region_col=None,
        admin_level="sigungu",
    )
    assert "loglog" not in fits
    assert "linear" in fits and "log" in fits


def test_area_subset_fits_three_scales_on_same_n():
    fits = fit_scale_candidates(
        _df(),
        ["gross_area", "land_area"],
        unified=False,
        region_col=None,
        admin_level="sigungu",
    )
    assert set(fits) == {"linear", "log", "loglog"}
    ns = {fit.n for fit in fits.values()}
    assert len(ns) == 1


def test_fit_best_scale_includes_loglog_comparison():
    fit, cmp = fit_best_scale(
        _df(),
        ["gross_area", "land_area"],
        unified=False,
        region_col=None,
        admin_level="sigungu",
    )
    assert fit is not None
    assert fit.response_scale in {"linear", "log", "loglog"}
    assert cmp is not None
    assert cmp.loglog is not None
    assert cmp.metric_basis in {"cv", "insample"}
    assert cmp.recommended == fit.response_scale


def test_complete_case_drops_nonpositive_area():
    df = _df(12, zero_area_at=2)
    ctx = SelectionContext(
        df=df,
        scope_label="test",
        admin_level="sigungu",
        addr4_city=False,
        mode="two_way",
        unified=False,
    )
    sampled = with_complete_case(ctx, ["gross_area", "land_area", "building_age"], region_col=None)
    assert 2 not in sampled.df.index
    assert sampled.selection_n == 11


def test_best_subset_explanatory_is_log_family():
    df = _df(48)
    ctx = SelectionContext(
        df=df,
        scope_label="test",
        admin_level="sigungu",
        addr4_city=False,
        mode="two_way",
        unified=False,
    )
    ctx = with_complete_case(ctx, ["gross_area", "land_area", "building_age"], region_col=None)
    req = RegressionRunRequest(
        variables=RegressionVariableSpec(gross_area=True, land_area=True, building_age=True)
    )
    result = run_group_best_subset(ctx, req, ["gross_area", "land_area", "building_age"])
    assert result is not None
    assert result.by_cv_mape
    assert result.by_aic
    for candidate in result.by_aic:
        assert candidate.fit.response_scale in {"log", "loglog"}


def test_loglog_area_coefficient_is_elasticity():
    coeffs = [RegressionCoeff(name="gross_area", estimate=0.82, p_value=0.001)]
    lines = build_coefficient_narratives(coeffs, response_scale="loglog")
    assert lines
    assert "1%" in lines[0].text_ko
    assert "만원" not in lines[0].text_ko


def test_predictive_pick_uses_cv_not_aic():
    class _Fit:
        def __init__(self, scale, cv, aic):
            self.response_scale = scale
            self.cv_mape = cv
            self.mape = 20.0
            self.aic = aic

    fits = {
        "linear": _Fit("linear", 41.0, 10.0),
        "log": _Fit("log", 33.0, 80.0),
        "loglog": _Fit("loglog", 28.0, 120.0),
    }
    picked = pick_predictive_scale(fits)  # type: ignore[arg-type]
    assert picked.response_scale == "loglog"
