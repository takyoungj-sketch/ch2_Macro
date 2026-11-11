"""복합 점검 1단계 (2026-11-11) — B-02 · B-12 · B-01 재현 조건 고정.

- B-02: 전남광주 시도 조회가 옛 시도명(광주광역시·전라남도) 2019~2020 행을 행정코드로 잇는다.
- B-12: 최종 표본에서 값이 모두 0인 더미·내포 중복 유형 더미를 빼고, 남은 식별 불가 계수는
  p값·유의 집계에서 제외한다.
- B-01: 선형 음수 추정은 값을 그대로 두고 성격만 표시한다.

DB 재현 테스트는 BUILT_DATABASE_URL 이 없으면 건너뛴다.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.built.regression.engine import (
    NONPOSITIVE_ESTIMATE_WARNING,
    _fit_ols,
    nonidentifiable_columns,
    nonpositive_estimate_flags,
    prune_design_columns,
)
from app.built.schemas import RegressionVariableSpec
from app.region_sido import addr1_scope_sql


# ── B-02 ─────────────────────────────────────────────────────────────────────


def test_addr1_scope_without_conn_is_plain_equality():
    params: dict = {}
    sql = addr1_scope_sql(None, params, addr1="전남광주통합특별시", table="built_transactions")
    assert sql == "addr1 = :addr1"
    assert params == {"addr1": "전남광주통합특별시"}


def test_addr1_scope_retired_name_unchanged():
    params: dict = {}
    sql = addr1_scope_sql(object(), params, addr1="광주광역시", table="built_transactions")  # type: ignore[arg-type]
    assert sql == "addr1 = :addr1"


# ── B-12 단위 ────────────────────────────────────────────────────────────────


def test_prune_drops_all_zero_dummy_and_nested_asset_type():
    X = pd.DataFrame(
        {
            "gross_area": [10.0, 20.0, 30.0, 40.0, 50.0, 60.0],
            "zone_미상": [0.0] * 6,
            "use_다가구": [0.0, 0.0, 0.0, 1.0, 0.0, 0.0],
            "use_단독": [0.0, 0.0, 0.0, 0.0, 1.0, 1.0],
            "use_판매": [0.0, 1.0, 0.0, 0.0, 0.0, 0.0],
            # 단독·다가구 ⇔ detached — 건축물용도에 내포
            "atype_detached": [0.0, 0.0, 0.0, 1.0, 1.0, 1.0],
        }
    )
    keep, dropped = prune_design_columns(X)
    reasons = {d.name: d.reason for d in dropped}
    assert reasons == {"zone_미상": "all_zero", "atype_detached": "nested_duplicate"}
    assert keep == ["gross_area", "use_다가구", "use_단독", "use_판매"]


def test_prune_keeps_asset_type_when_not_nested():
    X = pd.DataFrame(
        {
            "use_근린": [1.0, 1.0, 0.0, 0.0],
            # 같은 용도(근린) 안에서 유형이 둘 → 내포 아님
            "atype_detached": [0.0, 1.0, 0.0, 1.0],
        }
    )
    keep, dropped = prune_design_columns(X)
    assert dropped == []
    assert keep == ["use_근린", "atype_detached"]


def test_nonidentifiable_columns_flags_only_collinear_set():
    rng = np.random.default_rng(0)
    a = rng.normal(size=40)
    b = rng.normal(size=40)
    exog = np.column_stack([np.ones(40), a, b, a + b, rng.normal(size=40)])
    names = ["const", "a", "b", "a_plus_b", "c"]
    assert set(nonidentifiable_columns(exog, names)) == {"a", "b", "a_plus_b"}
    assert nonidentifiable_columns(exog[:, [0, 1, 2, 4]], ["const", "a", "b", "c"]) == []


def _synthetic_rows(n: int = 60, *, collinear: bool = False) -> pd.DataFrame:
    rng = np.random.default_rng(1)
    rows = []
    for i in range(n):
        gross = 50 + 3 * i + float(rng.normal(0, 4))
        land = (gross * 0.5 + 10) if collinear else 30 + 2 * i + float(rng.normal(0, 6))
        rows.append(
            {
                "price": 1000 + 20 * gross + 8 * land + float(rng.normal(0, 50)),
                "gross_area": gross,
                "land_area": land,
                "building_age": float(5 + i % 7),
                # '미상' 범주는 연면적 결측 행에만 → 최종 표본에서 전부 0이 된다
                "zone_type": "일반상업" if i % 2 else "준주거",
                "building_use": "근린",
                "road_width_label": "8m",
                "structure_group": "철콘",
                "asset_type": "commercial",
                "contract_year": 2021 + i % 4,
            }
        )
    rows.append({**rows[0], "gross_area": None, "zone_type": "미상"})
    return pd.DataFrame(rows)


_SPEC = RegressionVariableSpec(
    gross_area=True,
    land_area=True,
    building_age=True,
    road_width_dummy=False,
    zone_type_dummy=True,
    building_use_dummy=False,
    structure_dummy=False,
    asset_type_dummy=False,
)


def test_fit_drops_dummy_that_is_all_zero_after_missing_filter():
    fit = _fit_ols(_synthetic_rows(), _SPEC, "sigungu", "t", response_scale="linear")
    names = {c.name for c in fit.coefficients}
    assert "zone_미상" not in names
    assert [d.name for d in fit.dropped_design_columns] == ["zone_미상"]
    assert fit.identification_warning is None
    assert all(c.identifiable for c in fit.coefficients)
    assert fit.predict_options is not None
    assert "미상" not in fit.predict_options.zone_types


def test_fit_marks_nonidentifiable_and_excludes_from_significance():
    fit = _fit_ols(_synthetic_rows(collinear=True), _SPEC, "sigungu", "t", response_scale="linear")
    by_name = {c.name: c for c in fit.coefficients}
    for name in ("gross_area", "land_area"):
        assert by_name[name].identifiable is False
        assert by_name[name].p_value is None
        assert by_name[name].std_err is None
    assert fit.identification_warning and "한 값으로 정해지지 않습니다" in fit.identification_warning
    sig = sum(
        1 for c in fit.coefficients if c.name != "const" and c.p_value is not None and c.p_value < 0.05
    )
    assert fit.significant_count == sig


def test_cv_fold_drops_nested_asset_type():
    from app.built.regression.selection.fit import _estimable_columns

    x = pd.DataFrame(
        {
            "const": [1.0] * 6,
            "gross_area": [1.0, 2.0, 3.5, 4.0, 6.0, 7.5],
            "use_단독": [0.0, 0.0, 1.0, 1.0, 0.0, 1.0],
            "atype_detached": [0.0, 0.0, 1.0, 1.0, 0.0, 1.0],
            "zone_x": [0.0] * 6,
        }
    )
    assert _estimable_columns(x) == ["const", "gross_area", "use_단독"]


# ── B-01 단위 ────────────────────────────────────────────────────────────────


def test_nonpositive_flags_keep_value():
    nonpos, neg_lower, notes = nonpositive_estimate_flags(-56250.0, ci_lower=-114140.0, pi_lower=-2.0)
    assert nonpos is True and neg_lower is False
    assert notes == [NONPOSITIVE_ESTIMATE_WARNING]
    nonpos, neg_lower, notes = nonpositive_estimate_flags(500.0, ci_lower=-10.0, pi_lower=-200.0)
    assert nonpos is False and neg_lower is True and len(notes) == 1
    assert nonpositive_estimate_flags(500.0, ci_lower=100.0, pi_lower=50.0) == (False, False, [])


def test_prediction_narrative_does_not_call_negative_value_an_estimate():
    from app.ai.prediction_narrative import build_prediction_narrative

    out = build_prediction_narrative(
        diagnostics={"y_hat": -56250.0, "pi_lower": -257000.0, "pi_upper": 144000.0,
                     "ci_lower": -114140.0, "ci_upper": 1639.0, "n": 1217},
        scope_label="청주시",
    )
    assert "가격관계가 관찰됩니다" not in out.answer
    assert "실제 거래금액을 의미하지 않습니다" in out.answer


def test_dialogue_prediction_evidence_notes_negative_estimate():
    from app.ai.dialogue import ScreenEvidence, _prediction

    ev = ScreenEvidence(context={})
    _prediction(ev, {"y_hat": -56250.0, "ci_lower": -114140.0, "ci_upper": 1639.0, "n": 1217}, "만원")
    assert any("추정금액·가격으로 단정해 말하지 말고" in note for note in ev.notes)


# ── DB 재현 조건 ─────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def built_conn():
    from app.built.db import get_built_engine

    eng = get_built_engine()
    if eng is None:
        pytest.skip("BUILT_DATABASE_URL not configured")
    from app.collective.meta_cache import clear_meta_cache

    clear_meta_cache()
    with eng.connect() as conn:
        yield conn


def _as_of(conn) -> str:
    from sqlalchemy import text

    return str(conn.execute(text("SELECT to_char(max(contract_date), 'YYYY-MM') FROM built_transactions")).scalar())


def _year_counts(conn, **kw) -> dict[int, int]:
    from sqlalchemy import text

    from app.built.transaction_scope import build_transaction_where

    where, params = build_transaction_where(conn=conn, **kw)
    rows = conn.execute(
        text(f"SELECT contract_year, count(*) FROM built_transactions WHERE {where} GROUP BY 1"), params
    ).fetchall()
    return {int(r[0]): int(r[1]) for r in rows if r[0] is not None}


@pytest.mark.parametrize("asset_type", ["commercial", "factory"])
def test_b02_unified_sido_includes_legacy_named_rows(built_conn, asset_type):
    merged = _year_counts(built_conn, asset_type=asset_type, addr1="전남광주통합특별시")
    gwangju = _year_counts(built_conn, asset_type=asset_type, addr1="광주광역시")
    jeonnam = _year_counts(built_conn, asset_type=asset_type, addr1="전라남도")
    if not gwangju and not jeonnam:
        pytest.skip("레거시 시도명 행 없음")
    for year in (2019, 2020):
        legacy = gwangju.get(year, 0) + jeonnam.get(year, 0)
        assert legacy > 0
        assert merged.get(year, 0) >= legacy
    # 옛 이름 단독 조회는 기존과 동일 — 레거시 행만
    assert set(gwangju) <= {2019, 2020}


def test_b02_seven_year_regression_fit_years_include_2019(built_conn):
    from app.built.regression.engine import run_regression
    from app.built.schemas import RegressionRunRequest

    res = run_regression(
        built_conn,
        RegressionRunRequest(
            asset_type="commercial", addr1="전남광주통합특별시",
            as_of_month=_as_of(built_conn), window_years=7,
        ),
    )
    years = res.primary.analysis.fit_years
    first_window_year = int(_as_of(built_conn)[:4]) - 7
    expected = [y for y in (2019, 2020) if y >= first_window_year]
    assert expected and all(y in years for y in expected), years


def test_b12_sejong_jochiwon_no_degenerate_coefficients(built_conn):
    from app.built.regression.engine import run_regression
    from app.built.schemas import RegressionRunRequest

    spec = RegressionVariableSpec(
        gross_area=True, land_area=True, building_age=True, road_width_dummy=True,
        zone_type_dummy=True, building_use_dummy=True, structure_dummy=True,
        assessed_land_price=True, asset_type_dummy=True,
    )
    res = run_regression(
        built_conn,
        RegressionRunRequest(
            asset_type="commercial,detached", addr1="세종특별자치시", addr2="__FLAT_SIDO__",
            addr3_list=["조치원읍"], as_of_month=_as_of(built_conn), window_years=5,
            variables=spec, response_scale="linear", exclude_outliers_iqr=True,
            outlier_iqr_multiplier=3.0, enrich=True,
        ),
    )
    p = res.primary
    if p.n < 30:
        pytest.skip(f"표본 부족 n={p.n}")
    # 1e-11 같은 축퇴 계수가 p값을 달고 나오지 않는다
    for c in p.coefficients:
        if c.p_value is not None:
            assert abs(c.estimate) > 1e-6, c
    reasons = {d.reason for d in p.dropped_design_columns}
    assert "all_zero" in reasons
    assert "nested_duplicate" in reasons
    assert not any(c.name == "atype_detached" for c in p.coefficients)
    # 남은 rank 부족이 있으면 화면 경고가 있어야 한다
    if any(not c.identifiable for c in p.coefficients):
        assert p.identification_warning


def test_b01_cheongju_negative_estimate_kept_with_warning(built_conn):
    from app.built.regression.engine import predict_regression
    from app.built.schemas import RegressionPredictRequest

    r = predict_regression(
        built_conn,
        RegressionPredictRequest(
            asset_type="commercial", addr1="충청북도", addr2="청주시",
            as_of_month=_as_of(built_conn), window_years=5, admin_level="sigungu",
            gross_area=100, land_area=200, building_age=20, zone_type="농림",
        ),
    )
    assert r.y_hat < 0, "재현 조건: 선형 기본식 외삽이 음수여야 한다"
    assert r.nonpositive_estimate is True
    assert r.ci_lower < r.y_hat < r.ci_upper  # 값은 숨기거나 0으로 바꾸지 않는다
    assert NONPOSITIVE_ESTIMATE_WARNING in r.warnings
