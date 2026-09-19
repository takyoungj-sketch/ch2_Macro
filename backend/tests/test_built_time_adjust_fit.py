"""시점 보정이 적합·CV에 실제로 걸리는지, 그리고 holdout이 새지 않는지 (D-075)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.built.regression.price_index import TimeAdjuster
from app.built.regression.selection.fit import fit_block_subset

YEARS = (2021, 2022, 2023, 2024, 2025)
BLOCKS = ["gross_area", "building_age"]


def _rising_market(*, drift: float = 0.15, per_year: int = 60, seed: int = 11) -> pd.DataFrame:
    """구조 관계는 모든 해에 같고 가격 수준만 매년 오르는 표본."""
    rng = np.random.default_rng(seed)
    rows = []
    for i, year in enumerate(YEARS):
        gross = rng.uniform(60, 400, per_year)
        age = rng.integers(1, 30, per_year).astype(float)
        log_p = (
            8.0
            + 0.95 * np.log(gross)
            - 0.012 * age
            + drift * i
            + rng.normal(0, 0.10, per_year)
        )
        for j in range(per_year):
            rows.append(
                {
                    "price": float(np.exp(log_p[j])),
                    "gross_area": float(gross[j]),
                    "building_age": float(age[j]),
                    "contract_year": int(year),
                    "zone_type": "제2종일반주거지역",
                    "road_width_label": "12m미만",
                }
            )
    return pd.DataFrame(rows)


def _drifting_composition(
    *,
    area_elasticity: float,
    drift: float = 0.15,
    per_year: int = 60,
    seed: int = 5,
) -> pd.DataFrame:
    """가격 수준이 오르는 동시에 거래 물건이 점점 커지는 표본.

    연도와 면적이 상관되므로, 시간을 통제하지 않으면 면적 계수가 추세를 흡수한다.
    """
    rng = np.random.default_rng(seed)
    rows = []
    for i, year in enumerate(YEARS):
        lo = 60 + 45 * i
        gross = rng.uniform(lo, lo + 160, per_year)
        age = rng.integers(1, 30, per_year).astype(float)
        log_p = (
            8.0
            + area_elasticity * np.log(gross)
            - 0.012 * age
            + drift * i
            + rng.normal(0, 0.08, per_year)
        )
        for j in range(per_year):
            rows.append(
                {
                    "price": float(np.exp(log_p[j])),
                    "gross_area": float(gross[j]),
                    "building_age": float(age[j]),
                    "contract_year": int(year),
                    "zone_type": "제2종일반주거지역",
                    "road_width_label": "12m미만",
                }
            )
    return pd.DataFrame(rows)


def _fit(df: pd.DataFrame, adjuster: TimeAdjuster | None):
    return fit_block_subset(
        df,
        BLOCKS,
        unified=False,
        response_scale="loglog",
        region_col=None,
        admin_level="sigungu",
        time_adjuster=adjuster,
    )


def test_time_adjust_improves_cv_on_a_rising_market():
    """상승장에서 시점 보정은 CV를 개선한다.

    보정 전 모형은 창 전체의 평균 수준에 맞춰져 평가 연도보다 낮게 예측한다. 보정 후에는
    직전 연도 수준에 맞춰지므로 평가 연도에 더 가깝다.
    """
    df = _rising_market()
    plain = _fit(df, None)
    adjusted = _fit(df, TimeAdjuster(df))
    assert plain is not None and adjusted is not None
    assert plain.cv_mape is not None and adjusted.cv_mape is not None
    assert adjusted.cv_mape < plain.cv_mape


def test_time_adjust_removes_trend_absorbed_by_a_drifting_variable():
    """연도와 함께 움직이는 변수가 시간 추세를 대신 흡수하는 것을 막는다.

    보정 없이 5년을 한 번에 적합하면, 뒤 연도에 큰 건물이 더 많이 거래된 지역에서는
    면적 계수가 시장 상승분까지 빨아들여 부풀려진다. 구조 계수를 읽는 화면에서는 이게
    「이 지역은 면적 효과가 크다」로 잘못 보인다.
    """
    truth = 0.95
    df = _drifting_composition(area_elasticity=truth)
    plain = _fit(df, None)
    adjusted = _fit(df, TimeAdjuster(df))
    assert plain is not None and adjusted is not None

    plain_err = abs(float(plain.model.params["gross_area"]) - truth)
    adjusted_err = abs(float(adjusted.model.params["gross_area"]) - truth)
    assert plain_err > 0.05, "합성 표본에 편향이 안 심겼다 — 테스트 전제 확인"
    assert adjusted_err < plain_err / 2


def test_flat_market_is_left_alone():
    """추세가 없으면 보정이 결과를 흔들지 않는다."""
    df = _rising_market(drift=0.0)
    plain = _fit(df, None)
    adjusted = _fit(df, TimeAdjuster(df))
    assert adjusted.cv_mape == pytest.approx(plain.cv_mape, abs=1.5)


def test_cv_never_sees_the_year_it_evaluates():
    """fold 지수는 그 fold의 학습 연도만으로 세워진다 — 전처리 누수 차단 (D-075).

    평가 연도가 지수 추정에 섞이면 국소 모형이 그 해를 못 봤어도 가격 수준 정보를 받아,
    확인 CV가 실제보다 좋아진다.
    """
    df = _rising_market()

    class _Spy(TimeAdjuster):
        def __init__(self, frame):
            super().__init__(frame)
            self.asked: list[tuple[int, ...]] = []

        def for_train_years(self, years):
            key = tuple(sorted(int(y) for y in years))
            self.asked.append(key)
            return super().for_train_years(key)

    spy = _Spy(df)
    _fit(df, spy)

    assert spy.asked, "CV가 fold 지수를 요청하지 않았다"
    # rolling CV는 test_year 미만을 학습에 쓴다. 요청된 연도 집합은 연속 접두사여야 하고,
    # 그 다음 해(평가 연도)를 포함하면 안 된다.
    for key in spy.asked:
        assert key == tuple(range(min(key), max(key) + 1))
        assert max(key) < YEARS[-1] or len(key) == len(YEARS) - 1

    # 마지막 연도(확인 holdout)를 평가하는 fold의 학습 집합은 그 앞 4개 연도뿐이다.
    assert (2021, 2022, 2023, 2024) in spy.asked
    # 평가 연도까지 포함한 집합을 요청한 적은 없다.
    assert all(YEARS[-1] not in key for key in spy.asked)


def test_no_adjuster_keeps_previous_behaviour():
    """time_adjuster=None이면 P4 이전과 동일 — 롤백 경로가 살아 있다."""
    df = _rising_market()
    a = _fit(df, None)
    b = _fit(df, None)
    assert a.cv_mape == b.cv_mape
    assert "price_nominal" not in df.columns


def test_time_adjust_is_off_by_default():
    """제품 경로는 시점 보정을 쓰지 않는다 (D-075 보류).

    5년 창 실측에서 adj R²·MAPE 개선 근거가 없는데 가격 수준은 20~37% 움직였고, 그 이동은
    CV로 검증할 수단이 없다. 실수로 기본이 켜지면 화면 예상값이 조용히 20%대로 바뀐다.
    """
    from app.built.regression.selection.context import SelectionContext
    from app.built.schemas import (
        RegressionPredictRequest,
        RegressionRunRequest,
        RegressionSelectionRequest,
    )

    assert RegressionRunRequest().time_adjust is False
    assert RegressionSelectionRequest().time_adjust is False
    assert RegressionPredictRequest(admin_level="sigungu").time_adjust is False
    # 컨텍스트 기본도 보정 없음 — 옛 호출부가 인자를 안 넘겨도 켜지지 않는다.
    assert (
        SelectionContext(
            df=_rising_market(),
            scope_label="t",
            admin_level="sigungu",
            addr4_city=False,
            mode="sigungu_only",
            unified=False,
        ).time_adjuster
        is None
    )
