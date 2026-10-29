"""토지 공시지가 표본 정책·로그 원척도 평균·추천 계약 회귀 테스트."""
import math

import numpy as np
import pytest
from fastapi import HTTPException

from app import land_regression as engine
from app.schemas import LandRegressionRequest, LandRegressionPredictRequest, LandRegressionVariables


def rows():
    rng = np.random.default_rng(21)
    result = []
    for i in range(60):
        area = float(rng.uniform(30, 300))
        official = float(rng.uniform(1_000_000, 6_000_000))
        log_price = 3 + 0.2 * math.log(area) + 0.1 * math.log(official) + float(rng.normal(0, 0.6))
        result.append(dict(id=i, unit_price_per_sqm=math.exp(log_price), area_sqm=area,
            contract_year=2021+i % 5, road_condition="8미만", deal_type="중개거래",
            is_partial_ownership=False, official_price_won=official))
    return result


def request(assessed=True):
    return LandRegressionRequest(zone_type="2주", land_category="대", min_n=10,
        variables=LandRegressionVariables(area_sqm=True, log_area=True, road_condition=False,
            deal_type=False, year_trend=False, partial_ownership=False, beopjungri_fe=False,
            assessed_land_price=assessed))


def test_assessed_model_distinguishes_unsupported_shares_from_missing_price():
    data = rows()
    for row in data[:10]:
        row["is_partial_ownership"] = True
        # 잘못 연결된 값이 있어도 공시지가 모형에 지분거래를 넣지 않는다.
    data[10]["official_price_won"] = None
    result = engine.run_land_regression(data, request())
    assert result.n == 49
    assert any("지분거래 10건 제외" in w for w in result.warnings)
    assert any("개별공시지가 결측 1건" in w for w in result.warnings)
    assert engine.run_land_regression(data, request(False)).n == 60
    # 공시지가 없는 후보를 찾더라도 지분거래를 다시 투입하지 않는다.
    suggestion = engine.suggest_land_regression(data, request())
    assert suggestion.selection_n == 50
    assert any("지분거래 10건 제외" in w for w in suggestion.warnings)


@pytest.mark.parametrize("model_type", ["log", "linear"])
def test_prediction_mean_and_intervals_share_defined_price_scale(model_type):
    data = rows()
    req = request().model_copy(update={"model_type": model_type})
    predict = LandRegressionPredictRequest(**req.model_dump(), area_sqm=100, assessed_land_price=3_000_000)
    df, warnings = engine._prepare_df(data, req)
    df, warnings = engine._apply_assessed_case(df, req, warnings)
    bundle = engine._build_design(df, req, warnings)
    model = engine.sm.OLS(bundle.y_fit, bundle.X_const).fit()
    summary = model.get_prediction(engine._input_to_x_row(bundle, predict)).summary_frame().iloc[0]
    smear = engine._duan_smearing(model.resid) if model_type == "log" else 1
    result = engine.predict_land_regression(data, predict)
    assert result.log_smearing_factor == pytest.approx(smear)
    assert result.y_hat == pytest.approx(engine._back_transform(summary["mean"], model_type)*smear)
    assert result.ci_lower == pytest.approx(engine._back_transform(summary["mean_ci_lower"], model_type)*smear)
    assert result.ci_upper == pytest.approx(engine._back_transform(summary["mean_ci_upper"], model_type)*smear)
    assert result.pi_lower == pytest.approx(engine._back_transform(summary["obs_ci_lower"], model_type))
    assert result.pi_upper == pytest.approx(engine._back_transform(summary["obs_ci_upper"], model_type))
    if model_type == "log":
        assert smear > 1


def test_recommendation_explicitly_excludes_assessed_block_and_is_order_stable():
    data = rows()
    for row in data[:40]: row["official_price_won"] = None
    req = request()
    fit = engine.run_land_regression(data, req)
    result = engine.suggest_land_regression(data, req)
    assert fit.n == 20 and result.selection_n == 60
    assert result.excluded_blocks == ["assessed_land_price"]
    assert any("표본이 다르므로" in w for w in result.warnings)
    assert result.candidates_by_aic
    assert all(not c.variables.assessed_land_price for c in result.candidates_by_aic)
    assert result.model_dump() == engine.suggest_land_regression(list(reversed(data)), req).model_dump()


def test_assessed_prediction_rejects_share_transaction():
    req = LandRegressionPredictRequest(**request().model_dump(), area_sqm=100,
        assessed_land_price=3_000_000, partial_ownership=True)
    with pytest.raises(HTTPException) as exc:
        engine.predict_land_regression(rows(), req)
    assert exc.value.status_code == 400


def test_prediction_rejects_changed_fit_data_before_returning_new_price():
    data, req = rows(), request()
    fit = engine.run_land_regression(data, req)
    predict = LandRegressionPredictRequest(**req.model_dump(), area_sqm=100, assessed_land_price=3_000_000,
        expected_model_signature=fit.analysis.model_signature)
    engine.predict_land_regression(data, predict)
    data[0]["unit_price_per_sqm"] *= 1.1
    with pytest.raises(HTTPException) as exc:
        engine.predict_land_regression(data, predict)
    assert exc.value.status_code == 409


def test_assessed_model_never_fills_all_missing_prices():
    data = rows()
    for row in data: row["official_price_won"] = None
    with pytest.raises(HTTPException): engine.run_land_regression(data, request())
