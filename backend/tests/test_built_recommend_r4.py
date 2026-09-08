"""R4 — built_recommend narrative extensions."""

from __future__ import annotations

from app.recommendation.coef_narrative import build_coefficient_narratives
from app.recommendation.diagnostics import build_diagnostics_checklist
from app.built.schemas import RegressionCoeff, ResponseScale
import pandas as pd


def test_diagnostics_checklist_unsuitable():
    items = build_diagnostics_checklist(
        scope_n_tx=286,
        selection_n=168,
        fit_n=168,
        cv_mape=83.0,
        mape=66.0,
        verdict="no_predictive_model",
        exclude_outliers_iqr=False,
        primary_blocks=["land_area", "building_age"],
        variable_limit=True,
    )
    by_id = {i.check_id: i for i in items}
    assert by_id["sample"].status in {"ok", "warn"}
    assert by_id["variable"].status == "warn"
    assert "Local·Twin" not in by_id["variable"].summary_ko
    assert by_id["outlier"].status in {"warn", "ok"}
    assert len(items) == 4


def test_diagnostics_sample_caution_matches_macro_axis():
    items = build_diagnostics_checklist(
        scope_n_tx=87,
        selection_n=69,
        fit_n=69,
        cv_mape=37.5,
        mape=41.5,
        verdict="adopt_predictive",
        exclude_outliers_iqr=False,
        primary_blocks=["land_area"],
        variable_limit=False,
    )
    sample = next(i for i in items if i.check_id == "sample")
    assert sample.status == "warn"
    assert "표본 주의" in sample.summary_ko
    assert "무난한" not in sample.summary_ko


def test_coefficient_narratives_categorical():
    coeffs = [
        RegressionCoeff(name="building_use_숙박", estimate=195.0, p_value=0.01),
        RegressionCoeff(name="land_area", estimate=958.0, p_value=0.001),
    ]
    lines = build_coefficient_narratives(coeffs, response_scale="linear")
    assert len(lines) >= 1
    assert any("숙박" in ln.text_ko or "대지" in ln.text_ko for ln in lines)


def test_coefficients_from_block_fit_include_intercept():
    from types import SimpleNamespace

    from app.recommendation.coefficients import coefficients_from_block_fit

    model = SimpleNamespace(
        params=pd.Series({"const": 10.5, "building_age": -0.019}),
        bse=pd.Series({"const": 0.4, "building_age": 0.005}),
        tvalues=pd.Series({"const": 26.0, "building_age": -3.8}),
        pvalues=pd.Series({"const": 0.0, "building_age": 0.00018}),
    )
    coefs = coefficients_from_block_fit(SimpleNamespace(model=model))
    names = [c.name for c in coefs]
    assert "const" in names
    assert "building_age" in names
