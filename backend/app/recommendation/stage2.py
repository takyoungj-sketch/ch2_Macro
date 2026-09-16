"""R2 — stage2 Twin: 식 고정 표본 보강(diagnose) + 확인용 전체 풀 재탐색."""

from __future__ import annotations

from dataclasses import dataclass

from app.built.regression.region_features import (
    is_region_block,
    normalize_region_feature_tier,
)
from app.built.regression.engine import _region_col_for_scatter
from app.built.regression.selection.blocks import BlockId, spec_from_blocks
from app.built.regression.selection.context import SelectionContext
from app.built.regression.selection.pooling import (
    evaluate_pooling_candidates,
    research_full_twin_pool,
)
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


def _blocks_with_region_leaf(blocks: list[BlockId] | list[str]) -> list[BlockId]:
    """Twin1: Local 식에 지역 더미가 있든 없든 region_leaf를 붙인다."""
    out: list[BlockId] = []
    seen: set[str] = set()
    for b in (*blocks, "region_leaf"):
        key = str(b)
        if key in seen:
            continue
        seen.add(key)
        out.append(b)  # type: ignore[arg-type]
    return out


def _twin1_region_col(
    ctx: SelectionContext,
    blocks: list[BlockId],
    fallback: str | None,
) -> str | None:
    spec = spec_from_blocks(blocks)
    admin_level = getattr(ctx, "admin_level", None)
    addr4_city = bool(getattr(ctx, "addr4_city", False))
    return _region_col_for_scatter(spec, admin_level, addr4_city) or fallback


def _rank1_pool_rows(candidates: list[PoolingCandidateMetrics]) -> list[PoolingCandidateMetrics]:
    rank1 = [
        c
        for c in candidates
        if c.candidate_id != "local" and int(c.prefix_k or 0) == 1
    ]
    if rank1:
        return rank1
    others = [c for c in candidates if c.candidate_id != "local"]
    if not others:
        return []
    return [min(others, key=lambda c: int(c.prefix_k or 10**9))]


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
    # Twin1: Local 식·척도 고정 + 쌍둥이 1위만 + 지역 더미(region_leaf) 강제.
    # region_* 프로파일 공변량을 풀에 다시 넣어 재탐색하지 않는다. Twin2(재탐색)는 별 버튼.
    region_tier = normalize_region_feature_tier(getattr(inp.req, "region_feature_tier", None))
    scale: ResponseScale = inp.primary_raw.fit.response_scale
    primary_blocks = list(inp.primary_raw.blocks)
    twin1_blocks = _blocks_with_region_leaf(primary_blocks)
    twin1_region_col = _twin1_region_col(inp.ctx, twin1_blocks, inp.region_col)
    region_candidates = [b for b in twin1_blocks if is_region_block(str(b))]
    local_cv = inp.primary_raw.fit.cv_mape
    anchor_codes = _anchor_codes(inp.analysis_scope, inp.req)

    validated = validate_recommend_twin_neighbors(
        conn,
        req=inp.req,
        admin_level=inp.ctx.admin_level,
        search_pool=list(inp.blocks),
        anchor_df=inp.ctx.df,
    )
    twin_codes = tuple(validated.twin_codes[:1])
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
        blocks=primary_blocks,
        local_fit=inp.primary_raw.fit,
        anchor_region_codes=anchor_codes,
        twin_region_codes=twin_codes,
        admin_level=inp.ctx.admin_level,
        region_col=inp.region_col,
        twin_blocks=twin1_blocks,
        twin_region_col=twin1_region_col,
        fixed_response_scale=scale,
        mode="diagnose",
    )

    gate_note = hard_gate_summary(list(pooling.twin_gates))
    skipped_parts = [p for p in (validated.gate_summary, gate_note) if p]

    local_metrics = next((c for c in pooling.candidates if c.candidate_id == "local"), None)
    rank1_candidates = _rank1_pool_rows(list(pooling.candidates))
    prefix_rows = []
    for c in rank1_candidates:
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

    twin_pools = [_pool_candidate(c, local_cv=local_search) for c in rank1_candidates]
    inspect_src = rank1_candidates[0] if rank1_candidates else None
    inspect_pool = _pool_candidate(inspect_src, local_cv=local_search) if inspect_src else None

    primary_pool: RecommendationPoolCandidate | None = None
    recommended_blocks = primary_blocks
    recommended_scale = scale
    if prefix_decision.decision != "local":
        for c in rank1_candidates:
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

    research = None
    research_ran = False
    research_skipped_reason = None
    if bool(getattr(inp.req, "run_stage2_research", False)):
        research_ran = True
        research_metrics = research_full_twin_pool(
            conn,
            local_ctx=inp.ctx,
            req=req_for_pool,
            search_pool=list(inp.blocks),
            anchor_region_codes=anchor_codes,
            twin_region_codes=twin_codes,
            admin_level=inp.ctx.admin_level,
            region_col=inp.region_col,
        )
        if research_metrics is None:
            research_skipped_reason = "Twin 1위 표본에서 식을 다시 고를 수 없습니다."
        else:
            research = _pool_candidate(research_metrics, local_cv=local_search)

    return RecommendationStage2(
        ran=True,
        pools=twin_pools,
        primary=primary_pool,
        inspect_pool=inspect_pool,
        research=research,
        research_ran=research_ran,
        research_skipped_reason=research_skipped_reason,
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
