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
from app.recommendation.twin_structure import decide_twin_prefix, key_coefficients_from_fit
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
        confirm_cv_mape=m.confirm_cv_mape,
        blocks=list(m.blocks),
        response_scale=m.response_scale,
        variables=variables,
        prefix_k=int(m.prefix_k or 0),
        key_coefficients=dict(m.key_coefficients or {}),
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

    local_metrics = next((c for c in pooling.candidates if c.candidate_id == "local"), None)
    prefix_rows = []
    for c in pooling.candidates:
        if c.candidate_id == "local":
            continue
        prefix_rows.append(
            {
                "candidate_id": c.candidate_id,
                "label": c.label,
                "prefix_k": int(c.prefix_k or 0),
                "region_codes": list(c.region_codes),
                "n": c.n,
                "search_cv_mape": c.cv_mape,
                "confirm_cv_mape": c.confirm_cv_mape,
                "key_coefficients": dict(c.key_coefficients or {}),
                "blocks": list(c.blocks),
            }
        )

    local_search = local_metrics.cv_mape if local_metrics else local_cv
    local_confirm = local_metrics.confirm_cv_mape if local_metrics else None
    local_n = int(local_metrics.n) if local_metrics else int(getattr(inp.primary_raw.fit, "n", 0) or 0)
    local_coeffs = dict(local_metrics.key_coefficients) if local_metrics else key_coefficients_from_fit(inp.primary_raw.fit)

    prefix_decision = decide_twin_prefix(
        local_n=local_n,
        local_search_cv=local_search,
        local_confirm_cv=local_confirm,
        local_coeffs=local_coeffs,
        local_blocks=primary_blocks,
        prefixes=prefix_rows,
    )

    twin_pools = [
        _pool_candidate(c, local_cv=local_search)
        for c in pooling.candidates
        if c.candidate_id != "local"
    ]

    primary_pool: RecommendationPoolCandidate | None = None
    recommended_blocks = primary_blocks
    recommended_scale = scale
    if prefix_decision.decision != "local":
        for c in pooling.candidates:
            if c.candidate_id == prefix_decision.decision:
                primary_pool = _pool_candidate(c, local_cv=local_search)
                if c.blocks:
                    recommended_blocks = list(c.blocks)
                if c.response_scale:
                    recommended_scale = c.response_scale
                break

    decision_reason = prefix_decision.decision_reason
    if skipped_parts and decision_reason:
        decision_reason = "; ".join(skipped_parts) + " — " + decision_reason
    elif skipped_parts:
        decision_reason = "; ".join(skipped_parts)

    twin_validation = build_twin_validation_verdict(
        ran=True,
        skipped_reason=None,
        local_cv_mape=local_search,
        decision=prefix_decision.decision,
        primary=primary_pool,
        pools=twin_pools,
        prefix=prefix_decision,
    )

    return RecommendationStage2(
        ran=True,
        pools=twin_pools,
        primary=primary_pool,
        local_cv_mape=local_search,
        twin_gates=list(pooling.twin_gates),
        decision=prefix_decision.decision,
        decision_reason=decision_reason,
        twin_validation=twin_validation,
        fixed_blocks=recommended_blocks,
        recommended_blocks=recommended_blocks,
        fixed_response_scale=recommended_scale,
        region_candidate_blocks=region_candidates,
        region_feature_tier=region_tier if region_candidates else None,
        local_search_cv_mape=local_search,
        local_confirm_cv_mape=local_confirm,
        region_effect=prefix_decision.region_effect,
        twin_experiments=prefix_decision.steps,
    )
