"""복합 점검 3단계 (2026-11-11) — F-1 · B-05 · B-09 재현 조건 고정.

- F-1: 대장 정보 동의(enrich) 시에만 회귀 연식을 실거래 건축연도 → 대장 사용승인연도 순으로 보강.
- B-05: 분석 표본 「직거래 제외」(기본 OFF). 거래유형 빈 값은 직거래로 보지 않는다.
- B-09: 서버 meta 기본 롤링 기간 5년.
RS-1(7년 안내)은 화면 문구만이라 프론트 타입체크로 확인한다.

DB 재현 테스트는 BUILT_DATABASE_URL 이 없으면 건너뛴다.
"""

from __future__ import annotations

import pandas as pd
import pytest

from app.built.filters import apply_direct_trade_filter
from app.built.regression.age_backfill import (
    LEDGER_AGE_FLAG,
    apply_age_range,
    backfill_age_from_ledger,
    ledger_backfill_count,
)


# ── F-1 단위 ─────────────────────────────────────────────────────────────────


def test_backfill_only_missing_age_and_keeps_transaction_age():
    df = pd.DataFrame(
        {
            "building_age": [10.0, None, None, None],
            "approve_year": [1990, 2000, None, 1800],
            "contract_year": [2024, 2024, 2024, 2024],
        }
    )
    out = backfill_age_from_ledger(df)
    assert out["building_age"].tolist()[:2] == [10.0, 24.0]  # 실거래 연식 우선, 결측만 보강
    assert pd.isna(out["building_age"].iloc[2]) and pd.isna(out["building_age"].iloc[3])
    assert out[LEDGER_AGE_FLAG].tolist() == [False, True, False, False]
    assert df["building_age"].isna().sum() == 3  # 입력(원장 조회 결과)은 건드리지 않는다
    assert ledger_backfill_count(out, out.index) == 1


def test_backfill_noop_without_ledger_column():
    df = pd.DataFrame({"building_age": [None], "contract_year": [2024]})
    assert backfill_age_from_ledger(df) is df


def test_age_range_uses_backfilled_value():
    df = backfill_age_from_ledger(
        pd.DataFrame({"building_age": [None, 3.0], "approve_year": [2000, None], "contract_year": [2024, 2024]})
    )
    assert apply_age_range(df, 20, None).index.tolist() == [0]


# ── B-05 단위 ────────────────────────────────────────────────────────────────


def test_direct_trade_filter_clause():
    clauses: list[str] = []
    apply_direct_trade_filter(clauses, exclude=False)
    assert clauses == []
    apply_direct_trade_filter(clauses, exclude=True, col_prefix="t")
    assert clauses == ["COALESCE(btrim(t.deal_type::text), '') <> '직거래'"]  # 빈 값은 남는다


def test_meta_default_window_is_five():
    from app.built.schemas import BuiltFilterMetaResponse

    assert BuiltFilterMetaResponse.model_fields["default_window_years"].default == 5


# ── DB 재현 조건 ─────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def built_conn():
    from app.built.db import get_built_engine

    eng = get_built_engine()
    if eng is None:
        pytest.skip("BUILT_DATABASE_URL not configured")
    with eng.connect() as conn:
        yield conn


def _as_of(conn) -> str:
    from sqlalchemy import text

    return str(conn.execute(text("SELECT to_char(max(contract_date), 'YYYY-MM') FROM built_transactions")).scalar())


def test_f1_cheongju_factory_ledger_age(built_conn):
    from app.built.regression.engine import run_regression
    from app.built.schemas import RegressionRunRequest

    base = dict(asset_type="factory", addr1="충청북도", addr2="청주시", as_of_month=_as_of(built_conn), window_years=5)
    off = run_regression(built_conn, RegressionRunRequest(**base)).primary
    on = run_regression(built_conn, RegressionRunRequest(**base, enrich=True)).primary
    assert not any(s.code == "ledger_age" for s in off.sample.funnel)  # 동의 안 하면 기존과 동일
    step = next((s for s in on.sample.funnel if s.code == "ledger_age"), None)
    if step is None:
        pytest.skip("대장 사용승인연도로 보강할 거래 없음")
    assert step.kind == "info" and step.n > 0
    assert on.n == off.n + step.n
    assert on.sample.n_pool == off.sample.n_pool


def test_b05_cheongju_commercial_direct_excluded(built_conn):
    from app.built.regression.engine import run_regression
    from app.built.schemas import RegressionRunRequest

    base = dict(asset_type="commercial", addr1="충청북도", addr2="청주시", as_of_month=_as_of(built_conn), window_years=5)
    keep = run_regression(built_conn, RegressionRunRequest(**base))
    drop = run_regression(built_conn, RegressionRunRequest(**base, exclude_direct_trades=True))
    excluded = drop.analysis_scope.direct_tx_excluded
    if excluded == 0:
        pytest.skip("직거래 없음")
    assert keep.analysis_scope.direct_tx_excluded == 0
    assert drop.primary.sample.n_pool == keep.primary.sample.n_pool - excluded
