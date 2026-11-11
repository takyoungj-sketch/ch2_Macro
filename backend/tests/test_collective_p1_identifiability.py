"""집합 1단계 Phase 2 — C-03 회귀 식별 불가 변수 자동 제외.

단위 4종(연식↔시점, 면적 단일, 동 미상↔최근 반기, 식별 가능) + 층 효용지수 일관성
+ 실데이터(0단계 표본 51곳, 가경자이). 실데이터는 로컬 DB·logs 산출물이 없으면 skip.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from sqlalchemy import text

from app.collective.floor_index_regression import compute_residential_floor_index_regression
from app.collective.regression import engine
from app.collective.schemas import (
    CollectiveRegressionPredictInputs,
    CollectiveRegressionRequest,
    CollectiveRegressionSpec,
)


def _spec(**flags):
    base = dict(
        exclusive_area=True, building_age=False, floor=False, dong=False,
        contract_period=False, housing_subtype=False, structure=False,
    )
    base.update(flags)
    return CollectiveRegressionSpec(**base)


def _rows(n, *, year, month, age, dong=None, area=None, effect=0.0, seed=0):
    rng = np.random.default_rng(seed)
    a = np.full(n, 84.0) if area is not None else rng.uniform(40, 120, n)
    return pd.DataFrame({
        "transaction_id": np.arange(seed * 1000, seed * 1000 + n),
        "exclusive_area": a,
        "price": 1000 * a + effect + rng.normal(0, 50, n),
        "floor": rng.integers(1, 20, n).astype(float),
        "building_age": float(age),
        "contract_year": year,
        "contract_month": month,
        "dong": dong,
        "asset_type": "apartment",
    })


def _fit(df, **flags):
    req = CollectiveRegressionRequest(asset_type="apartment", model_type="linear", variables=_spec(**flags))
    _m, _x, _meta, fit = engine._run_regression_core(df, req)
    return req, fit


def _r2_equal(fit):
    ident = fit.identifiability
    assert ident is not None
    assert ident.rank_after == ident.cols_after
    assert ident.r_squared_before == pytest.approx(ident.r_squared_after, abs=1e-9)


def test_age_collinear_with_period_drops_age_keeps_period():
    df = pd.concat([
        _rows(20, year=y, month=m, age=y - 2010, effect=300 * i, seed=i)
        for i, (y, m) in enumerate([(2022, 3), (2022, 9), (2023, 3), (2023, 9)])
    ], ignore_index=True)
    _req, fit = _fit(df, building_age=True, contract_period=True)
    assert [e.variable for e in fit.excluded_variables] == ["building_age"]
    assert fit.excluded_variables[0].reason_code == "age_collinear_period"
    assert "한 단지 안에서는" in fit.excluded_variables[0].message
    names = {c.name for c in fit.coefficients}
    assert "building_age" not in names
    assert sum(n.startswith("time_") for n in names) == 3
    _r2_equal(fit)
    assert not any("모형 식별" in w for w in fit.warnings)


def test_single_area_drops_area():
    df = pd.concat([
        _rows(25, year=2024, month=m, age=10, area=84.0, effect=200 * i, seed=i)
        for i, m in enumerate([3, 9])
    ], ignore_index=True)
    _req, fit = _fit(df, exclusive_area=True, contract_period=True)
    assert [e.variable for e in fit.excluded_variables] == ["exclusive_area"]
    assert fit.excluded_variables[0].reason_code == "area_single"
    assert fit.excluded_variables[0].message == "이 단지는 전용면적이 한 종류라 면적 효과를 추정하지 않았습니다."
    _r2_equal(fit)


def test_dong_unknown_collinear_with_recent_period_drops_unknown_keeps_period():
    early = [
        _rows(15, year=2024, month=3, age=10, dong="101동", seed=1),
        _rows(15, year=2024, month=3, age=10, dong="102동", effect=500, seed=2),
        _rows(15, year=2024, month=9, age=10, dong="101동", seed=3),
        _rows(15, year=2024, month=9, age=10, dong="102동", effect=500, seed=4),
    ]
    recent = _rows(12, year=2026, month=9, age=10, dong=None, effect=900, seed=5)
    df = pd.concat([*early, recent], ignore_index=True)
    _req, fit = _fit(df, dong=True, contract_period=True)
    assert [e.variable for e in fit.excluded_variables] == ["dong_unknown"]
    assert fit.excluded_variables[0].reason_code == "dong_unknown_collinear_period"
    names = {c.name for c in fit.coefficients}
    assert "time_2026H2" in names
    assert "dong_102동" in names
    _r2_equal(fit)


def test_identifiable_design_unchanged():
    df = pd.concat([
        _rows(20, year=2024, month=m, age=a, effect=100 * i, seed=i)
        for i, (m, a) in enumerate([(3, 10), (9, 10), (3, 12), (9, 12)])
    ], ignore_index=True)
    req, fit = _fit(df, building_age=True, contract_period=True)
    assert fit.excluded_variables == []
    assert fit.identifiability is None
    with engine.auto_exclusion_disabled():
        _m, _x, _meta, off = engine._run_regression_core(df, req)
    assert [c.name for c in fit.coefficients] == [c.name for c in off.coefficients]
    assert [c.coef for c in fit.coefficients] == pytest.approx([c.coef for c in off.coefficients])
    assert fit.r_squared == pytest.approx(off.r_squared)


def test_floor_index_and_regression_agree_on_age():
    """층 효용지수의 기존 연식 가드와 회귀 자동 제외가 같은 단지에서 같은 판단을 한다."""
    frames = []
    for year, month in ((2023, 3), (2023, 9), (2024, 3), (2024, 9)):
        for floor, unit in ((1, 100.0), (2, 120.0)):
            frames.append(pd.DataFrame({
                "unit_price": [unit] * 8, "exclusive_area": [50.0] * 4 + [60.0] * 4,
                "price": [unit * 50.0] * 4 + [unit * 60.0] * 4,
                "building_age": [float(year - 2000)] * 8, "building_year": [2000] * 8,
                "contract_year": [year] * 8, "contract_month": [month] * 8, "floor": [floor] * 8,
            }))
    df = pd.concat(frames, ignore_index=True)
    raw = compute_residential_floor_index_regression(df, asset_type="apartment", dimension="floor", floor_mode="dummy")
    assert "building_age" not in raw["controls"]
    _req, fit = _fit(df.assign(transaction_id=range(len(df))), building_age=True, contract_period=True, floor=True,
                     floor_mode="dummy")
    assert "building_age" in [e.variable for e in fit.excluded_variables]


def test_predict_ignores_excluded_age_input():
    df = pd.concat([
        _rows(20, year=y, month=m, age=y - 2010, effect=300 * i, seed=i)
        for i, (y, m) in enumerate([(2022, 3), (2022, 9), (2023, 3), (2023, 9)])
    ], ignore_index=True)
    req, _fit_resp = _fit(df, building_age=True, contract_period=True)
    a = engine.predict_regression(df, req, CollectiveRegressionPredictInputs(exclusive_area=80, building_age=5))
    b = engine.predict_regression(df, req, CollectiveRegressionPredictInputs(exclusive_area=80, building_age=30))
    assert a["y_hat"] == b["y_hat"]
    assert any("연식 입력은 반영하지 않았습니다" in w for w in b["warnings"])


def test_rent_path_keeps_current_behaviour():
    df = pd.concat([
        _rows(20, year=y, month=m, age=y - 2010, seed=i)
        for i, (y, m) in enumerate([(2022, 3), (2022, 9), (2023, 3), (2023, 9)])
    ], ignore_index=True)
    req = CollectiveRegressionRequest(asset_type="apartment", model_type="linear",
                                      variables=_spec(building_age=True, contract_period=True))
    with engine.auto_exclusion_disabled():
        _m, _x, _meta, fit = engine._run_regression_core(df, req)
    assert fit.excluded_variables == []
    assert any(c.name == "building_age" for c in fit.coefficients)


# ---------------- 실데이터 ----------------

ROOT = Path(__file__).resolve().parents[2]
C03 = ROOT / "logs" / "collective_phase0" / "c03_detail.csv"
W0, W1 = date(2021, 11, 1), date(2026, 10, 31)
GAGYEONG_XI = "af6811fc56f7e9f309657ec6ff5b378aa548e7d334af8f3ff9dda965456916be"

_SQL = text(
    """SELECT id AS transaction_id, price, unit_price, exclusive_area, building_age, floor, dong, housing_subtype,
              contract_year, contract_month
       FROM collective_transactions
       WHERE building_key = :bk AND is_valid = true AND contract_date >= :d0 AND contract_date <= :d1"""
)


@pytest.fixture(scope="module")
def ceng():
    from app.collective.db import get_collective_engine

    eng = get_collective_engine()
    if eng is None:
        pytest.skip("COLLECTIVE_DATABASE_URL not configured")
    return eng


def _product(conn, bk, model_type="linear"):
    df = pd.DataFrame(conn.execute(_SQL, {"bk": bk, "d0": W0, "d1": W1}).mappings().all())
    req = CollectiveRegressionRequest(asset_type="apartment", model_type=model_type, contract_date_from=W0, contract_date_to=W1)
    after = engine.run_building_regression(df, bk, bk[:8], req)
    with engine.auto_exclusion_disabled():
        before = engine.run_building_regression(df, bk, bk[:8], req)
    return before, after


def test_db_phase0_51_sites_identifiable_after_exclusion(ceng):
    if not C03.exists():
        pytest.skip("logs/collective_phase0/c03_detail.csv 없음")
    d = pd.read_csv(C03, encoding="utf-8-sig")
    keys = d.loc[d.cause != "식별 가능", "key"].tolist()
    assert len(keys) == 51
    unresolved, r2_diff, cv_diff = [], [], []
    with ceng.connect() as c:
        for bk in keys:
            before, after = _product(c, bk)
            ident = after.identifiability
            if ident is not None and ident.rank_after < ident.cols_after:
                unresolved.append(bk)
            if before.r_squared is not None and abs((after.r_squared or 0) - before.r_squared) > 1e-6:
                r2_diff.append(bk)
            if (before.cv_mape is None) != (after.cv_mape is None) or (
                before.cv_mape is not None and abs(after.cv_mape - before.cv_mape) > 0.05
            ):
                cv_diff.append(bk)
    assert unresolved == []
    assert r2_diff == []
    assert cv_diff == []


def test_db_gagyeong_xi_drops_age_keeps_period(ceng):
    with ceng.connect() as c:
        if c.execute(text("SELECT 1 FROM collective_transactions WHERE building_key = :bk LIMIT 1"), {"bk": GAGYEONG_XI}).first() is None:
            pytest.skip("가경자이 거래 없음")
        before, after = _product(c, GAGYEONG_XI)
    age = [x for x in before.coefficients if x.name == "building_age"]
    assert age and age[0].p is None  # 제외 전: 임의값, p값 없음
    assert any("모형 식별" in w for w in before.warnings)
    assert [e.variable for e in after.excluded_variables] == ["building_age"]
    assert after.excluded_variables[0].message.startswith("한 단지 안에서는 연식이")
    assert all(x.name != "building_age" for x in after.coefficients)
    before_t = {x.name: x.coef for x in before.coefficients if x.name.startswith("time_")}
    after_t = {x.name: x.coef for x in after.coefficients if x.name.startswith("time_")}
    assert set(after_t) == set(before_t) and after_t
    assert not any("모형 식별" in w for w in after.warnings)
    assert after.r_squared == pytest.approx(before.r_squared, abs=1e-9)
