"""단계형 추천 orchestration (R1 stage1 + R2 stage2)."""

from __future__ import annotations

from dataclasses import dataclass

from app.built.regression.selection.best_subset import CompareResult, run_group_best_subset
from app.built.regression.selection.blocks import BlockId, spec_from_blocks
from app.built.regression.selection.context import (
    region_col_for_context,
    resolve_selection_context,
    with_complete_case,
)
from app.built.schemas import (
    RegressionRecommendResponse,
    RegressionSelectionRequest,
    RecommendationSatisfaction,
    RecommendationStage1,
    RecommendationStage2,
)
from app.recommendation.built_pool import filter_pool_by_coverage, resolve_recommendation_pool
from app.recommendation.ranks import (
    candidate_from_compare,
    pick_alternate_explanatory,
    pick_primary_predictive,
)
from app.recommendation.satisfaction import (
    built_min_fit_n,
    built_min_local_n,
    lookup_built_satisfaction,
)
from app.recommendation.scope import resolve_built_analysis_scope
from app.recommendation.stage2 import Stage2Input, run_stage2_twin
from app.recommendation.coef_narrative import build_coefficient_narratives
from app.recommendation.conclusion import build_recommendation_conclusion
from app.recommendation.diagnostics import build_diagnostics_checklist
from app.recommendation.termination import (
    build_termination_r2,
    narrative_hints_from_termination,
)

MIN_SELECTION_N = 30
MAX_COMPARE_SUBSETS = 128


@dataclass(frozen=True)
class _Stage1Bundle:
    ctx: object
    pool: list[BlockId]
    region_col: str | None
    result: CompareResult
    primary_raw: object


def _warnings_for_n(n: int) -> list[str]:
    if n < MIN_SELECTION_N:
        return [f"표본 n={n} — 신뢰도 낮을 수 있습니다 (권장 n≥{MIN_SELECTION_N})."]
    return []


def _warnings_for_cv_mape(value: float | None) -> list[str]:
    if value is None:
        return []
    if value >= 70:
        return [
            f"CV-MAPE {value:.2f}% — 예측 안정성이 매우 낮습니다. 설명용 결과로만 해석하세요."
        ]
    if value >= 50:
        return [f"CV-MAPE {value:.2f}% — 예측 오차가 클 수 있어 주의가 필요합니다."]
    return []


def _twin_recommended(
    *,
    grade_proceed: bool,
    selection_n: int,
    scope_n_tx: int,
    fit_n: int,
    has_twins: bool,
) -> bool:
    if not has_twins:
        return False
    if selection_n < built_min_local_n() or scope_n_tx < built_min_local_n():
        return True
    if fit_n < built_min_fit_n():
        return True
    return grade_proceed


def _build_stage1(conn, req: RegressionSelectionRequest) -> tuple:
    analysis_scope = resolve_built_analysis_scope(conn, req)

    ctx = resolve_selection_context(conn, req)
    base_pool = resolve_recommendation_pool(ctx, unified=ctx.unified)
    pool, excluded_blocks = filter_pool_by_coverage(ctx, base_pool)
    if not pool:
        detail = "SSOT 추천 변수 풀이 비어 있습니다."
        if excluded_blocks:
            detail += " 제외: " + "; ".join(excluded_blocks)
        raise ValueError(detail)

    pool_spec = spec_from_blocks(pool)
    region_col = region_col_for_context(ctx, pool_spec)
    ctx = with_complete_case(ctx, pool, region_col=region_col)

    req_for_fit = req.model_copy(update={"variables": pool_spec})
    result = run_group_best_subset(ctx, req_for_fit, pool)
    if result is None:
        raise ValueError("1단계 추천 모형을 적합할 수 없습니다. 표본·scope를 확인하세요.")

    primary_raw = pick_primary_predictive(result.by_cv_mape, result.by_mape, result.by_aic)
    if primary_raw is None:
        raise ValueError("적합된 후보 모형이 없습니다.")

    alternate_raw = pick_alternate_explanatory(result.by_aic)
    primary = candidate_from_compare(primary_raw)
    alternate = candidate_from_compare(alternate_raw) if alternate_raw else None

    cv_mape = primary.metrics.cv_mape
    grade = lookup_built_satisfaction(
        cv_mape=cv_mape,
        selection_n=ctx.selection_n,
        asset_slice=analysis_scope.asset_slice,
    )

    stage1 = RecommendationStage1(
        candidates_explanatory=[candidate_from_compare(c) for c in result.by_aic],
        candidates_predictive=[
            candidate_from_compare(c) for c in (result.by_cv_mape or result.by_mape)
        ],
        primary=primary,
        alternate=alternate,
        selection_n=ctx.selection_n,
        fit_n=primary_raw.fit.n,
        candidate_pool=list(pool),
        satisfaction=RecommendationSatisfaction(
            grade=grade.grade,
            stars=grade.stars,
            cv_mape=cv_mape,
        ),
        total_subsets=result.total_subsets,
        truncated=result.truncated,
    )

    bundle = _Stage1Bundle(
        ctx=ctx,
        pool=pool,
        region_col=region_col,
        result=result,
        primary_raw=primary_raw,
    )
    return analysis_scope, stage1, primary, alternate, grade, bundle, excluded_blocks


def run_stage1_local(conn, req: RegressionSelectionRequest) -> RegressionRecommendResponse:
    return run_recommendation(conn, req)


def run_recommendation(conn, req: RegressionSelectionRequest) -> RegressionRecommendResponse:
    analysis_scope, stage1, primary, alternate, grade, bundle, excluded_blocks = _build_stage1(
        conn, req
    )

    warnings = _warnings_for_n(stage1.selection_n) + _warnings_for_cv_mape(
        stage1.satisfaction.cv_mape
    )
    if excluded_blocks:
        warnings.append(
            "표본에 유효 값이 부족해 탐색 풀에서 제외: " + "; ".join(excluded_blocks)
        )
    if stage1.truncated:
        warnings.append(
            f"조합 {stage1.total_subsets}개 중 {MAX_COMPARE_SUBSETS}개만 평가했습니다."
        )

    stage2: RecommendationStage2 | None = None
    has_twins = bool(req.profile_twin_neighbors)
    twin_recommended = _twin_recommended(
        grade_proceed=grade.proceed_twin,
        selection_n=stage1.selection_n,
        scope_n_tx=analysis_scope.scope_n_tx,
        fit_n=stage1.fit_n,
        has_twins=has_twins,
    )

    if req.run_stage2 and twin_recommended and has_twins:
        stage2 = run_stage2_twin(
            conn,
            Stage2Input(
                ctx=bundle.ctx,
                req=req,
                blocks=bundle.pool,
                primary_raw=bundle.primary_raw,
                analysis_scope=analysis_scope,
                region_col=bundle.region_col,
            ),
        )
    elif req.run_stage2 and not has_twins:
        stage2 = RecommendationStage2(
            ran=False,
            skipped_reason="Profile Twin 후보가 전달되지 않았습니다.",
            fixed_blocks=list(bundle.primary_raw.blocks),
            fixed_response_scale=bundle.primary_raw.fit.response_scale,
            local_cv_mape=stage1.satisfaction.cv_mape,
        )

    termination = build_termination_r2(
        grade=grade,
        selection_n=stage1.selection_n,
        scope_n_tx=analysis_scope.scope_n_tx,
        primary=primary,
        alternate=alternate,
        truncated=stage1.truncated,
        stage2=stage2,
    )

    conclusion = build_recommendation_conclusion(
        cv_mape=stage1.satisfaction.cv_mape,
        grade=grade,
        scope_n_tx=analysis_scope.scope_n_tx,
        selection_n=stage1.selection_n,
        fit_n=stage1.fit_n,
        has_twins=has_twins,
        twin_recommended=twin_recommended,
        stage2=stage2,
    )

    coef_narratives = build_coefficient_narratives(
        primary.coefficients,
        response_scale=primary.response_scale,
    )
    diagnostics_checklist = build_diagnostics_checklist(
        scope_n_tx=analysis_scope.scope_n_tx,
        selection_n=stage1.selection_n,
        fit_n=stage1.fit_n,
        cv_mape=stage1.satisfaction.cv_mape,
        mape=primary.metrics.mape,
        verdict=conclusion.verdict,
        exclude_outliers_iqr=bool(req.exclude_outliers_iqr),
        primary_blocks=list(primary.blocks),
        variable_limit=conclusion.variable_limit,
    )

    return RegressionRecommendResponse(
        analysis_scope=analysis_scope,
        stage1=stage1,
        stage2=stage2,
        termination=termination,
        conclusion=conclusion,
        diagnostics_checklist=diagnostics_checklist,
        coefficient_narratives=coef_narratives,
        narrative_hints=narrative_hints_from_termination(termination),
        warnings=warnings,
    )
