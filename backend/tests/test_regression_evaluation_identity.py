import numpy as np
import pandas as pd

from app.built.regression.selection.fit import _rolling_time_cv_mape
from app.built.schemas import RegressionVariableSpec


def evaluate(frame):
    spec = RegressionVariableSpec(gross_area=True, land_area=False, building_age=False,
        road_width_dummy=False, zone_type_dummy=False, building_use_dummy=False,
        structure_dummy=False, asset_type_dummy=False)
    return _rolling_time_cv_mape(frame, spec, unified=False, response_scale="linear",
        region_col=None, holdout_last_year=True)[0]


def test_cv_identity_tracks_actual_observations_split_and_targets():
    rng = np.random.default_rng(82)
    area = rng.uniform(50, 300, 80)
    frame = pd.DataFrame(dict(id=np.arange(80), gross_area=area,
        price=500+area*20+rng.normal(0, 50, 80), contract_year=np.repeat([2021, 2022, 2023, 2024], 20)))
    base = evaluate(frame)
    assert base.mape is not None and base.evaluation_signature
    assert evaluate(frame.iloc[::-1]).evaluation_signature == base.evaluation_signature
    different_id = frame.copy()
    different_id.loc[30, "id"] = 1000
    assert evaluate(different_id).evaluation_signature != base.evaluation_signature
    different_target = frame.copy()
    different_target.loc[30, "price"] += 1
    assert evaluate(different_target).evaluation_signature != base.evaluation_signature
    different_split = frame.copy()
    different_split.loc[30, "contract_year"] = 2023
    assert evaluate(different_split).evaluation_signature != base.evaluation_signature
    assert evaluate(frame.drop(columns="id")).evaluation_signature is None


def test_one_nonfinite_prediction_rejects_the_whole_year(monkeypatch):
    import statsmodels.api as sm
    original = sm.OLS
    calls = 0
    def ols(*args, **kwargs):
        estimator = original(*args, **kwargs)
        fit_original = estimator.fit
        def fit(*fit_args, **fit_kwargs):
            result = fit_original(*fit_args, **fit_kwargs)
            predict_original = result.predict
            def predict(*predict_args, **predict_kwargs):
                nonlocal calls
                calls += 1
                values = np.array(predict_original(*predict_args, **predict_kwargs), dtype=float, copy=True)
                if calls == 1:
                    values[0] = np.nan
                return values
            result.predict = predict
            return result
        estimator.fit = fit
        return estimator
    monkeypatch.setattr(sm, "OLS", ols)
    area = np.arange(80) + 50.
    frame = pd.DataFrame(dict(id=np.arange(80), gross_area=area, price=500+area*20,
        contract_year=np.repeat([2021, 2022, 2023, 2024], 20)))
    phase = evaluate(frame)
    assert phase.folds == 1 and phase.n_trades == 20
    assert phase.years == (2023,)
    assert phase.failure_reasons == ((2022, "전체 평가 거래의 유한한 예측값 확보 실패"),)
