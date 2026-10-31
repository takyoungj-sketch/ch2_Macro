import numpy as np
import pandas as pd
import pytest

from app.collective.regression import engine
from app.collective.schemas import CollectiveRegressionRequest, CollectiveRegressionSpec, CollectiveRegressionPredictInputs


def fixture():
    rng = np.random.default_rng(90)
    area = rng.uniform(45, 130, 80)
    age = rng.integers(1, 35, 80)
    month = np.where(np.arange(80) % 2, 9, 3)
    df = pd.DataFrame(dict(transaction_id=np.arange(80), exclusive_area=area, building_age=age,
        price=10000+area*500-age*100+(month == 9)*5000+rng.normal(0, 100, 80),
        contract_year=2024, contract_month=month, asset_type="apartment", floor=1))
    req = CollectiveRegressionRequest(asset_type="apartment", model_type="linear",
        variables=CollectiveRegressionSpec(floor=False, dong=False))
    return df, req


def test_residential_half_year_changes_prediction_and_reports_actual_period():
    df, req = fixture()
    _, _, _, fit = engine._run_regression_core(df, req)
    assert fit.predict_options.contract_periods == ["2024H1", "2024H2"]
    results = [engine.predict_regression(df, req, CollectiveRegressionPredictInputs(
        exclusive_area=85, building_age=10, contract_period=p)) for p in fit.predict_options.contract_periods]
    coef = next(c.coef for c in fit.coefficients if c.name == "time_2024H2")
    assert results[1]["y_hat"] - results[0]["y_hat"] == pytest.approx(coef, abs=.11)
    assert [r["applied_contract_period"] for r in results] == fit.predict_options.contract_periods


@pytest.mark.parametrize("inputs", [dict(building_age=10), dict(exclusive_area=0, building_age=10),
    dict(exclusive_area=85), dict(exclusive_area=85, building_age=10, contract_period="2099H1")])
def test_missing_input_does_not_become_zero_or_reference(inputs):
    df, req = fixture()
    with pytest.raises(ValueError):
        engine.predict_regression(df, req, CollectiveRegressionPredictInputs(**inputs))


def test_prediction_requires_the_displayed_model_signature():
    from fastapi import HTTPException
    from app.collective.schemas import CollectiveRegressionPredictRequest
    df, req = fixture()
    _, _, _, fit = engine._run_regression_core(df, req)
    pred_req = CollectiveRegressionPredictRequest(**req.model_dump(), expected_model_signature=fit.analysis.model_signature)
    inputs = CollectiveRegressionPredictInputs(exclusive_area=85, building_age=10)
    engine.predict_regression(df, pred_req, inputs)
    df.loc[0, "price"] += 1000
    with pytest.raises(HTTPException) as exc:
        engine.predict_regression(df, pred_req, inputs)
    assert exc.value.status_code == 409


def test_transaction_identity_and_order_are_part_of_fit_contract():
    df, req = fixture()
    _, _, _, original = engine._run_regression_core(df, req)
    _, _, _, shuffled = engine._run_regression_core(df.sample(frac=1, random_state=20), req)
    assert original.analysis.fit_sample_signature
    assert original.analysis.model_signature == shuffled.analysis.model_signature
    assert original.analysis.metrics == shuffled.analysis.metrics
    df.loc[0, "transaction_id"] = 1000
    _, _, _, other = engine._run_regression_core(df, req)
    assert other.analysis.model_signature != original.analysis.model_signature


def test_unknown_category_does_not_silently_use_reference():
    df, req = fixture()
    df["housing_subtype"] = np.where(df.index % 2, "기존주택", "분양권")
    req.variables.housing_subtype = True
    with pytest.raises(ValueError, match="권리유형"):
        engine.predict_regression(df, req, CollectiveRegressionPredictInputs(
            exclusive_area=85, building_age=10, housing_subtype="다른모형의범주"))
