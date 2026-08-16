"""R2 — stage2 Twin pool (표본 확장 후 재탐색)."""

from __future__ import annotations

from dataclasses import dataclass

from app.built.regression.region_features import (
    is_region_block,
    normalize_region_feature_tier,
    region_blocks_for_asset,
)
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
from app.recommendation.twin_validation import (
    build_twin_validation_verdict,
    hard_gate_summary,
    validate_recommend_twin_neighbors,
)


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


def _pool_candidate(
    m: PoolingCandidateMetrics,
    *,
    local_cv: float | None,
) -> RecommendationPoolCandidate:
    delta = None
    if local_cv is not None and m.cv_mape is not None:
        delta = round(local_cv - m.cv_mape, 2)
    variables = spec_from_blocks(m.blocks) if m.blocks else None
    return RecommendationPoolCandidate(
        candidate_id=m.candidate_id,
        label=m.label,
        n=m.n,
        region_codes=list(m.region_codes),
        adj_r_squared=m.adj_r_squared,
        mape=m.mape,
        cv_mape=m.cv_mape,
        cv_mape_delta=delta,
        blocks=list(m.blocks),
        response_scale=m.response_scale,
        variables=variables,
    )


def run_stage2_twin(conn, inp: Stage2Input) -> RecommendationStage2:
    search_pool = list(inp.blocks)
    # Stage1 Local-only에서는 region_*가 상수로 풀에서 빠진다.
    # Twin 다지역 표본에서는 다시 후보로 넣어 RT 축이 식별 가능하게 한다.
    region_tier = normalize_region_feature_tier(getattr(inp.req, "region_feature_tier", None))
    region_candidates: list[str] = []
    if getattr(inp.req, "include_region_features", False):
        for b in region_blocks_for_asset(inp.req.asset_type, tier=region_tier):
            if b not in search_pool:
                search_pool.append(b)  # type: ignore[arg-type]
        region_candidates = [b for b in search_pool if is_region_block(str(b))]
    scale: ResponseScale = inp.primary_raw.fit.response_scale
    primary_blocks = list(inp.primary_raw.blocks)
    local_cv = inp.primary_raw.fit.cv_mape
    anchor_codes = _anchor_codes(inp.analysis_scope, inp.req)

    validated = validate_recommend_twin_neighbors(
        conn,
        req=inp.req,
        admin_level=inp.ctx.admin_level,
        search_pool=search_pool,
        anchor_df=inp.ctx.df,
    )
    twin_codes = validated.twin_codes
    req_for_pool = inp.req.model_copy(update={"profile_twin_neighbors": validated.neighbors})

    if not twin_codes:
        reason = validated.gate_summary or "Profile Twin 후보가 없습니다."
        return RecommendationStage2(
            ran=False,
            skipped_reason=reason,
            fixed_blocks=primary_blocks,
            recommended_blocks=primary_blocks,
            fixed_response_scale=scale,
            local_cv_mape=local_cv,
            region_candidate_blocks=region_candidates,
            region_feature_tier=region_tier if region_candidates else None,
            twin_validation=build_twin_validation_verdict(
                ran=False,
                skipped_reason=reason,
                local_cv_mape=local_cv,
                decision="local",
                primary=None,
                pools=[],
            ),
        )

    pooling = evaluate_pooling_candidates(
        conn,
        local_ctx=inp.ctx,
        req=req_for_pool,
        blocks=search_pool,
        local_fit=inp.primary_raw.fit,
        anchor_region_codes=anchor_codes,
        twin_region_codes=twin_codes,
        admin_level=inp.ctx.admin_level,
        region_col=inp.region_col,
        mode="optimize",
    )

    gate_note = hard_gate_summary(list(pooling.twin_gates))
    skipped_parts = [p for p in (validated.gate_summary, gate_note) if p]

    twin_pools = [
        _pool_candidate(c, local_cv=local_cv)
        for c in pooling.candidates
        if c.candidate_id != "local"
    ]

    primary_pool: RecommendationPoolCandidate | None = None
    recommended_blocks = primary_blocks
    recommended_scale = scale
    if pooling.decision != "local":
        for c in pooling.candidates:
            if c.candidate_id == pooling.decision:
                primary_pool = _pool_candidate(c, local_cv=local_cv)
                if c.blocks:
                    recommended_blocks = list(c.blocks)
                if c.response_scale:
                    recommended_scale = c.response_scale
                break

    decision_reason = pooling.decision_reason
    if skipped_parts and decision_reason:
        decision_reason = "; ".join(skipped_parts) + " — " + decision_reason
    elif skipped_parts:
        decision_reason = "; ".join(skipped_parts)

    twin_validation = build_twin_validation_verdict(
        ran=True,
        skipped_reason=None,
        local_cv_mape=local_cv,
        decision=pooling.decision,
        primary=primary_pool,
        pools=twin_pools,
    )

    return RecommendationStage2(
        ran=True,
        pools=twin_pools,
        primary=primary_pool,
        local_cv_mape=local_cv,
        twin_gates=list(pooling.twin_gates),
        decision=pooling.decision,
        decision_reason=decision_reason,
        twin_validation=twin_validation,
        fixed_blocks=recommended_blocks,
        recommended_blocks=recommended_blocks,
        fixed_response_scale=recommended_scale,
        region_candidate_blocks=region_candidates,
        region_feature_tier=region_tier if region_candidates else None,
    )
