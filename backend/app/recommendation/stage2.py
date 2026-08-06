"""R2 — stage2 Twin pool (식 고정)."""

from __future__ import annotations

from dataclasses import dataclass

from app.built.regression.selection.blocks import BlockId, spec_from_blocks
from app.built.regression.selection.context import SelectionContext
from app.built.regression.selection.pooling import evaluate_pooling_candidates
from app.built.regression.selection.best_subset import CompareCandidate
from app.built.schemas import (
    PoolingCandidateMetrics,
    RecommendationPoolCandidate,
    RecommendationStage2,
    RegressionSelectionRequest,
    ResponseScale,
)
from app.recommendation.models import AnalysisScope


@dataclass(frozen=True)
class Stage2Input:
    ctx: SelectionContext
    req: RegressionSelectionRequest
    blocks: list[BlockId]
    primary_raw: CompareCandidate
    analysis_scope: AnalysisScope
    region_col: str | None


def _anchor_codes(scope: AnalysisScope, req: RegressionSelectionRequest) -> tuple[str, ...]:
    if scope.anchor_unit and scope.anchor_unit.code:
        return (scope.anchor_unit.code,)
    codes = tuple(c for c in (req.region_codes or []) if str(c).strip())
    return codes


def _twin_neighbor_codes(req: RegressionSelectionRequest) -> tuple[str, ...]:
    out: list[str] = []
    seen: set[str] = set()
    for row in req.profile_twin_neighbors or []:
        code = str(row.get("region_code") or row.get("twin_region_code") or "").strip()
        if code and code not in seen:
            seen.add(code)
            out.append(code)
    return tuple(out)


def _pool_candidate(
    m: PoolingCandidateMetrics,
    *,
    local_cv: float | None,
) -> RecommendationPoolCandidate:
    delta = None
    if local_cv is not None and m.cv_mape is not None:
        delta = round(local_cv - m.cv_mape, 2)
    return RecommendationPoolCandidate(
        candidate_id=m.candidate_id,
        label=m.label,
        n=m.n,
        region_codes=list(m.region_codes),
        adj_r_squared=m.adj_r_squared,
        mape=m.mape,
        cv_mape=m.cv_mape,
        cv_mape_delta=delta,
    )


def run_stage2_twin(conn, inp: Stage2Input) -> RecommendationStage2:
    blocks = list(inp.blocks)
    scale: ResponseScale = inp.primary_raw.fit.response_scale
    local_cv = inp.primary_raw.fit.cv_mape
    anchor_codes = _anchor_codes(inp.analysis_scope, inp.req)
    twin_codes = _twin_neighbor_codes(inp.req)

    if not twin_codes:
        return RecommendationStage2(
            ran=False,
            skipped_reason="Profile Twin 후보가 없습니다.",
            fixed_blocks=blocks,
            fixed_response_scale=scale,
            local_cv_mape=local_cv,
        )

    pooling = evaluate_pooling_candidates(
        conn,
        local_ctx=inp.ctx,
        req=inp.req,
        blocks=blocks,
        local_fit=inp.primary_raw.fit,
        anchor_region_codes=anchor_codes,
        twin_region_codes=twin_codes,
        admin_level=inp.ctx.admin_level,
        region_col=inp.region_col,
        fixed_response_scale=scale,
    )

    twin_pools = [
        _pool_candidate(c, local_cv=local_cv)
        for c in pooling.candidates
        if c.candidate_id != "local"
    ]

    primary_pool: RecommendationPoolCandidate | None = None
    if pooling.decision != "local":
        for c in pooling.candidates:
            if c.candidate_id == pooling.decision:
                primary_pool = _pool_candidate(c, local_cv=local_cv)
                break

    return RecommendationStage2(
        ran=True,
        pools=twin_pools,
        primary=primary_pool,
        local_cv_mape=local_cv,
        twin_gates=list(pooling.twin_gates),
        decision=pooling.decision,
        decision_reason=pooling.decision_reason,
        fixed_blocks=blocks,
        fixed_response_scale=scale,
    )
