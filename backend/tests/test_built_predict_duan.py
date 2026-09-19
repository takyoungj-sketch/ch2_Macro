"""log 계열 예측 역변환 — Duan smearing 적용 범위 (D-074).

점추정·평균CI에는 보정을 곱하고 예측구간에는 곱하지 않는다. 예전에는 예측값이
`exp(ŷ)`뿐이어서 같은 화면의 MAPE·CV-MAPE(보정 기준)와 다른 추정량을 가리켰다.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from app.built.regression import engine as eng
from app.built.schemas import RegressionPredictRequest, RegressionVariableSpec

_VARS = RegressionVariableSpec(
    gross_area=True,
    land_area=False,
    building_age=True,
    road_width_dummy=False,
    zone_type_dummy=False,
    building_use_dummy=False,
    structure_dummy=False,
    asset_type_dummy=False,
)


def _scope_df(n: int = 120, noise: float = 0.35) -> pd.DataFrame:
    """log(금액)이 면적·연식의 선형함수 + 넓은 잔차인 표본.

    잔차가 넓어야 smearing 계수가 1에서 뚜렷하게 떨어져 검증에 의미가 생긴다.
    """
    rng = np.random.default_rng(7)
    gross = np.linspace(40.0, 400.0, n)
    age = np.tile(np.arange(1, 21), n // 20)[:n].astype(float)
    log_price = 7.0 + 0.9 * np.log(gross) - 0.01 * age + rng.normal(0.0, noise, n)
    return pd.DataFrame(
        {
            "price": np.exp(log_price),
            "gross_area": gross,
            "land_area": gross * 0.6,
            "building_age": age,
            "road_width_label": "8m",
            "zone_type": "일반",
            "building_use": "근린",
            "asset_type": "commercial",
            "contract_year": np.tile([2021, 2022, 2023, 2024, 2025], n // 5)[:n],
            "addr1": "서울특별시",
            "addr2": "강남구",
            "addr3": "역삼동",
        }
    )


@pytest.fixture
def patched_scope(monkeypatch):
    """DB 없이 예측 경로를 돌린다 — scope 해석만 고정 표본으로 대체."""
    df = _scope_df()

    def _prepare(_conn, req):
        return df, req, False, "single", 0

    monkeypatch.setattr(eng, "_prepare_regression_scope", _prepare)
    monkeypatch.setattr(
        eng, "_scope_for_level", lambda wide_df, *a, **k: wide_df  # noqa: ARG005
    )
    return df


def _request(scale: str) -> RegressionPredictRequest:
    return RegressionPredictRequest(
        admin_level="sigungu",
        addr1="서울특별시",
        addr2="강남구",
        response_scale=scale,  # type: ignore[arg-type]
        variables=_VARS,
        gross_area=200.0,
        building_age=10.0,
    )


def test_log_prediction_applies_duan_to_point_and_mean_ci(patched_scope):
    out = eng.predict_regression(None, _request("log"))

    assert out.duan_factor is not None
    # 잔차가 넓으면 exp의 평균은 1보다 확실히 크다 (Jensen).
    assert out.duan_factor > 1.02

    # 예측구간은 보정하지 않으므로 log 척도에서 mean을 중심으로 대칭이다.
    # 따라서 기하중심 sqrt(pi_lo × pi_hi) = exp(ŷ)이고, 점추정을 그것으로 나누면
    # 정확히 smearing 계수가 나온다. 보정이 빠지면 이 값이 1이 된다.
    pi_center = math.sqrt(out.pi_lower * out.pi_upper)
    assert out.y_hat / pi_center == pytest.approx(out.duan_factor, rel=1e-6)

    # 평균 CI도 같은 계수로 이동한다.
    ci_center = math.sqrt(out.ci_lower * out.ci_upper)
    assert ci_center / pi_center == pytest.approx(out.duan_factor, rel=1e-6)

    assert out.ci_lower < out.y_hat < out.ci_upper
    assert out.pi_lower < out.pi_upper
    assert any("평균 보정" in w for w in out.warnings)


def test_loglog_prediction_also_applies_duan(patched_scope):
    out = eng.predict_regression(None, _request("loglog"))

    assert out.duan_factor is not None and out.duan_factor > 1.0
    pi_center = math.sqrt(out.pi_lower * out.pi_upper)
    assert out.y_hat / pi_center == pytest.approx(out.duan_factor, rel=1e-6)


def test_linear_prediction_has_no_duan_factor(patched_scope):
    out = eng.predict_regression(None, _request("linear"))

    assert out.duan_factor is None
    # 선형은 역변환이 없으므로 점추정이 평균CI·PI의 산술 중심이다.
    assert out.y_hat == pytest.approx((out.pi_lower + out.pi_upper) / 2, rel=1e-6)
    assert not any("평균 보정" in w for w in out.warnings)
