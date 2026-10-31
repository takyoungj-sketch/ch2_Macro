"""희소 단지·반기 제외, 학습 밖 층 거절, 식별되지 않는 예측·교차검증."""

import numpy as np
import pandas as pd
import pytest

from app.collective.regression import engine
from app.collective.schemas import (
    CollectiveRegressionPredictInputs,
    CollectiveRegressionRequest,
    CollectiveRegressionSpec,
)
from app.collective_commercial.regression import engine as commercial
from app.collective_commercial.schemas import CommercialRegressionRequest, CommercialRegressionSpec


def _spec(**flags):
    base = dict(
        exclusive_area=True, building_age=False, floor=False, dong=False,
        contract_period=False, housing_subtype=False, structure=False,
    )
    base.update(flags)
    return CollectiveRegressionSpec(**base)


def _block(start, n, key, effect, *, year=2024, month=3, floor=1, age=10):
    rng = np.random.default_rng(start + n)
    area = rng.uniform(40, 120, n)
    return pd.DataFrame({
        "transaction_id": np.arange(start, start + n),
        "building_key": key,
        "exclusive_area": area,
        "price": 1000 * area + effect,
        "floor": floor,
        "building_age": age,
        "contract_year": year,
        "contract_month": month,
        "asset_type": "apartment",
    })


def test_sparse_building_does_not_move_the_other_fe():
    df = pd.concat([
        _block(0, 80, "A", 0),
        _block(80, 40, "B", 5000),
        _block(120, 4, "C", 40000),
    ], ignore_index=True)
    req = CollectiveRegressionRequest(asset_type="apartment", model_type="linear", variables=_spec())
    _model, _X, meta, fit = engine._run_regression_core(
        df, req, cohort_mode=True, building_display_names={"A": "가단지", "B": "나단지", "C": "다단지"},
    )
    assert fit.n == 120
    assert "C" not in meta.building_fe_map
    assert "C" not in meta.building_counts
    coef = next(c.coef for c in fit.coefficients if c.name == meta.building_fe_map["B"])
    assert coef == pytest.approx(5000, abs=0.05)
    assert any("다단지" in note and "학습에서 제외" in note for note in fit.warnings)


def test_thin_half_year_is_left_out_of_training():
    df = pd.concat([
        _block(0, 40, "A", 0, year=2024, month=3),
        _block(40, 40, "A", 3000, year=2024, month=9),
        _block(80, 4, "A", 50000, year=2020, month=3),
    ], ignore_index=True)
    req = CollectiveRegressionRequest(
        asset_type="apartment", model_type="linear",
        variables=_spec(contract_period=True),
    )
    _model, _X, meta, fit = engine._run_regression_core(df, req)
    assert fit.n == 80
    assert fit.predict_options.contract_periods == ["2024H1", "2024H2"]
    assert meta.time_reference in {"2024H1", "2024H2"}
    other = next(p for p in fit.predict_options.contract_periods if p != meta.time_reference)
    base = engine.predict_regression(df, req, CollectiveRegressionPredictInputs(
        exclusive_area=80, contract_period=meta.time_reference))
    moved = engine.predict_regression(df, req, CollectiveRegressionPredictInputs(
        exclusive_area=80, contract_period=other))
    assert moved["y_hat"] - base["y_hat"] == pytest.approx(3000 if other == "2024H2" else -3000, abs=0.2)


def test_unseen_floor_is_refused_and_trained_floors_differ():
    low = _block(0, 40, "A", 0, floor=1)
    high = _block(40, 40, "A", 800, floor=3)
    df = pd.concat([low, high], ignore_index=True)
    req = CollectiveRegressionRequest(
        asset_type="apartment", model_type="linear",
        variables=_spec(floor=True, floor_mode="dummy"),
    )
    _model, _X, meta, fit = engine._run_regression_core(df, req)
    assert set(meta.floor_trained_codes) == {"floor_1", "floor_3"}
    with pytest.raises(ValueError, match="모형에 포함된 층"):
        engine.predict_regression(df, req, CollectiveRegressionPredictInputs(exclusive_area=80, floor=2))
    first = engine.predict_regression(df, req, CollectiveRegressionPredictInputs(exclusive_area=80, floor=1))
    third = engine.predict_regression(df, req, CollectiveRegressionPredictInputs(exclusive_area=80, floor=3))
    assert third["y_hat"] - first["y_hat"] == pytest.approx(800, abs=0.2)


def test_collinear_age_refuses_only_the_unseen_combination():
    frames = []
    start = 0
    for year, age in ((2022, 12), (2023, 13)):
        for month in (3, 9):
            frames.append(_block(start, 20, "A", age * 10 + (50 if month == 9 else 0), year=year, month=month, age=age))
            start += 20
    df = pd.concat(frames, ignore_index=True)
    req = CollectiveRegressionRequest(
        asset_type="apartment", model_type="linear",
        variables=_spec(building_age=True, contract_period=True),
    )
    _model, _X, _meta, fit = engine._run_regression_core(df, req)
    age = next(c for c in fit.coefficients if c.name == "building_age")
    assert age.se is None and age.p is None
    assert age.effect_plain == "이 계수는 한 값으로 정해지지 않습니다."
    ok = engine.predict_regression(df, req, CollectiveRegressionPredictInputs(
        exclusive_area=80, building_age=13, contract_period="2023H1"))
    assert np.isfinite(ok["y_hat"])
    with pytest.raises(ValueError, match="정해지지 않아"):
        engine.predict_regression(df, req, CollectiveRegressionPredictInputs(
            exclusive_area=80, building_age=12, contract_period="2023H1"))


def test_one_row_dummy_makes_cv_unavailable():
    y = np.linspace(100, 200, 40)
    rare = np.zeros(40)
    rare[0] = 1.0
    x = np.column_stack([np.ones(40), np.linspace(1, 2, 40), rare])
    report = {}
    mape, rmse = engine._cv_price_metrics(y, x, "linear", diagnostics=report)
    assert mape is None and rmse is None
    assert report["status"] == "unavailable"
    assert any(item["code"] == "unseen_category" for item in report["failures"])


def test_subject_pair_withholds_cv_when_a_category_is_held_out():
    n = 80
    y = pd.Series(np.linspace(100, 200, n))
    rare = np.zeros(n)
    rare[0] = 1.0
    x = pd.DataFrame({"area": np.linspace(1, 2, n), "rare": rare})
    report = {}
    mape, rmse = engine._cv_price_metrics(y.to_numpy(), engine._with_const(x), "linear", diagnostics=report)
    assert mape is None and rmse is None
    assert any(item["code"] == "unseen_category" for item in report["failures"])
    neighbors = pd.DataFrame({"area": np.linspace(1, 2, 20), "rare": 0.0}, index=range(100, 120))
    y_after = pd.concat([y, pd.Series(np.linspace(100, 180, 20), index=neighbors.index)])
    x_after = pd.concat([x, neighbors])
    before_m, after_m, basis = engine._subject_pair_mape(y, x, y_after, x_after, y.index, "linear")
    assert before_m is None and after_m is None
    assert basis == "cv"


def test_sparse_cluster_does_not_move_the_other_fe():
    rng = np.random.default_rng(7)
    frames = []
    start = 0
    for key, n, effect in (("A", 80, 0), ("B", 40, 5000), ("C", 4, 40000)):
        area = rng.uniform(40, 120, n)
        price = 1000 * area + effect
        frames.append(pd.DataFrame({
            "transaction_id": np.arange(start, start + n),
            "cluster_key": key,
            "gross_area": area,
            "price": price,
            "unit_price": price / area,
            "building_age": 10,
            "building_year": 2014,
            "contract_year": 2024,
            "contract_month": 6,
            "floor": 1,
        }))
        start += n
    df = pd.concat(frames, ignore_index=True)
    req = CommercialRegressionRequest(
        model_type="linear",
        variables=CommercialRegressionSpec(
            gross_area=True, building_age=False, floor=False, zone_type=False,
            building_use=False, road_width=False, contract_period=False,
        ),
    )
    _model, _X, meta, fit = commercial._run_regression_core(
        df, req, is_shop=True, cohort_mode=True,
        cluster_display_labels={"A": "가도로", "B": "나도로", "C": "다도로"},
    )
    assert fit.n == 120
    assert "C" not in meta.cluster_fe_map
    coef = next(c.coef for c in fit.coefficients if c.name == meta.cluster_fe_map["B"])
    assert coef == pytest.approx(5000, abs=0.05)
    assert any("다도로" in note and "학습에서 제외" in note for note in fit.warnings)


def _priced(n, price, **cols):
    frame = _block(0, n, "A", 0)
    frame["price"] = price
    for key, value in cols.items():
        frame[key] = value
    return frame


def test_blank_dong_is_not_the_labeled_reference():
    df = pd.concat(
        [
            _priced(20, 50000.0, dong=""),
            _priced(20, 55000.0, dong="101"),
            _priced(20, 60000.0, dong="102"),
        ],
        ignore_index=True,
    )
    req = CollectiveRegressionRequest(
        asset_type="apartment",
        model_type="linear",
        variables=_spec(exclusive_area=False, dong=True),
    )
    _model, _X, meta, fit = engine._run_regression_core(df, req)
    assert meta.dong_reference == "101"
    assert fit.n == 60
    reference = engine.predict_regression(df, req, CollectiveRegressionPredictInputs(dong="101"))
    blank = engine.predict_regression(df, req, CollectiveRegressionPredictInputs(dong=""))
    assert reference["y_hat"] == pytest.approx(55000, abs=1)
    assert blank["y_hat"] == pytest.approx(50000, abs=1)


def test_blank_rights_is_not_the_labeled_reference():
    df = pd.concat(
        [
            _priced(20, 40000.0, housing_subtype=""),
            _priced(20, 55000.0, housing_subtype="분양권"),
            _priced(20, 70000.0, housing_subtype="입주권"),
        ],
        ignore_index=True,
    )
    req = CollectiveRegressionRequest(
        asset_type="presale",
        model_type="linear",
        variables=_spec(exclusive_area=False, housing_subtype=True),
    )
    _model, _X, meta, fit = engine._run_regression_core(df, req)
    assert meta.housing_subtype_reference == "분양권"
    named = engine.predict_regression(df, req, CollectiveRegressionPredictInputs(housing_subtype="분양권"))
    blank = engine.predict_regression(df, req, CollectiveRegressionPredictInputs(housing_subtype=""))
    assert named["y_hat"] == pytest.approx(55000, abs=1)
    assert blank["y_hat"] == pytest.approx(40000, abs=1)


def test_missing_floor_is_excluded_in_individual_and_grouped_modes():
    known = pd.concat(
        [_priced(40, 50000.0, floor=1), _priced(40, 80000.0, floor=8)],
        ignore_index=True,
    )
    missing = _priced(30, 90000.0)
    missing["floor"] = np.nan
    df = pd.concat([known, missing], ignore_index=True)
    for mode in ("dummy", "grouped", "relative"):
        req = CollectiveRegressionRequest(
            asset_type="apartment",
            model_type="linear",
            variables=_spec(exclusive_area=False, floor=True, floor_mode=mode),
        )
        _model, _X, _meta, fit = engine._run_regression_core(df, req)
        assert fit.n == 80
        first = engine.predict_regression(df, req, CollectiveRegressionPredictInputs(floor=1))
        assert first["y_hat"] == pytest.approx(50000, abs=1)
