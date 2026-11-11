"""복합 점검 2단계 (2026-11-11) — R-1 · T-1 · T-2 · T-3 · T-4 재현 조건 고정.

- R-1: 전체 탐색 CV가 없으면 같은 evaluation_signature 부분 CV로 1위, 그것도 없으면 대표 추천 보류.
- T-1: Twin 판정에 「계산 불가」를 두고 「동등」과 구분한다.
- T-2: Local·Twin CV를 같은 내 지역 검증거래로 채점한다 (학습은 각자, 연도 < t).
- T-3: 제품 Twin2(일반 사용자 노출)는 Twin1처럼 지역 더미를 붙인다.
- T-4: Twin 실행 뒤 종료 사유 문구가 실행 상태를 따른다.

DB 재현 테스트는 BUILT_DATABASE_URL 이 없으면 건너뛴다.
"""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from app.built.regression.selection.best_subset import CompareResult, _rank_partial_cv
from app.built.regression.selection.fit import CvPhase
from app.recommendation.ranks import pick_primary_predictive, predictive_ranking_basis
from app.recommendation.twin_structure import classify_search_delta, decide_twin_prefix
from app.recommendation.twin_validation import build_twin_validation_verdict


def _fit(mape, *, sig="s1", complete=False, n_trades=40, years=(2023, 2024, 2025)):
    held = years if complete else (2022, *years)
    failures = () if complete else ((2022, "학습 표본 또는 평가 거래 부족"),)
    phase = CvPhase(
        mape=mape, folds=len(years), n_trades=n_trades, years=years, held_years=held,
        evaluation_signature=sig, failure_reasons=failures,
    )
    return SimpleNamespace(cv_search=phase, cv_mape=mape, mape=mape)


# ── R-1 ──────────────────────────────────────────────────────────────────────


def test_partial_cv_ranks_within_shared_signature():
    scored = [(["a"], _fit(42.01), None), (["b"], _fit(36.22), None), (["c"], _fit(10.0, sig="other"), None)]
    ranked, years = _rank_partial_cv(scored)
    assert [c.blocks for c in ranked] == [["b"], ["a"]]  # 서명이 다른 10% 후보는 섞지 않는다
    assert years == (2023, 2024, 2025)


def test_ranking_basis_full_partial_withheld():
    cand = lambda b, f: SimpleNamespace(rank=1, blocks=b, fit=f)  # noqa: E731
    full = CompareResult(by_aic=[], by_bic=[], by_mape=[], by_cv_mape=[cand(["a"], _fit(30, complete=True))],
                         total_subsets=1, truncated=False)
    assert predictive_ranking_basis(full)[0] == "full_cv"

    partial = CompareResult(by_aic=[], by_bic=[], by_mape=[cand(["m"], _fit(None))], by_cv_mape=[],
                            total_subsets=1, truncated=False,
                            by_partial_cv=[cand(["p"], _fit(36.22))], partial_cv_years=(2023, 2024, 2025))
    basis, rows, label, years = predictive_ranking_basis(partial)
    assert basis == "partial_cv" and rows[0].blocks == ["p"]
    assert label == "부분 CV(2023~2025) 기준"
    assert pick_primary_predictive(partial.by_cv_mape, partial.by_mape, partial.by_aic, partial.by_partial_cv).blocks == ["p"]

    withheld = CompareResult(by_aic=[], by_bic=[], by_mape=[cand(["m"], _fit(None))], by_cv_mape=[],
                             total_subsets=1, truncated=False)
    assert predictive_ranking_basis(withheld)[0] == "withheld"


# ── T-1 ──────────────────────────────────────────────────────────────────────


def test_missing_cv_is_unavailable_not_tie():
    assert classify_search_delta(None, 0.5) == "unavailable"
    decision = decide_twin_prefix(
        local_n=72, local_search_cv=None, local_confirm_cv=33.49, local_coeffs={},
        local_blocks=["gross_area"],
        prefixes=[{"candidate_id": "twin_selected", "label": "Local + 1곳", "prefix_k": 1, "n": 102,
                   "search_cv_mape": None, "confirm_cv_mape": 29.17, "blocks": ["gross_area", "region_leaf"]}],
    )
    assert decision.search_band == "unavailable"
    assert "동등하다는 뜻이 아닙니다" in decision.decision_reason
    assert "계산 불가" in decision.steps[1].verdict_ko
    verdict = build_twin_validation_verdict(
        ran=True, skipped_reason=None, local_cv_mape=None, decision="local",
        primary=None, pools=[], prefix=decision,
    )
    assert verdict.verdict == "unavailable" and verdict.label_ko == "계산 불가"
    assert decision.region_effect and "더미 포함" in decision.region_effect


def test_pool_path_without_cv_is_unavailable():
    verdict = build_twin_validation_verdict(
        ran=True, skipped_reason=None, local_cv_mape=None, decision="local", primary=None, pools=[],
    )
    assert verdict.verdict == "unavailable"


# ── T-2 ──────────────────────────────────────────────────────────────────────


def test_paired_rows_compare_only_same_trade_count():
    row = {"candidate_id": "t", "label": "t", "prefix_k": 1, "n": 120, "blocks": ["gross_area"],
           "scored_on": "anchor_common", "search_cv_mape": 20.0, "search_eval_n": 40,
           "local_search_cv_mape": 30.0, "local_search_eval_n": 38}
    d = decide_twin_prefix(local_n=80, local_search_cv=30.0, local_confirm_cv=None, local_coeffs={},
                           local_blocks=["gross_area"], prefixes=[row])
    assert d.steps[1].search_cv_delta is None  # 평가 거래 수가 다르면 비교하지 않는다
    row["local_search_eval_n"] = 40
    d = decide_twin_prefix(local_n=80, local_search_cv=30.0, local_confirm_cv=None, local_coeffs={},
                           local_blocks=["gross_area"], prefixes=[row])
    assert d.steps[1].search_cv_delta == 10.0
    assert d.steps[0].search_eval_n == 40


def test_score_mask_limits_scoring_not_training():
    from app.built.regression.selection.fit import _rolling_time_cv_mape
    from app.built.schemas import RegressionVariableSpec

    rng = np.random.default_rng(3)
    rows = []
    for i in range(160):
        gross = 50 + float(rng.uniform(0, 200))
        rows.append({"transaction_id": i, "price": 300 + 9 * gross + float(rng.normal(0, 40)),
                     "gross_area": gross, "contract_year": 2021 + i % 4, "anchor": i % 2 == 0})
    df = pd.DataFrame(rows)
    spec = RegressionVariableSpec(gross_area=True, land_area=False, building_age=False, road_width_dummy=False,
                                  zone_type_dummy=False, building_use_dummy=False, structure_dummy=False,
                                  asset_type_dummy=False)
    full, _ = _rolling_time_cv_mape(df, spec, unified=False, response_scale="linear", region_col=None)
    masked, _ = _rolling_time_cv_mape(df, spec, unified=False, response_scale="linear", region_col=None,
                                      score_mask=df["anchor"])
    assert masked.n_trades == int((df["anchor"] & (df["contract_year"] > 2021)).sum())
    assert masked.n_trades < full.n_trades


# ── T-4 ──────────────────────────────────────────────────────────────────────


def test_termination_states_follow_execution():
    from app.recommendation.termination import build_termination_r2

    grade = SimpleNamespace(proceed_twin=True, label_ko="보통", grade="fair", note=None)
    primary = SimpleNamespace(metrics=SimpleNamespace(cv_mape=30.0), blocks=["a"])
    t = build_termination_r2(grade=grade, selection_n=50, scope_n_tx=60, primary=primary, alternate=None,
                             truncated=False, stage2=None, has_twins=True)
    assert "Twin 후보는 있으나 Twin1을 아직 실행하지 않았습니다." in t.reasons
    assert not any("미전달 또는" in r for r in t.reasons)


# ── DB 재현 조건 ─────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def built_conn():
    from app.built.db import get_built_engine

    eng = get_built_engine()
    if eng is None:
        pytest.skip("BUILT_DATABASE_URL not configured")
    with eng.connect() as conn:
        yield conn


def _base_req(conn, **extra):
    from sqlalchemy import text

    from app.built.schemas import RegressionSelectionRequest

    am = str(conn.execute(text("SELECT to_char(max(contract_date), 'YYYY-MM') FROM built_transactions")).scalar())
    codes = dict(conn.execute(text(
        "SELECT addr4, max(eupmyeondong_code) FROM built_transactions "
        "WHERE addr1='충청북도' AND addr2='청주시' AND addr4 IN ('가경동','복대동') GROUP BY 1"
    )).fetchall())
    if len(codes) < 2:
        pytest.skip("청주 가경동·복대동 원장 없음")
    return codes, RegressionSelectionRequest(
        asset_type="commercial", addr1="충청북도", addr2="청주시", addr3_list=["흥덕구"],
        addr4_list=["복대동"], region_codes=[codes["복대동"]], region_code_level="eupmyeondong",
        as_of_month=am, window_years=5, **extra,
    )


def test_r1_bokdae_partial_cv_primary(built_conn):
    from app.recommendation.stages import run_recommendation

    _codes, req = _base_req(built_conn)
    s1 = run_recommendation(built_conn, req).stage1
    if s1.ranking_basis == "full_cv":
        pytest.skip("데이터가 바뀌어 전체 탐색 CV가 계산됨")
    assert s1.ranking_basis == "partial_cv"
    assert s1.ranking_basis_label.startswith("부분 CV(")
    cvs = [c.metrics.cv_mape for c in s1.candidates_predictive if c.metrics.cv_mape is not None]
    assert s1.primary.metrics.cv_mape == min(cvs)
    sigs = {c.cv_report.search.evaluation_signature for c in s1.candidates_predictive}
    assert len(sigs) == 1


def test_t1_t2_t3_bokdae_gagyeong_twin(built_conn):
    from app.recommendation.stages import run_recommendation

    codes, req = _base_req(built_conn)
    req = req.model_copy(update=dict(
        run_stage2=True, run_stage2_research=True,
        profile_twin_neighbors=[{"region_code": codes["가경동"], "similarity_score": 0.9, "rank": 1}],
        selected_twin_codes=[codes["가경동"]], profile_version="v2.1-national",
        profile_as_of_month=req.as_of_month, profile_window_years=3,
    ))
    s2 = run_recommendation(built_conn, req).stage2
    assert s2 is not None and s2.ran
    twin = next(s for s in s2.twin_experiments if s.step_id != "local")
    # T-1: 탐색 CV가 둘 다 없으면 동등이 아니라 계산 불가
    if twin.search_cv_mape is None or twin.local_search_cv_mape is None:
        assert s2.twin_validation.verdict == "unavailable"
        assert "동등(" not in twin.verdict_ko
    # T-2: 확인 CV는 같은 내 지역 거래 수로 채점
    assert twin.confirm_eval_n is not None
    assert twin.confirm_eval_n == twin.local_confirm_eval_n
    # T-3: Twin2도 지역 더미
    assert s2.research is not None
    assert "region_leaf" in s2.research.blocks or s2.research.region_dummy_note
