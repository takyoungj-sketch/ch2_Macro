"""R4 — built_recommend narrative extensions."""

from __future__ import annotations

from app.recommendation.coef_narrative import build_coefficient_narratives
from app.recommendation.diagnostics import build_diagnostics_checklist
from app.built.schemas import RegressionCoeff, ResponseScale


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
    assert by_id["variable"].status == "fail"
    assert by_id["outlier"].status in {"warn", "ok"}
    assert len(items) == 4


def test_coefficient_narratives_categorical():
    coeffs = [
        RegressionCoeff(name="building_use_숙박", estimate=195.0, p_value=0.01),
        RegressionCoeff(name="land_area", estimate=958.0, p_value=0.001),
    ]
    lines = build_coefficient_narratives(coeffs, response_scale="linear")
    assert len(lines) >= 1
    assert any("숙박" in ln.text_ko or "대지" in ln.text_ko for ln in lines)
