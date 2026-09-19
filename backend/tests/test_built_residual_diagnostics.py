"""잔차 진단 (P5) — 심어 둔 결함을 실제로 찾아내는지 본다.

진단이 «돌아간다»는 것만 확인하면 의미가 없다. 각 테스트는 자료에 결함을 하나 심고
진단이 그 결함을 지목하는지, 그리고 결함이 없을 때 조용한지를 함께 본다.
"""

import numpy as np
import pandas as pd
import pytest

from app.built.regression.engine import _fit_ols
from app.built.regression.residuals import MIN_GROUP_N
from app.built.schemas import RegressionVariableSpec

# 더미는 명시적으로 끈다. `RegressionVariableSpec`은 zone/use/struct/road 더미가 기본 True라,
# 끄지 않으면 모형이 용도지역을 이미 흡수해 「누락 변수」 결함을 심을 수 없다.
SPEC = RegressionVariableSpec(
    gross_area=True,
    land_area=True,
    building_age=True,
    road_width_dummy=False,
    zone_type_dummy=False,
    building_use_dummy=False,
    structure_dummy=False,
    asset_type_dummy=False,
)


def _rows(n=400, seed=0, *, zone_bump=None, proportional_noise=False, drift=None):
    """연면적·대지·연식으로 가격이 결정되는 합성 상가 표본.

    zone_bump: {용도지역: 배수} — 모형에 없는 변수로 가격을 올려 집단 편향을 만든다.
    proportional_noise: 오차를 가격에 비례시킨다.

    기본(절대 오차)과 `proportional_noise`(비례 오차)의 차이가 중요하다. **백분율** 척도에서
    비례 오차는 오히려 평평해지고, 금액대별 산포를 벌리는 것은 절대 오차다. 작은 거래는
    같은 절대 오차가 훨씬 큰 백분율이 되기 때문이다 — 운영 수성구에서 1분위 83% →
    5분위 43%로 나온 것이 이 형태다.
    """
    rng = np.random.default_rng(seed)
    zones = ["제2종일반주거", "일반상업", "준주거"]
    out = []
    for i in range(n):
        ga = float(rng.uniform(80, 600))
        la = float(rng.uniform(50, 400))
        age = float(rng.integers(0, 40))
        zone = zones[i % len(zones)]
        base = 3.2 * ga + 5.1 * la - 22.0 * age + 4000.0
        noise_sd = 400.0 * (ga / 300.0 if proportional_noise else 1.0)
        price = base * (zone_bump or {}).get(zone, 1.0) + rng.normal(0, noise_sd)
        out.append(
            {
                "price": max(price, 500.0),
                "gross_area": ga,
                "land_area": la,
                "building_age": age,
                "zone_type": zone,
                "building_use": "제1종근린생활시설",
                "asset_type": "commercial",
                "contract_year": 2021 + (i % 5),
                "addr1": "서울특별시",
                "addr2": "강남구",
                "addr3": f"{'가' if i % 2 else '나'}동",
                "addr4": None,
                "addr5": f"{i}-1",
            }
        )
    df = pd.DataFrame(out)
    if drift:
        df["price"] = df["price"] * (1 + drift * (df["contract_year"] - 2021))
    return df


def _diag(df, **kw):
    res = _fit_ols(df, SPEC, "sigungu", "강남구", with_residuals=True, **kw)
    assert res.residuals is not None, "진단이 만들어지지 않았다"
    return res.residuals


def _set(diag, key):
    for s in diag.groups:
        if s.key == key:
            return s
    return None


def test_group_bias_finds_an_omitted_variable():
    """모형에 없는 변수가 가격을 올리면 그 집단 편향이 유의하게 잡혀야 한다.

    용도지역을 변수에서 뺀 채 일반상업만 가격을 30% 올렸다. 모형은 그 집단을 계속
    과소평가하므로 편향이 양수로 남는다 — 이게 「변수를 더 넣으라」는 신호다.
    """
    df = _rows(n=500, zone_bump={"일반상업": 1.3})
    zone = _set(_diag(df, response_scale="linear"), "zone_type")
    assert zone is not None
    hit = next(g for g in zone.groups if g.label == "일반상업")
    assert hit.excess_bias_pct > 5, f"과소평가를 못 잡았다: {hit.excess_bias_pct}"
    assert hit.significant
    # 편향이 큰 집단이 표 맨 위에 와야 한다.
    assert zone.groups[0].label == "일반상업"


def test_clean_data_leaves_no_significant_group_bias():
    """결함을 심지 않으면 집단 편향이 유의하지 않아야 한다 — 거짓 경보 방지."""
    diag = _diag(_rows(n=500, seed=7), response_scale="linear")
    zone = _set(diag, "zone_type")
    assert zone is not None
    flagged = [g.label for g in zone.groups if g.significant]
    assert not flagged, f"깨끗한 자료에서 편향을 잡았다: {flagged}"
    assert abs(diag.bias_pct) < 2


def test_thin_groups_are_withheld_not_reported():
    """최소 건수 미달 집단은 표에 넣지 않고 제외 건수로만 센다."""
    df = _rows(n=200, seed=3)
    df.loc[df.index[:4], "zone_type"] = "자연녹지"  # 4건뿐
    zone = _set(_diag(df, response_scale="linear"), "zone_type")
    assert zone is not None
    assert "자연녹지" not in [g.label for g in zone.groups]
    assert zone.omitted_n >= 4
    assert all(g.n >= MIN_GROUP_N for g in zone.groups)


def test_absolute_noise_makes_small_deals_worse():
    """절대 오차 자료에서는 금액이 작은 쪽 산포가 커지고, 문구가 그 방향을 말해야 한다."""
    diag = _diag(_rows(n=600, seed=37), response_scale="linear")
    assert len(diag.scale_bins) >= 3
    spreads = [b.spread_pct for b in diag.scale_bins]
    assert spreads[0] > spreads[-1], f"작은 금액대가 더 나빠야 한다: {spreads}"
    assert diag.het_note and "금액이 작은 쪽" in diag.het_note


def test_flat_spread_is_not_called_heteroscedastic_on_test_alone():
    """분위 산포가 고르면 BP가 기각해도 「금액대에 따라 다르다」고 말하지 않는다.

    운영 강남구에서 BP p=0.000인데 분위 산포는 42~46%로 평평했다. 검정만 보고 문구를
    쓰면 사용자가 고가 물건 오차를 경계해야 한다고 잘못 읽는다.
    """
    diag = _diag(_rows(n=500, seed=11, proportional_noise=True), response_scale="linear")
    spreads = [b.spread_pct for b in diag.scale_bins]
    assert max(spreads) / min(spreads) < 1.4, f"백분율 산포가 평평해야 한다: {spreads}"
    assert diag.het_note and "고릅니다" in diag.het_note
    if diag.het_p_value is not None and diag.het_p_value < 0.05:
        assert "다른 변수 방향" in diag.het_note


def test_residual_definition_matches_screen_mape():
    """집단별 MAPE를 건수로 가중평균하면 화면 상단 MAPE와 같아야 한다.

    여기가 어긋나면 사용자는 같은 모형에 대해 서로 다른 오차율 두 개를 보게 된다.
    """
    df = _rows(n=400, seed=5)
    res = _fit_ols(df, SPEC, "sigungu", "강남구", with_residuals=True, response_scale="linear")
    diag = res.residuals
    zone = _set(diag, "zone_type")
    assert zone is not None and zone.omitted_n == 0
    weighted = sum(g.mape_pct * g.n for g in zone.groups) / sum(g.n for g in zone.groups)
    assert weighted == pytest.approx(res.mape, abs=0.6)


def test_influential_rows_are_ranked_and_refit_is_reported():
    """가격을 크게 비틀어 넣은 거래가 영향 상위로 올라오고 재적합 변화가 보고된다."""
    df = _rows(n=300, seed=13)
    df.loc[df.index[0], "gross_area"] = 3000.0  # 지렛대가 큰 관측
    df.loc[df.index[0], "price"] = 80000.0
    diag = _diag(df, response_scale="linear")
    assert diag.influential, "영향이 큰 거래를 못 찾았다"
    assert diag.influential[0].rank == 1
    assert diag.influential[0].cooks_d > 0
    # 비틀어 넣은 그 건이 1위여야 한다.
    assert diag.influential[0].label.endswith("0-1")
    assert diag.refit_shifts, "재적합 계수 변화가 비었다"
    assert diag.refit_note
    assert max(c.shift_se or 0 for c in diag.refit_shifts) > 1.0


def test_log_model_uses_duan_corrected_predictions():
    """log 모형에서도 오차%는 Duan 보정 예측 기준 — MAPE와 같은 정의."""
    df = _rows(n=400, seed=17)
    res = _fit_ols(df, SPEC, "sigungu", "강남구", with_residuals=True, response_scale="loglog")
    diag = res.residuals
    assert diag is not None
    # Duan 보정을 빼먹으면 예측이 체계적으로 낮아져 편향이 양수로 크게 치우친다.
    assert abs(diag.bias_pct) < 5, f"편향이 과하다 — Duan 누락 의심: {diag.bias_pct}"
    zone = _set(diag, "zone_type")
    weighted = sum(g.mape_pct * g.n for g in zone.groups) / sum(g.n for g in zone.groups)
    assert weighted == pytest.approx(res.mape, abs=0.8)


def test_global_percentage_skew_is_not_reported_as_group_bias():
    """백분율 오차의 전역 치우침을 집단 편향으로 착각하지 않아야 한다.

    운영 표본에서 평균 편향이 −12~−19%로 나오고 거의 모든 집단이 «유의»하게 찍혔다.
    모형 결함이 아니라 작은 거래에서 백분율 오차가 한쪽으로만 벌어지는 성질이다. 집단
    판정은 「나머지와 비교」라서 이 공통 치우침에 반응하지 않아야 한다.
    """
    df = _rows(n=600, seed=29)
    # 금액이 아주 작은 거래를 섞어 평균 편향을 음수로 끌어내린다.
    small = df.index[:40]
    df.loc[small, "price"] = df.loc[small, "price"] * 0.08
    diag = _diag(df, response_scale="loglog")
    assert diag.mean_bias_pct is not None
    assert diag.mean_bias_pct < diag.bias_pct, "평균이 중위보다 음수 쪽이어야 한다"
    assert diag.bias_note
    zone = _set(diag, "zone_type")
    assert zone is not None
    # 용도지역은 가격 생성과 무관하게 배정했으므로 유의 집단이 없어야 한다.
    flagged = [(g.label, g.excess_bias_pct, g.p_value) for g in zone.groups if g.significant]
    assert not flagged, f"전역 치우침을 집단 편향으로 오인했다: {flagged}"


def test_group_bias_excess_is_measured_against_the_rest():
    """초과 편향은 나머지 표본 기준 — 전체 치우침이 빠져 있어야 한다."""
    df = _rows(n=500, seed=31, zone_bump={"일반상업": 1.25})
    zone = _set(_diag(df, response_scale="linear"), "zone_type")
    bumped = next(g for g in zone.groups if g.label == "일반상업")
    others = [g for g in zone.groups if g.label != "일반상업"]
    assert bumped.excess_bias_pct > 0
    # 올린 집단은 과소평가(+), 나머지는 과대평가(−) 쪽으로 갈라진다.
    assert all(g.excess_bias_pct < bumped.excess_bias_pct for g in others)


def test_age_bins_keep_natural_order():
    """연식 구간은 편향 크기가 아니라 연식 순서로 나와야 읽을 수 있다."""
    diag = _diag(_rows(n=500, seed=19), response_scale="linear")
    ages = _set(diag, "building_age")
    assert ages is not None
    assert [g.label for g in ages.groups] == sorted(
        [g.label for g in ages.groups],
        key=lambda s: ["신축", "준신축", "10–19", "20–29", "30년+"].index(
            next(k for k in ["신축", "준신축", "10–19", "20–29", "30년+"] if s.startswith(k))
        ),
    )


def test_comparisons_do_not_carry_diagnostics():
    """상위 비교 모형에는 진단을 붙이지 않는다 — 화면이 없고 n이 크다."""
    res = _fit_ols(_rows(n=200), SPEC, "gu", "강남구", response_scale="linear")
    assert res.residuals is None


def test_tiny_sample_returns_no_diagnostics():
    """표본이 진단 최소 건수 미달이면 조용히 없음 — 빈 표를 그리게 하지 않는다."""
    res = _fit_ols(
        _rows(n=12, seed=23), SPEC, "sigungu", "강남구",
        with_residuals=True, response_scale="linear",
    )
    assert res.residuals is None or res.residuals.n >= MIN_GROUP_N
