"""DB 반환 순서가 바뀌어도 지역회귀·추천·예측이 같아야 한다."""
from datetime import date
from types import SimpleNamespace

import numpy as np
import pytest

from app.collective.regional_regression import engine
from app.collective.regional_regression.schemas import (
    RegionalRegressionPredictInputs,
    RegionalRegressionRunRequest,
    RegionalRegressionVariables,
)


@pytest.fixture
def unordered_connection(monkeypatch):
    monkeypatch.setattr(engine, "latest_mart_snapshot", lambda conn: (date(2026, 9, 1), {}))
    monkeypatch.setattr(engine, "_latest_snapshot_ym", lambda conn: "202607")
    monkeypatch.setattr(engine, "_mart_region_where", lambda *args, **kwargs: ("TRUE", {}))
    monkeypatch.setattr(engine, "_assessed_land_price_sql", lambda conn: ("", ""))
    rng = np.random.default_rng(17)
    rows = []
    for i in range(64):
        asset_type = "apartment" if i % 2 else "officetel"
        households = 60 + i * 7
        age = i % 21
        floor = 5 + i % 17
        rows.append(dict(
            # 두 유형에서 같은 building_key도 구분되어야 한다.
            building_key=f"building-{i // 2:03}", display_name=f"단지 {i:03}",
            asset_type=asset_type, median=800 + households * 0.7 - age * 9 + floor * 12
            + (200 if asset_type == "apartment" else 0) + float(rng.normal(0, 25)),
            n_tx=6 + i % 9, building_year=2026-age, approved_year=2026-age,
            addr1="서울특별시", addr2="강남구", addr3="삼성동", addr4=None,
            match_tier="A", match_rule="test", households=households,
            max_floor=floor, parking_per_household=0.8 + (i % 7) * 0.1,
            structure_group="RC", builder_group="시공사", attr_quality_flags=None,
            assessed_land_price=None, assessed_land_price_year=None, assessed_land_price_pnu=None,
        ))
    # 검증 분할을 하지 않는 표본에서도 순서를 고정하는지 확인한다.
    state = {"order": np.arange(len(rows)), "count": len(rows)}

    def execute(*args, **kwargs):
        result = [rows[int(i)].copy() for i in state["order"] if i < state["count"]]
        return SimpleNamespace(mappings=lambda: SimpleNamespace(all=lambda: result))

    return SimpleNamespace(execute=execute), state


def request(model_type="log", weight_mode="equal"):
    return RegionalRegressionRunRequest(
        addr1="서울특별시", addr2="강남구", addr3_list=["삼성동"],
        asset_type="apartment,officetel", window_years=5,
        variables=RegionalRegressionVariables(parking=False),
        model_type=model_type, weight_mode=weight_mode,
    )


def test_prediction_uses_same_categorical_missing_rows_as_displayed_fit(unordered_connection, monkeypatch):
    conn, _ = unordered_connection
    req = request().model_copy(update={"categorical_missing": "drop",
        "variables": RegionalRegressionVariables(parking=False, structure=True)})
    frame, meta = engine.load_danji_frame(conn, req)
    frame.loc[frame.index[:10], "structure_group"] = None
    monkeypatch.setattr(engine, "load_danji_frame", lambda *args: (frame.copy(), meta))
    actual_fit = engine._fit_ols
    fit_indices = []
    def capture(work, x, **kwargs):
        fit_indices.append(tuple(kwargs["train_idx"]))
        return actual_fit(work, x, **kwargs)
    monkeypatch.setattr(engine, "_fit_ols", capture)
    engine.predict_regional(conn, req, RegionalRegressionPredictInputs(
        households=220, max_floor=15, building_age=10, asset_type="apartment", structure_group="RC"))
    # 첫 호출은 표시 결과, 마지막 호출은 입력 추정. 제외한 단지와 분할이 같아야 한다.
    assert fit_indices[0] == fit_indices[-1]
    assert not set(frame.index[:10]).intersection(fit_indices[-1])


def test_regional_prediction_checks_model_after_second_load(unordered_connection, monkeypatch):
    from fastapi import HTTPException
    from app.collective.regional_regression.schemas import RegionalRegressionPredictRequest
    conn, _ = unordered_connection
    req = request()
    fit = engine.run_regional_regression(conn, req, with_recommendation=False)
    pred_req = RegionalRegressionPredictRequest(**req.model_dump(), expected_model_signature=fit.analysis.model_signature)
    inputs = RegionalRegressionPredictInputs(households=220, max_floor=15, building_age=10, asset_type="apartment")
    engine.predict_regional(conn, pred_req, inputs)
    load = engine.load_danji_frame
    calls = 0
    def changing_load(*args):
        nonlocal calls
        calls += 1
        frame, meta = load(*args)
        if calls == 2:
            frame["median"] *= 1.2
        return frame, meta
    monkeypatch.setattr(engine, "load_danji_frame", changing_load)
    with pytest.raises(HTTPException) as exc:
        engine.predict_regional(conn, pred_req, inputs)
    assert exc.value.status_code == 409


@pytest.mark.parametrize("region_dummy", [False, True])
def test_extension_scores_same_original_region_holdout_without_training_leakage(
    unordered_connection, monkeypatch, region_dummy,
):
    import pandas as pd
    conn, _ = unordered_connection
    frame, _ = engine.load_danji_frame(conn, request())
    neighbor = frame.copy()
    neighbor["building_key"] = "neighbor-" + neighbor.building_key.astype(str)
    neighbor["addr3"] = "역삼동"
    neighbor["median"] *= 1.1
    work = pd.concat([frame, neighbor], ignore_index=True)
    req = request().model_copy(update={"region_dummy": region_dummy,
        "region_addrs": ["서울특별시|강남구|삼성동", "서울특별시|강남구|역삼동"],
        "evaluation_region_addrs": ["서울특별시|강남구|삼성동"]})
    fit = engine._fit_ols
    calls = []
    def record(work, x, **kwargs):
        calls.append((set(kwargs["train_idx"]), set(kwargs["hold_idx"])))
        return fit(work, x, **kwargs)
    monkeypatch.setattr(engine, "_fit_ols", record)
    result = engine._extension_comparison(work, req)
    assert result.status == "available" and result.evaluation_signature
    assert (result.fit_before_n, result.fit_after_n, result.evaluation_n) == (48, 112, 16)
    assert calls[0][1] == calls[1][1]
    assert not calls[0][0].intersection(calls[0][1])
    assert not calls[1][0].intersection(calls[1][1])
    assert calls[0][1].issubset(set(frame.index))
    assert engine._extension_comparison(work, req.model_copy(update={
        "evaluation_region_addrs": ["서울특별시|강남구|없는동"]})).status == "unavailable"


@pytest.mark.parametrize("count", [0, 24, 64])
def test_loader_and_split_ignore_database_row_order(unordered_connection, count):
    conn, state = unordered_connection
    state["count"] = count
    expected = None
    for seed in (1, 11, 29):
        state["order"] = np.random.default_rng(seed).permutation(64)
        df, _ = engine.load_danji_frame(conn, request())
        train, hold = engine._split_hold(df.index)
        def identities(index):
            return list(df.loc[index, ["asset_type", "building_key"]].itertuples(index=False, name=None))
        actual = (identities(train), identities(hold))
        if expected is None:
            expected = actual
        assert actual == expected
        assert len(train) + len(hold) == count
        assert len(hold) == (16 if count == 64 else 0)


@pytest.mark.parametrize("households", [None, -1, 0])
def test_regional_prediction_requires_actual_numeric_input(unordered_connection, households):
    conn, _ = unordered_connection
    with pytest.raises(ValueError, match="세대수"):
        engine.predict_regional(conn, request(), RegionalRegressionPredictInputs(
            households=households, max_floor=15, building_age=10, asset_type="apartment"))


@pytest.mark.parametrize("model_type,weight_mode", [("linear", "equal"), ("log", "tx")])
def test_regression_recommendations_and_prediction_ignore_row_order(
    unordered_connection, model_type, weight_mode,
):
    conn, state = unordered_connection
    req = request(model_type, weight_mode)
    inputs = RegionalRegressionPredictInputs(
        households=220, max_floor=15, building_age=10, asset_type="apartment",
    )
    baseline = None
    for seed in (1, 29):
        state["order"] = np.random.default_rng(seed).permutation(64)
        result = engine.run_regional_regression(conn, req)
        assert result.n == 48
        assert result.sample.n_hold == 16
        assert result.hold_mape is not None
        assert result.coefficients and result.model_candidates
        assert all(row.transaction_n is not None and row.transaction_n >= req.min_tx for row in result.fitted)
        assert result.analysis is not None
        assert result.analysis.fit_n == 48
        assert result.analysis.fit_sample_signature is not None
        assert result.analysis.metrics[1].n == 16
        assert result.model_adj_r_squared is not None
        # predict_regional도 내부에서 두 번 조회하므로 매번 다른 순서를 제공한다.
        counter = 0
        original_execute = conn.execute
        def changing_execute(*args, **kwargs):
            nonlocal counter
            counter += 1
            state["order"] = np.random.default_rng(seed + counter).permutation(64)
            return original_execute(*args, **kwargs)
        conn.execute = changing_execute
        try:
            prediction = engine.predict_regional(conn, req, inputs)
        finally:
            conn.execute = original_execute
        actual = (result.model_dump(), prediction)
        if baseline is None:
            baseline = actual
        assert actual == baseline
