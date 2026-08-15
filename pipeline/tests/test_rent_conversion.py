"""rent 전환율 4후보·게이트 단위 테스트."""

from __future__ import annotations

import sys
from pathlib import Path

PIPE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PIPE))

from rent.conversion import (
    DEFAULT_METHOD,
    BuildingRateObs,
    building_obs_from_rows,
    candidate_rates,
    errors_vs_jeonse,
    jeonse_equiv_per_m2,
    monthly_equiv_per_m2,
    region_gate,
    select_rate,
)


def _rows(jeonse_deps: list[float], mixed: list[tuple[float, float]]) -> list[dict]:
    rows = []
    for d in jeonse_deps:
        rows.append(
            {
                "building_key": "b1",
                "deposit_per_m2": d,
                "monthly_per_m2": 0.0,
            }
        )
    for d, m in mixed:
        rows.append(
            {
                "building_key": "b1",
                "deposit_per_m2": d,
                "monthly_per_m2": m,
            }
        )
    return rows


def test_building_obs_requires_both_sides():
    assert building_obs_from_rows(_rows([100, 101, 102], [(80, 1.0)])) is None
    obs = building_obs_from_rows(
        _rows([100, 101, 102], [(80, 1.0), (81, 1.1), (79, 0.9)])
    )
    assert obs is not None
    assert obs.j_m2 == 101.0
    assert obs.d_m2 == 80.0
    assert obs.m_m2 == 1.0


def test_default_method_is_mean_simple():
    assert DEFAULT_METHOD == "mean_simple"
    obs = [
        BuildingRateObs("a", 100, 80, 0.1, 10, 10),
        BuildingRateObs("b", 200, 100, 0.5, 10, 10),
    ]
    cand = candidate_rates(obs)
    assert select_rate(cand) == cand["r_mean_simple"]


def test_ols_origin_matches_manual():
    obs = [
        BuildingRateObs("a", 100, 80, 0.1, 10, 10),
        BuildingRateObs("b", 200, 160, 0.2, 10, 10),
    ]
    cand = candidate_rates(obs)
    assert cand["r_ols_origin"] == 6.0
    assert select_rate(cand, method="ols_origin") == 6.0


def test_region_gate():
    obs = [BuildingRateObs("a", 100, 80, 1.0, 10, 10)] * 5
    ok, nb, nj, nm = region_gate(obs)
    assert ok
    assert nb == 5
    assert nj == 50
    assert nm == 50
    thin = [BuildingRateObs("a", 100, 80, 0.1, 5, 5)] * 3
    assert region_gate(thin, level="dong")[0]
    assert not region_gate(thin, level="sigungu")[0]


def test_errors_vs_jeonse_zero_when_r_matches():
    obs = [BuildingRateObs("a", 100, 80, 0.1, 10, 10)]
    err = errors_vs_jeonse(obs, 6.0)
    assert err["n"] == 1
    assert err["mae"] == 0.0
    assert err["median_ae"] == 0.0


def test_rb_distribution_bands():
    from rent.report_rb_distribution import _band

    assert _band(0.4, 0.2) == "stable"
    assert _band(1.2, 0.6) == "mild"
    assert _band(2.0, 1.5) == "unstable"


def test_equiv_formulas():
    r = 6.0
    assert jeonse_equiv_per_m2(deposit_per_m2=100, monthly_per_m2=0, r_pct=r) == 100
    assert jeonse_equiv_per_m2(deposit_per_m2=80, monthly_per_m2=1.0, r_pct=r) == 280.0
    assert monthly_equiv_per_m2(deposit_per_m2=80, monthly_per_m2=1.0, r_pct=r) == 1.4
