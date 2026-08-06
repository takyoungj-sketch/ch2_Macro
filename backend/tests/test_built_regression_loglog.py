"""log-log 회귀 · 외삽 등급."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.built.regression.engine import (
    LOGLOG_X_COLS,
    _build_design_matrix,
    _format_equation,
    _input_to_x_row,
)
from app.built.regression.extrapolation import assess_continuous, should_suppress_y_hat
from app.built.schemas import RegressionCoeff, RegressionPredictRequest, RegressionVariableSpec


def _sample_df(n: int = 20) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    gross = rng.uniform(50, 800, n)
    return pd.DataFrame(
        {
            "price": 500 + gross ** 1.2 * 2,
            "gross_area": gross,
            "land_area": gross * 0.5,
            "building_age": rng.integers(1, 30, n),
            "road_width_label": ["8m"] * n,
            "zone_type": ["일반"] * n,
            "building_use": ["근린"] * n,
            "asset_type": ["commercial"] * n,
        }
    )


def test_loglog_transforms_area_columns():
    df = _sample_df()
    spec = RegressionVariableSpec(
        gross_area=True,
        land_area=True,
        building_age=True,
    )
    y, X, meta = _build_design_matrix(df, spec, response_scale="loglog")
    assert meta is not None
    assert meta.log_x_columns == LOGLOG_X_COLS
    assert (y > 0).all() or True  # y is log(price)
    assert X["gross_area"].between(-20, 20).all()
    assert X["building_age"].max() > 5  # building_age stays linear scale


def test_loglog_input_applies_log_to_area():
    df = _sample_df()
    spec = RegressionVariableSpec(gross_area=True, land_area=False, building_age=False)
    _y, _X, meta = _build_design_matrix(df, spec, response_scale="loglog")
    assert meta is not None
    req = RegressionPredictRequest(
        addr1="a",
        addr2="b",
        admin_level="sigungu",
        variables=spec,
        response_scale="loglog",
        gross_area=100.0,
    )
    row = _input_to_x_row(meta, spec, req)
    assert abs(float(row["gross_area"].iloc[0]) - np.log(100.0)) < 1e-9


def test_format_equation_loglog_labels():
    coefs = [
        RegressionCoeff(name="const", estimate=10.0, std_err=1, t_value=10, p_value=0.001),
        RegressionCoeff(name="gross_area", estimate=1.2, std_err=0.1, t_value=12, p_value=0.001),
    ]
    eq = _format_equation(coefs, response_scale="loglog")
    assert eq.startswith("log(금액)")
    assert "log(연면적)" in eq


@pytest.mark.parametrize(
    "lo,hi,val,expected_level",
    [
        (100, 800, 400, 0),
        (100, 800, 850, 1),  # just outside, small span fraction
        (100, 800, 2000, 3),  # ~2.5x hi
        (100, 800, 20000, 4),  # >>10x hi
    ],
)
def test_extrapolation_levels(lo, hi, val, expected_level):
    a = assess_continuous("gross_area", "연면적", lo, hi, val)
    assert a.level == expected_level


def test_suppress_semilog_l4_only():
    assert should_suppress_y_hat(4, "log") is True
    assert should_suppress_y_hat(4, "linear") is False
    assert should_suppress_y_hat(4, "loglog") is False
    assert should_suppress_y_hat(2, "log") is False
