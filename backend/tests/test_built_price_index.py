"""시군구 가격시점 지수 — 시간 보정 계층 (D-075)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.built.regression.price_index import (
    MIN_ROWS_PER_YEAR,
    deflate_prices,
    estimate_year_index,
    last_complete_year,
)


def _frame(
    *,
    years: tuple[int, ...] = (2021, 2022, 2023, 2024, 2025),
    drift: float = 0.10,
    per_year: int = 40,
    noise: float = 0.08,
    seed: int = 3,
) -> pd.DataFrame:
    """연 `drift`만큼 로그 가격이 오르는 표본. 구조 관계는 모든 해에 동일."""
    rng = np.random.default_rng(seed)
    rows = []
    for i, y in enumerate(years):
        gross = rng.uniform(50, 400, per_year)
        land = gross * rng.uniform(0.4, 0.9, per_year)
        age = rng.integers(1, 30, per_year).astype(float)
        log_p = (
            7.0
            + 0.9 * np.log(gross)
            + 0.2 * np.log(land)
            - 0.01 * age
            + drift * i
            + rng.normal(0, noise, per_year)
        )
        for j in range(per_year):
            rows.append(
                {
                    "price": float(np.exp(log_p[j])),
                    "gross_area": float(gross[j]),
                    "land_area": float(land[j]),
                    "building_age": float(age[j]),
                    "contract_year": int(y),
                }
            )
    return pd.DataFrame(rows)


def test_recovers_known_drift():
    """연 10% 로그 상승을 심으면 환산 배수가 그만큼 나온다."""
    idx = estimate_year_index(_frame(drift=0.10))
    assert idx.available
    assert idx.base_year == 2025
    assert idx.factor(2025) == pytest.approx(1.0)
    # 2021은 기준보다 4구간 낮으므로 exp(0.4) ≈ 1.49배로 올려야 한다.
    assert idx.factor(2021) == pytest.approx(np.exp(0.40), rel=0.05)
    assert idx.factor(2023) == pytest.approx(np.exp(0.20), rel=0.05)
    # 단조 증가하는 시장이면 과거일수록 배수가 크다.
    assert idx.factor(2021) > idx.factor(2022) > idx.factor(2023) > idx.factor(2025)


def test_flat_market_gives_unit_factors():
    """추세가 없으면 배수가 1이고, 수축이 연도 효과를 지워 보정 없음으로 떨어진다."""
    idx = estimate_year_index(_frame(drift=0.0))
    for y in (2021, 2022, 2023, 2024, 2025):
        assert idx.factor(y) == pytest.approx(1.0, abs=0.05)
    assert not idx.available


def test_future_year_carries_forward_without_extrapolating():
    """학습 구간 뒤의 연도는 추세를 연장하지 않고 마지막 수준을 이어 쓴다.

    미래 지수는 알 수 없다. 추세를 연장하면 모르는 것을 아는 것처럼 만들고 그 오차가
    구조 계수 평가에 섞인다.
    """
    idx = estimate_year_index(_frame(years=(2021, 2022, 2023)), base_year=2023)
    assert idx.available
    assert idx.factor(2026) == idx.factor(2023) == pytest.approx(1.0)
    assert idx.factor(2019) == idx.factor(2021)


def test_holdout_year_can_be_excluded():
    """CV는 학습 연도만 넘긴다 — holdout 연도가 지수에 섞이면 누수다 (D-075)."""
    df = _frame()
    train = estimate_year_index(df, years=[2021, 2022, 2023, 2024])
    assert train.available
    assert train.base_year == 2024
    assert 2025 not in train.factors
    # 2025(holdout)는 마지막 학습 연도 수준으로만 환산된다.
    assert train.factor(2025) == train.factor(2024)


def test_thin_years_are_skipped():
    """연도별 표본이 얇으면 보정을 포기한다 — 잘못된 보정보다 보정 없음이 낫다."""
    idx = estimate_year_index(_frame(per_year=MIN_ROWS_PER_YEAR - 5))
    assert not idx.available
    assert idx.note and "생략" in idx.note


def test_too_few_years_skipped():
    idx = estimate_year_index(_frame(years=(2024, 2025)))
    assert not idx.available


def test_deflate_removes_drift_and_keeps_nominal():
    df = _frame(drift=0.12)
    idx = estimate_year_index(df)
    out = deflate_prices(df, idx)

    assert "price_nominal" in out.columns
    # 원본 가격은 보존된다 — 거래목록은 명목가를 보여야 한다.
    assert out["price_nominal"].equals(pd.to_numeric(df["price"], errors="coerce"))

    # 환산 전에는 연도별 중위가가 계단처럼 오르고, 환산 후에는 평평해진다.
    before = df.groupby("contract_year")["price"].median()
    after = out.groupby("contract_year")["price"].median()
    spread_before = float(before.max() / before.min())
    spread_after = float(after.max() / after.min())
    assert spread_before > 1.3
    assert spread_after < spread_before
    assert spread_after < 1.2


def test_deflate_is_noop_without_index():
    df = _frame(years=(2024, 2025))
    idx = estimate_year_index(df)
    out = deflate_prices(df, idx)
    assert out is df
    assert "price_nominal" not in out.columns


def test_pure_noise_shrinks_to_no_adjustment():
    """연도차가 표본오차 수준이면 수축이 보정을 0으로 만든다.

    실측에서 시군구 연도별 표본이 수십 건인 지역이 많아 연도 계수 자체가 흔들렸고, 그
    잡음이 모든 거래가격에 곱해져 CV가 오히려 나빠졌다.
    """
    idx = estimate_year_index(_frame(drift=0.0, noise=0.5, per_year=35, seed=17))
    assert idx.shrink_keep_ratio < 0.3
    for y in (2021, 2022, 2023, 2024):
        assert idx.factor(y) == pytest.approx(1.0, abs=0.03)


def test_fully_shrunk_index_counts_as_no_adjustment():
    """배수가 전부 1이면 「환산했다」고 말하지 않는다."""
    idx = estimate_year_index(_frame(drift=0.0, noise=0.6, per_year=32, seed=41))
    if idx.shrink_keep_ratio < 0.05:
        assert not idx.available


def test_real_drift_survives_shrinkage():
    """시장이 실제로 움직였으면 수축이 거의 손대지 않는다."""
    idx = estimate_year_index(_frame(drift=0.12, per_year=60, seed=23))
    assert idx.shrink_keep_ratio > 0.9
    assert idx.factor(2021) == pytest.approx(np.exp(0.48), rel=0.08)


def test_incomplete_latest_year_is_not_the_base():
    """진행 중인 해를 기준시점으로 쓰지 않는다.

    운영 실측에서 2026년(거래 18~29건)이 기준으로 잡혀 수성구 예상값이 35% 내려갔다.
    빠진 해의 거래는 마지막 기준연도 수준으로 간주한다.
    """
    df = _frame(years=(2021, 2022, 2023, 2024, 2025))
    idx = estimate_year_index(df, max_complete_year=2024)
    assert idx.available
    assert idx.base_year == 2024
    assert 2025 not in idx.factors
    assert idx.factor(2025) == idx.factor(2024) == pytest.approx(1.0)


def test_last_complete_year_needs_december():
    assert last_complete_year("2026-09") == 2025
    assert last_complete_year("2026-12") == 2026
    assert last_complete_year("2025-01") == 2024


def test_yearly_change_pct_reads_as_market_level():
    idx = estimate_year_index(_frame(drift=0.10))
    changes = dict(idx.yearly_change_pct())
    assert changes[2025] == pytest.approx(0.0, abs=0.5)
    # 2021년 가격 수준은 기준시점보다 낮다.
    assert changes[2021] < -25
