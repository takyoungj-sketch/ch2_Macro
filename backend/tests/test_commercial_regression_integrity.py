"""비주거 기간·검증 오차·추정 시점 및 공유 계산 계약 회귀 테스트."""
from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest

from app.collective.regression import engine as shared
from app.collective.regression.presentation import interpret_coefficient
from app.collective_commercial import router
from app.collective_commercial.regression import engine
from app.collective_commercial.schemas import (
    CommercialRegressionRequest, CommercialRegressionSpec,
    CommercialRegressionPredictRequest, CommercialRegressionPredictInputs,
    CommercialRegressionResponse,
)


def sample():
    rng = np.random.default_rng(10)
    n = 80
    area = rng.uniform(50, 120, n)
    age = rng.integers(1, 30, n)
    month = np.where(np.arange(n) % 2 == 0, 3, 9)
    price = 10000 + 400 * area - 100 * age + (month == 9) * 4000 + rng.normal(0, 100, n)
    return pd.DataFrame(dict(
        transaction_id=np.arange(n), price=price, unit_price=price/area,
        gross_area=area, building_age=age, building_year=2024-age,
        contract_year=2024, contract_month=month, floor=1,
        zone_type="상업", building_use="판매", road_width_label="25m미만",
        road_code=10, asset_type="collective_shop", building_key="b", addr4="개포동",
    ))


def request():
    return CommercialRegressionRequest(variables=CommercialRegressionSpec(
        floor=False, zone_type=False, building_use=False, road_width=False,
        contract_period=True,
    ))


def test_unknown_category_does_not_silently_use_reference():
    df, req = sample(), request()
    df["zone_type"] = np.where(df.index % 2, "상업", "주거")
    req.variables.zone_type = True
    _, X, meta, _ = engine._run_regression_core(df, req, is_shop=True)
    with pytest.raises(ValueError, match="용도지역"):
        engine._inputs_to_x_row(X, meta, req, CommercialRegressionPredictInputs(
            gross_area=85, building_age=10, zone_type="다른모형의범주"))


def test_cv_cleans_missing_rows_before_folds():
    df = sample()
    y = df.price.to_numpy()
    x = np.column_stack([np.ones(len(df)), df.gross_area, df.building_age])
    x[[2, 7, 16, 35], 1] = np.nan
    good = np.isfinite(x).all(axis=1)
    assert shared._cv_price_metrics(y, x, "linear") == shared._cv_price_metrics(y[good], x[good], "linear")


def test_cv_never_reports_partial_fold_success(monkeypatch):
    original = shared.sm.OLS
    calls = 0
    def fail_one_fold(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise ValueError("one fold failed")
        return original(*args, **kwargs)
    monkeypatch.setattr(shared.sm, "OLS", fail_one_fold)
    df = sample()
    assert shared._cv_price_metrics(df.price, np.column_stack([np.ones(len(df)), df.gross_area]), "linear") == (None, None)


@pytest.mark.parametrize("model_type", ["linear", "log"])
@pytest.mark.parametrize("is_shop", [True, False])
def test_response_separates_metrics_and_is_order_invariant(model_type, is_shop):
    df = sample()
    df.loc[[2, 7, 16], "gross_area"] = np.nan
    req = request().model_copy(update={"model_type": model_type})
    first = engine.run_commercial_regression(df, "road", "도로", req, is_shop=is_shop)
    other = engine.run_commercial_regression(df.sample(frac=1, random_state=29), "road", "도로", req, is_shop=is_shop)
    assert first.n == 77
    assert first.in_sample_mape is not None and first.cv_mape is not None
    assert first.metric_basis == "cv" and first.mape == first.cv_mape
    assert first.model_dump() == other.model_dump()


def test_cohort_regression_keeps_same_metrics_after_shuffling():
    df = sample()
    df["cluster_key"] = np.where(df.index < 40, "road-a", "road-b")
    kwargs = dict(cluster_keys=["road-a", "road-b"], display_label="두 도로", req=request(), is_shop=True)
    first = engine.run_cohort_commercial_regression(df, **kwargs)
    other = engine.run_cohort_commercial_regression(df.sample(frac=1, random_state=29), **kwargs)
    assert first.n == 80 and first.cv_mape is not None
    assert first.model_dump() == other.model_dump()


def test_prediction_uses_selected_half_year_and_reports_it():
    df, req = sample(), request()
    _, _, meta, fit = engine._run_regression_core(df, req, is_shop=True)
    periods = fit.predict_options.contract_periods
    assert periods == ["2024H1", "2024H2"]
    predictions = [engine.predict_commercial_regression(df, req,
        CommercialRegressionPredictInputs(gross_area=85, building_age=10, contract_period=p), is_shop=True)
        for p in periods]
    coefficient = next(c.coef for c in fit.coefficients if c.name == "time_2024H2")
    assert predictions[1]["y_hat"] - predictions[0]["y_hat"] == pytest.approx(coefficient, abs=0.11)
    assert [x["applied_contract_period"] for x in predictions] == periods
    assert meta.time_reference == "2024H1"


def test_prediction_requires_same_model_after_data_refresh():
    from fastapi import HTTPException
    df, req = sample(), request()
    _, _, _, fit = engine._run_regression_core(df, req, is_shop=True)
    pred_req = CommercialRegressionPredictRequest(**req.model_dump(), expected_model_signature=fit.analysis.model_signature)
    inputs = CommercialRegressionPredictInputs(gross_area=85, building_age=10)
    engine.predict_commercial_regression(df, pred_req, inputs, is_shop=True)
    df.loc[0, "price"] += 1000
    with pytest.raises(HTTPException) as exc:
        engine.predict_commercial_regression(df, pred_req, inputs, is_shop=True)
    assert exc.value.status_code == 409


@pytest.mark.parametrize("inputs", [
    dict(building_age=10), dict(gross_area=0, building_age=10),
    dict(gross_area=85, building_age=10, contract_period="2099H1"),
])
def test_missing_or_unmodeled_prediction_input_is_rejected(inputs):
    with pytest.raises(ValueError):
        engine.predict_commercial_regression(sample(), request(), CommercialRegressionPredictInputs(**inputs), is_shop=True)


@pytest.mark.parametrize("endpoint", ["run", "predict"])
def test_single_road_routes_forward_date_bounds_and_order(endpoint, monkeypatch):
    seen = {}
    def where(**kwargs):
        seen.update(kwargs)
        return "TRUE", {}
    monkeypatch.setattr(router, "_tx_where", where)
    monkeypatch.setattr(router, "evaluate_analysis_gates", lambda *args: SimpleNamespace(regression_eligible=True))
    monkeypatch.setattr(router, "_cluster_display_label", lambda *args: "도로")
    monkeypatch.setattr(router, "run_commercial_regression", lambda *args, **kwargs: CommercialRegressionResponse(cluster_key="r", display_label="도로", n=80))
    monkeypatch.setattr(router, "predict_commercial_regression", lambda *args, **kwargs: dict(
        n=80, y_hat=1, pi_lower=0, pi_upper=2, ci_lower=0.5, ci_upper=1.5))
    db = MagicMock()
    db.execute.return_value.mappings.return_value.all.return_value = sample().to_dict("records")
    cls = CommercialRegressionRequest if endpoint == "run" else CommercialRegressionPredictRequest
    body = cls(contract_date_from="2021-10-01", contract_date_to="2026-09-30")
    fn = router.cluster_regression if endpoint == "run" else router.cluster_regression_predict
    fn("road", body, db)
    assert seen["contract_date_from"] == date(2021, 10, 1)
    assert seen["contract_date_to"] == date(2026, 9, 30)
    assert "ORDER BY id" in str(db.execute.call_args.args[0])


def test_single_floor_index_forwards_rolling_dates(monkeypatch):
    seen = {}

    def where(**kwargs):
        seen.update(kwargs)
        return "TRUE", {"cluster_key": "road"}

    monkeypatch.setattr(router, "_tx_where", where)
    monkeypatch.setattr(router, "_cluster_display_label", lambda *args: "도로")
    monkeypatch.setattr(
        router,
        "evaluate_analysis_gates",
        lambda *args, **kwargs: SimpleNamespace(
            floor_index_eligible=True,
            regression_eligible=True,
            count_total=80,
            count_recent=80,
            messages=[],
        ),
    )
    monkeypatch.setattr(
        router,
        "compute_residential_floor_index_regression",
        lambda *args, **kwargs: {
            "dimension": "floor",
            "method": "reference_only",
            "floor_mode": "shop",
            "reference_floor": "1층",
            "controls": [],
            "n_total": 80,
            "cells": [],
            "warnings": [],
        },
    )
    db = MagicMock()
    db.execute.return_value.mappings.return_value.all.return_value = sample().to_dict("records")
    router.cluster_floor_index(
        "road",
        db,
        contract_date_from=date(2021, 10, 1),
        contract_date_to=date(2026, 9, 30),
    )
    assert seen["contract_date_from"] == date(2021, 10, 1)
    assert seen["contract_date_to"] == date(2026, 9, 30)


def test_date_filter_uses_exact_bounds():
    where, params = router._tx_where(contract_date_from=date(2021, 10, 1), contract_date_to=date(2026, 9, 30))
    assert "contract_date" in where
    assert date(2021, 10, 1) in params.values()
    assert date(2026, 9, 30) in params.values()


@pytest.mark.parametrize("name", ["time_2024H2", "shop_high", "fac_3p", "clu_road"])
def test_category_effect_is_reference_comparison(name):
    assert "기준 대비" in interpret_coefficient(name, name, 200, model_type="linear")
