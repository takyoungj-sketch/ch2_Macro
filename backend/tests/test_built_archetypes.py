"""Pareto archetype picks — 설명형 · 균형형 · 예측형."""

from __future__ import annotations

import numpy as np
import pandas as pd

from app.built.regression.selection.archetypes import ARCHETYPE_LABELS, pick_archetypes
from app.built.regression.selection.blocks import BlockId
from app.built.regression.selection.context import SelectionContext, with_complete_case
from app.built.regression.selection.fit import BlockFitResult, fit_best_scale
from app.built.regression.selection.pooling import (
    _decision_confidence,
    accepted_twin_region_codes,
    evaluate_pooling_candidates,
)
from app.built.regression.selection.service import _warnings_for_cv_mape
from app.built.schemas import RegressionSelectionRequest


def _make_df(n: int = 40) -> pd.DataFrame:
    rows = []
    for i in range(n):
        gross = 50 + i * 2
        land = 30 + i
        age = 5 + (i % 6)
        zone = ["Z1", "Z2", "Z3"][i % 3]
        price = 3000 + gross * 8 + land * 4 - age * 20 + (500 if zone == "Z2" else 0)
        rows.append(
            {
                "price": price,
                "gross_area": gross,
                "land_area": land,
                "building_age": age,
                "road_width_label": "8m" if i % 2 == 0 else "12m",
                "zone_type": zone,
                "building_use": "근린",
                "asset_type": "commercial",
            }
        )
    return pd.DataFrame(rows)


def _score_all(df: pd.DataFrame, block_lists: list[list[BlockId]]):
    scored = []
    for blocks in block_lists:
        fit, cmp = fit_best_scale(
            df, blocks, unified=False, region_col=None, admin_level="sigungu"
        )
        if fit is not None:
            scored.append((blocks, fit, cmp))
    return scored


def test_pick_archetypes_returns_three_kinds():
    df = _make_df()
    blocks = [
        ["gross_area"],
        ["gross_area", "land_area"],
        ["gross_area", "building_age"],
        ["gross_area", "land_area", "building_age"],
        ["gross_area", "land_area", "building_age", "road_width"],
        ["gross_area", "land_area", "building_age", "zone_type"],
    ]
    scored = _score_all(df, blocks)
    baseline, _ = fit_best_scale(
        df,
        ["gross_area", "land_area", "building_age", "road_width", "zone_type"],
        unified=False,
        region_col=None,
        admin_level="sigungu",
    )
    picks = pick_archetypes(scored, baseline)
    assert len(picks) >= 2
    kinds = {p.kind for p in picks}
    assert "explanation" in kinds or "prediction" in kinds
    for p in picks:
        assert p.kind in ARCHETYPE_LABELS
        assert p.confidence_label in ("높음", "보통", "낮음")
        assert p.reasons


def test_archetype_explanation_has_highest_adj():
    df = _make_df()
    blocks = [
        ["gross_area"],
        ["gross_area", "zone_type"],
        ["gross_area", "land_area", "zone_type"],
    ]
    scored = _score_all(df, blocks)
    picks = pick_archetypes(scored, None)
    expl = next(p for p in picks if p.kind == "explanation")
    pool_adj = [f.adj_r_squared for _, f, _ in scored if f.adj_r_squared is not None]
    assert expl.fit.adj_r_squared == max(pool_adj)


def test_complete_case_is_shared_across_candidate_union():
    df = _make_df(8)
    df.loc[2, "building_age"] = None
    df.loc[5, "zone_type"] = None
    ctx = SelectionContext(
        df=df,
        scope_label="test",
        admin_level="sigungu",
        addr4_city=False,
        mode="two_way",
        unified=False,
    )
    sampled = with_complete_case(
        ctx,
        ["gross_area", "building_age", "zone_type"],
        region_col=None,
    )
    assert sampled.selection_n == 6
    assert sampled.df.index.tolist() == [0, 1, 3, 4, 6, 7]
    assert sampled.sample_columns == (
        "price",
        "gross_area",
        "building_age",
        "zone_type",
    )


def test_joint_f_test_is_reported_for_included_block():
    fit, _ = fit_best_scale(
        _make_df(),
        ["gross_area", "zone_type"],
        unified=False,
        region_col=None,
        admin_level="sigungu",
    )
    assert fit is not None
    assert fit.joint_f_tests["gross_area"].tested is True
    assert fit.joint_f_tests["zone_type"].tested is True


def test_high_cv_mape_warns_about_prediction_use():
    assert _warnings_for_cv_mape(71.73)
    assert "설명용" in _warnings_for_cv_mape(71.73)[0]
    assert _warnings_for_cv_mape(29.3) == []


def _timed_rows(n: int, *, start_year: int, years: int, seed: int, noise_std: float) -> list[dict]:
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(n):
        gross = 50 + (i % 20) * 2
        land = 30 + (i % 20)
        age = 5 + (i % 6)
        zone = ["Z1", "Z2", "Z3"][i % 3]
        base_price = 3000 + gross * 8 + land * 4 - age * 20 + (500 if zone == "Z2" else 0)
        rows.append(
            {
                "price": base_price + rng.normal(0, noise_std),
                "gross_area": gross,
                "land_area": land,
                "building_age": age,
                "road_width_label": "8m" if i % 2 == 0 else "12m",
                "zone_type": zone,
                "building_use": "근린",
                "asset_type": "commercial",
                "contract_year": start_year + (i % years),
            }
        )
    return rows


class _FakePoolResult:
    def __init__(self, rows: list[dict]):
        self._rows = rows

    def mappings(self):
        return self

    def all(self):
        return self._rows


class _FakePoolConn:
    """conn.execute를 흉내낸다 — SQL 텍스트로 가격수준 조회와 원행 조회를 구분한다."""

    def __init__(self, rows: list[dict], price_levels: dict[str, float] | None = None):
        self._rows = rows
        self._price_levels = price_levels or {}

    def execute(self, stmt, _params=None):
        if "median_psqm" in str(stmt):
            price_rows = [
                {"code": code, "median_psqm": value, "n": 999}
                for code, value in self._price_levels.items()
            ]
            return _FakePoolResult(price_rows)
        return _FakePoolResult(self._rows)


def _median_psqm(rows: list[dict]) -> float:
    values = sorted(r["price"] / r["gross_area"] for r in rows)
    mid = len(values) // 2
    if len(values) % 2:
        return values[mid]
    return (values[mid - 1] + values[mid]) / 2


_POOL_BLOCKS: list[BlockId] = ["gross_area", "land_area", "building_age", "zone_type"]


def _local_ctx_and_fit(rows: list[dict]):
    ctx = SelectionContext(
        df=pd.DataFrame(rows),
        scope_label="local",
        admin_level="eupmyeondong",
        addr4_city=False,
        mode="single",
        unified=False,
    )
    ctx = with_complete_case(ctx, _POOL_BLOCKS, region_col=None)
    fit, _ = fit_best_scale(
        ctx.df, _POOL_BLOCKS, unified=False, region_col=None, admin_level="eupmyeondong"
    )
    return ctx, fit


def test_decision_confidence_grades_by_relative_gap():
    wide = _decision_confidence(60.0, 40.0)
    assert wide.grade == "A"
    assert wide.stars == 5
    tight = _decision_confidence(50.0, 50.0)
    assert tight.grade == "E"
    assert tight.stars == 1


def test_accepted_twin_region_codes_excludes_anchor_and_other_providers():
    from app.built.regression.candidates import CandidateSpec

    specs = (
        CandidateSpec(candidate_id="local", provider_id="local", region_codes=("A1",), variables=()),
        CandidateSpec(
            candidate_id="profile-twin-1",
            provider_id="profile_twin",
            region_codes=("A1", "T1"),
            variables=(),
        ),
        CandidateSpec(
            candidate_id="profile-twin-2",
            provider_id="profile_twin",
            region_codes=("A1", "T1", "T2"),
            variables=(),
        ),
    )
    assert accepted_twin_region_codes(specs, ("A1",)) == ("T1", "T2")


def test_evaluate_pooling_candidates_without_twin_codes_keeps_local():
    local_rows = _timed_rows(15, start_year=2018, years=3, seed=1, noise_std=800)
    local_ctx, local_fit = _local_ctx_and_fit(local_rows)
    assert local_fit is not None
    result = evaluate_pooling_candidates(
        _FakePoolConn([]),
        local_ctx=local_ctx,
        req=RegressionSelectionRequest(),
        blocks=_POOL_BLOCKS,
        local_fit=local_fit,
        anchor_region_codes=("11110250",),
        twin_region_codes=(),
        admin_level="eupmyeondong",
        region_col=None,
    )
    assert result.decision == "local"
    assert len(result.candidates) == 1
    assert "없어" in result.decision_reason


def test_evaluate_pooling_candidates_prefers_lower_cv_mape_pool():
    # local: 표본이 작고 잡음이 커서 CV-MAPE가 나쁘다.
    local_rows = _timed_rows(15, start_year=2018, years=3, seed=1, noise_std=1200)
    # twin: 동일한 관계식이지만 잡음이 훨씬 작다 — pool하면 표본이 커지고 CV-MAPE가 개선돼야 한다.
    twin_rows = _timed_rows(80, start_year=2018, years=3, seed=2, noise_std=50)

    local_ctx, local_fit = _local_ctx_and_fit(local_rows)
    assert local_fit is not None

    anchor_code = "11110250"
    twin_code = "11110251"  # 같은 시도(11) — 인접성 gate 통과
    price_levels = {anchor_code: _median_psqm(local_rows), twin_code: _median_psqm(twin_rows)}

    result = evaluate_pooling_candidates(
        _FakePoolConn(local_rows + twin_rows, price_levels=price_levels),
        local_ctx=local_ctx,
        req=RegressionSelectionRequest(
            profile_twin_neighbors=[{"region_code": twin_code, "similarity_score": 0.9}]
        ),
        blocks=_POOL_BLOCKS,
        local_fit=local_fit,
        anchor_region_codes=(anchor_code,),
        twin_region_codes=(twin_code,),
        admin_level="eupmyeondong",
        region_col=None,
    )
    assert result.decision.startswith("twin_pool")
    assert len(result.candidates) == 2
    pool_metrics = next(c for c in result.candidates if c.candidate_id != "local")
    local_metrics = next(c for c in result.candidates if c.candidate_id == "local")
    assert pool_metrics.cv_mape is not None and local_metrics.cv_mape is not None
    assert pool_metrics.cv_mape < local_metrics.cv_mape
    assert result.decision_confidence is not None
    assert 1 <= result.decision_confidence.stars <= 5
    assert result.twin_gates and result.twin_gates[0].accepted is True


def test_evaluate_pooling_candidates_rejects_twin_failing_price_gate():
    local_rows = _timed_rows(15, start_year=2018, years=3, seed=1, noise_std=800)
    local_ctx, local_fit = _local_ctx_and_fit(local_rows)
    assert local_fit is not None

    anchor_code = "11110250"
    twin_code = "11110251"
    # twin 가격수준이 anchor의 5배 — hard gate(0.5~2.0) 실패.
    price_levels = {anchor_code: 100.0, twin_code: 500.0}

    result = evaluate_pooling_candidates(
        _FakePoolConn([], price_levels=price_levels),
        local_ctx=local_ctx,
        req=RegressionSelectionRequest(
            profile_twin_neighbors=[{"region_code": twin_code, "similarity_score": 0.9}]
        ),
        blocks=_POOL_BLOCKS,
        local_fit=local_fit,
        anchor_region_codes=(anchor_code,),
        twin_region_codes=(twin_code,),
        admin_level="eupmyeondong",
        region_col=None,
    )
    assert result.decision == "local"
    assert len(result.candidates) == 1
    assert result.twin_gates and result.twin_gates[0].accepted is False
    assert result.twin_gates[0].price_gate is False
    assert result.twin_gates[0].adjacency_gate is True


def test_evaluate_pooling_candidates_rejects_twin_failing_adjacency_gate():
    local_rows = _timed_rows(15, start_year=2018, years=3, seed=1, noise_std=800)
    local_ctx, local_fit = _local_ctx_and_fit(local_rows)
    assert local_fit is not None

    anchor_code = "11110250"  # 서울
    twin_code = "50110250"  # 제주 — 서울과 인접 시도가 아님

    result = evaluate_pooling_candidates(
        _FakePoolConn([]),
        local_ctx=local_ctx,
        req=RegressionSelectionRequest(
            profile_twin_neighbors=[{"region_code": twin_code, "similarity_score": 0.9}]
        ),
        blocks=_POOL_BLOCKS,
        local_fit=local_fit,
        anchor_region_codes=(anchor_code,),
        twin_region_codes=(twin_code,),
        admin_level="eupmyeondong",
        region_col=None,
    )
    assert result.decision == "local"
    assert result.twin_gates and result.twin_gates[0].adjacency_gate is False
    assert result.twin_gates[0].accepted is False


def test_evaluate_pooling_candidates_builds_multiple_pool_variants():
    local_rows = _timed_rows(15, start_year=2018, years=3, seed=1, noise_std=1200)
    anchor_code = "11110250"
    twin_codes = [f"1111025{i}" for i in range(1, 6)]  # 5개, 같은 시도(11)
    twin_rows_by_code = {
        code: _timed_rows(30, start_year=2018, years=3, seed=10 + i, noise_std=50)
        for i, code in enumerate(twin_codes)
    }
    all_twin_rows = [row for rows in twin_rows_by_code.values() for row in rows]

    local_ctx, local_fit = _local_ctx_and_fit(local_rows)
    assert local_fit is not None

    price_levels = {anchor_code: _median_psqm(local_rows)}
    for code, rows in twin_rows_by_code.items():
        price_levels[code] = _median_psqm(rows)

    result = evaluate_pooling_candidates(
        _FakePoolConn(local_rows + all_twin_rows, price_levels=price_levels),
        local_ctx=local_ctx,
        req=RegressionSelectionRequest(
            profile_twin_neighbors=[
                {"region_code": code, "similarity_score": 0.9 - i * 0.05}
                for i, code in enumerate(twin_codes)
            ]
        ),
        blocks=_POOL_BLOCKS,
        local_fit=local_fit,
        anchor_region_codes=(anchor_code,),
        twin_region_codes=tuple(twin_codes),
        admin_level="eupmyeondong",
        region_col=None,
    )
    variant_ids = {c.candidate_id for c in result.candidates}
    assert "twin_pool_n1" in variant_ids
    assert "twin_pool_n3" in variant_ids
    assert "twin_pool_n5" in variant_ids
    assert len(result.twin_gates) == 5
    assert all(g.accepted for g in result.twin_gates)
