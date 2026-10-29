"""주거·비주거 공통 CV의 성공/미실행/부분 실패 근거를 보존한다."""
import numpy as np
import pandas as pd
import pytest

from app.collective.regression import engine


def xy(n=80):
    rng = np.random.default_rng(712)
    area = rng.uniform(40, 120, n)
    return 1000 + area * 20 + rng.normal(0, 30, n), np.column_stack([np.ones(n), area])


@pytest.mark.parametrize("scale", ["linear", "log"])
def test_complete_cv_reports_all_folds_and_only_valid_rows(scale):
    y, x = xy()
    x[[2, 7], 1] = np.nan
    report = {}
    result = engine._cv_price_metrics(y, x, scale, diagnostics=report)
    valid = np.isfinite(x).all(axis=1)
    assert result == engine._cv_price_metrics(y[valid], x[valid], scale)
    assert report["status"] == "available"
    assert (report["requested_folds"], report["attempted_folds"], report["completed_folds"]) == (5, 5, 5)
    assert (report["eligible_n"], report["evaluated_n"], report["excluded_n"]) == (78, 78, 2)
    assert report["failures"] == [] and report["reason"] is None


def test_insufficient_sample_and_training_are_distinct():
    y, x = xy(39)
    report = {}
    assert engine._cv_price_metrics(y, x, "linear", diagnostics=report) == (None, None)
    assert report["reason_code"] == "insufficient_sample"
    assert report["attempted_folds"] == 0
    y, x = xy(40)
    x = np.tile(x, (1, 20))
    assert engine._cv_price_metrics(y, x, "linear", diagnostics=report) == (None, None)
    assert report["reason_code"] == "insufficient_training"
    assert report["completed_folds"] == 0 and len(report["failures"]) == 5


def test_exception_in_one_fold_keeps_counts_but_publishes_no_partial_mape(monkeypatch):
    original, calls = engine.sm.OLS, 0
    def fail_one(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise ValueError("simulated fit failure")
        return original(*args, **kwargs)
    monkeypatch.setattr(engine.sm, "OLS", fail_one)
    y, x = xy()
    report = {}
    assert engine._cv_price_metrics(y, x, "linear", diagnostics=report) == (None, None)
    assert (report["completed_folds"], report["evaluated_n"]) == (4, 64)
    assert report["reason_code"] == "fit_failure"
    assert report["failures"][0]["fold"] == 1


@pytest.mark.parametrize("scale", ["linear", "log"])
def test_nonfinite_prediction_rejects_whole_fold(scale, monkeypatch):
    original, calls = engine.sm.OLS, 0
    def ols(*args, **kwargs):
        estimator = original(*args, **kwargs)
        original_fit = estimator.fit
        def fit():
            fitted = original_fit()
            original_predict = fitted.predict
            def predict(test):
                nonlocal calls
                calls += 1
                pred = np.array(original_predict(test), copy=True)
                if calls == 1:
                    pred[0] = np.inf
                return pred
            fitted.predict = predict
            return fitted
        estimator.fit = fit
        return estimator
    monkeypatch.setattr(engine.sm, "OLS", ols)
    y, x = xy()
    report = {}
    assert engine._cv_price_metrics(y, x, scale, diagnostics=report) == (None, None)
    assert report["reason_code"] == "invalid_prediction"
    assert report["evaluated_n"] == 64


@pytest.mark.parametrize("commercial", [False, True])
def test_both_engines_attach_same_validation_contract(commercial):
    from app.collective.schemas import CollectiveRegressionRequest, CollectiveRegressionSpec
    from app.collective_commercial.schemas import CommercialRegressionRequest, CommercialRegressionSpec
    from app.collective_commercial.regression import engine as business
    y, x = xy(39)
    frame = pd.DataFrame(dict(price=y, exclusive_area=x[:, 1], gross_area=x[:, 1],
        building_age=10, building_year=2014, floor=1, contract_year=2024, contract_month=1,
        zone_type="상업", building_use="판매", road_width_label="25m미만", road_code=10))
    if commercial:
        req = CommercialRegressionRequest(variables=CommercialRegressionSpec(gross_area=True,
            building_age=False, floor=False, zone_type=False, building_use=False, road_width=False, contract_period=False))
        _, _, _, result = business._run_regression_core(frame, req, is_shop=True)
    else:
        req = CollectiveRegressionRequest(asset_type="apartment", variables=CollectiveRegressionSpec(
            exclusive_area=True, building_age=False, floor=False, dong=False, contract_period=False))
        _, _, _, result = engine._run_regression_core(frame, req)
    metric = next(m for m in result.analysis.metrics if m.role == "selection_validation")
    assert metric.value is None and metric.status == "unavailable"
    assert metric.validation.reason_code == "insufficient_sample"
    assert metric.validation.eligible_n == result.n == 39
    assert metric.reason == metric.validation.reason


@pytest.mark.parametrize("failure", ["exception", "nonfinite"])
def test_holdout_failure_keeps_fit_and_reports_exact_cause(monkeypatch, failure):
    from app.collective.regional_regression import engine as regional
    original, calls = regional.sm.OLS, 0
    def ols(*args, **kwargs):
        estimator = original(*args, **kwargs)
        original_fit = estimator.fit
        def fit(*fit_args, **fit_kwargs):
            fitted = original_fit(*fit_args, **fit_kwargs)
            original_predict = fitted.predict
            def predict(test):
                nonlocal calls
                calls += 1
                if calls == 2 and failure == "exception":
                    raise ValueError("holdout prediction failed")
                pred = np.array(original_predict(test), copy=True)
                if calls == 2:
                    pred[0] = np.nan
                return pred
            fitted.predict = predict
            return fitted
        estimator.fit = fit
        return estimator
    monkeypatch.setattr(regional.sm, "OLS", ols)
    y, x = xy()
    frame = pd.DataFrame(dict(median=y, households=x[:, 1]))
    train, hold = regional._split_hold(frame.index)
    result = regional._fit_ols(frame, frame[["households"]], model_type="linear", train_idx=train, hold_idx=hold)
    assert result is not None and result["hold_mape"] is None
    report = result["validation"]
    assert report["status"] == "unavailable" and report["completed_folds"] == 0
    assert report["eligible_n"] == len(hold) and report["evaluated_n"] == 0
    assert report["reason_code"] == ("prediction_failure" if failure == "exception" else "invalid_prediction")


def test_holdout_sample_shortage_is_not_prediction_failure():
    from app.collective.regional_regression import engine as regional
    y, x = xy(31)
    frame = pd.DataFrame(dict(median=y, households=x[:, 1]))
    train, hold = regional._split_hold(frame.index)
    result = regional._fit_ols(frame, frame[["households"]], model_type="linear", train_idx=train, hold_idx=hold)
    assert result["validation"]["reason_code"] == "insufficient_sample"
    assert result["validation"]["attempted_folds"] == 0


def test_basic_built_separates_unrequested_validation_from_missing_year():
    from app.built.regression.engine import _focus_cv_mape
    from app.built.schemas import RegressionVariableSpec
    report = {}
    args = dict(unified=False, response_scale="linear", region_col=None, diagnostics=report)
    _focus_cv_mape(pd.DataFrame(), RegressionVariableSpec(), enabled=False, **args)
    assert report["search"]["status"] == "not_run"
    _focus_cv_mape(pd.DataFrame(), RegressionVariableSpec(), enabled=True, **args)
    assert report["search"]["reason_code"] == "missing_year"
