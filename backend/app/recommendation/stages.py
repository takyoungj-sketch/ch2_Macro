"""단계형 추천 orchestration (R1 stage1 + R2 stage2)."""

from __future__ import annotations

from dataclasses import dataclass, replace

from app.built.regression.region_features import (
    attach_region_features,
    normalize_region_feature_tier,
    region_blocks_for_asset,
)
from app.built.regression.selection.best_subset import (
    MAX_SUBSETS as MAX_COMPARE_SUBSETS,
    CompareResult,
    run_group_best_subset,
)
from app.built.regression.selection.blocks import BlockId, spec_from_blocks
from app.built.regression.selection.context import (
    SelectionContext,
    region_col_for_context,
    resolve_selection_context,
    with_complete_case,
)
from app.built.schemas import (
    AssessedSideNote,
    RegressionRecommendResponse,
    RegressionSelectionRequest,
    RecommendationSatisfaction,
    RecommendationStage1,
    RecommendationStage2,
)
from app.recommendation.built_pool import (
    filter_pool_by_coverage,
    fit_is_offerable,
    resolve_recommendation_pool,
)
from app.recommendation.ranks import (
    annotate_predictive_band,
    candidate_from_compare,
    pick_alternate_explanatory,
    pick_primary_predictive,
    representative_verdict,
)
from app.recommendation.cv_fitness import offer_structure_twin
from app.regression_sample_judge import (
    PROVISION_FOLLOWUP,
    identification_note,
    judge_exog,
    provision_note,
)
from app.recommendation.satisfaction import (
    built_min_fit_n,
    built_min_local_n,
    grade_cv_basis,
    lookup_built_satisfaction,
    lookup_predictive_fit,
)
from app.recommendation.scope import resolve_built_analysis_scope
from app.recommendation.twin_validation import build_twin_validation_verdict
from app.recommendation.stage2 import Stage2Input, run_stage2_twin
from app.recommendation.coef_narrative import build_coefficient_narratives
from app.recommendation.conclusion import build_recommendation_conclusion
from app.recommendation.diagnostics import build_diagnostics_checklist
from app.recommendation.termination import (
    build_termination_r2,
    narrative_hints_from_termination,
)

@dataclass(frozen=True)
class _Stage1Bundle:
    ctx: object
    pool: list[BlockId]
    region_col: str | None
    result: CompareResult
    primary_raw: object


def _warnings_for_cv_mape(value: float | None) -> list[str]:
    if value is None:
        return []
    if value >= 75:
        return [
            f"CV-MAPE {value:.2f}% — 개별 가격 설명에는 한계가 큽니다. 구조 탐색으로 해석하세요."
        ]
    if value >= 60:
        return [f"CV-MAPE {value:.2f}% — 예측값보다 계수 방향·상대 영향을 중심으로 보세요."]
    return []


def _twin_opt_in_allowed(admin_level: str | None) -> bool:
    """시군구·구에는 Twin을 붙이지 않는다 (D-066). 권고 여부와 별개로 실행 가능 여부."""
    return (admin_level or "").strip().lower() not in {"sigungu", "gu"}


def _twin_recommended(
    *,
    cv_mape: float | None,
    mape: float | None,
    selection_n: int,
    scope_n_tx: int,
    fit_n: int,
    has_twins: bool,
    admin_level: str | None = None,
) -> bool:
    return offer_structure_twin(
        has_twins=has_twins,
        cv_mape=cv_mape,
        mape=mape,
        selection_n=selection_n,
        scope_n_tx=scope_n_tx,
        fit_n=fit_n,
        min_local_n=built_min_local_n(),
        min_fit_n=built_min_fit_n(),
        admin_level=admin_level,
    )


def _apply_region_features(
    ctx: SelectionContext,
    req: RegressionSelectionRequest,
) -> SelectionContext:
    if not getattr(req, "include_region_features", False):
        return ctx
    pv = (req.profile_version or "v2.1-national").strip() or "v2.1-national"
    wy = int(req.profile_window_years or req.window_years or 3)
    tier = normalize_region_feature_tier(getattr(req, "region_feature_tier", None))
    blocks = region_blocks_for_asset(req.asset_type, tier=tier)
    df = attach_region_features(
        ctx.df,
        profile_version=pv,
        window_years=wy,
        block_ids=blocks,
    )
    return replace(ctx, df=df)


def _confirm_note(fit) -> str | None:
    """확인 CV가 없을 때의 이유. 있으면 None.

    후보 적합 단계에서 마지막 연도를 이미 홀드아웃해 두므로(D-074) 여기서 다시
    계산하지 않는다. 예전에는 1위 모형만 따로 재계산했는데, 그 랭킹 CV가 마지막
    연도를 포함하고 있어 확인이 확인이 아니었다.
    """
    if fit.confirm_cv_mape is not None:
        return None
    return "확인 CV 생략 — 고유 계약연도가 3년 미만이거나 마지막 연도 fold를 적합할 수 없음"


def _provision_notes(fit) -> list[str]:
    model = getattr(fit, "model", None)
    exog = getattr(getattr(model, "model", None), "exog", None)
    if exog is None:
        return []
    try:
        verdict = judge_exog(exog)
    except (AttributeError, TypeError, ValueError):
        return []
    notes: list[str] = []
    text = provision_note(verdict)
    if text:
        notes.append(text)
        notes.append(PROVISION_FOLLOWUP)
    identified = identification_note(verdict)
    if identified:
        notes.append(identified)
    return notes


def _assessed_side(ctx, primary_raw, req) -> AssessedSideNote | None:
    """대표식에 개별공시지가를 더한 옆 비교. 공통 순위에 넣지 않는다."""
    if not bool(getattr(req, "enrich", False)):
        return None
    if not bool(getattr(req.variables, "assessed_land_price", False)):
        return None
    if "assessed_land_price" not in ctx.df.columns:
        return AssessedSideNote(n=0, note="개별공시지가 열이 없어 옆 비교를 만들지 않습니다.")

    import pandas as pd

    from app.built.regression.engine import _build_design_matrix
    from app.built.regression.selection.blocks import spec_from_blocks
    from app.built.regression.selection.fit import rolling_time_cv_split

    assessed = pd.to_numeric(ctx.df["assessed_land_price"], errors="coerce")
    frame = ctx.df.loc[assessed.notna() & (assessed > 0)]
    spec = spec_from_blocks(list(primary_raw.blocks)).model_copy(
        update={"assessed_land_price": True}
    )
    if len(frame) < built_min_fit_n():
        return AssessedSideNote(
            n=int(len(frame)),
            note=f"개별공시지가 유효 {int(len(frame))}건이라 옆 비교를 만들지 않습니다.",
        )
    scale = primary_raw.fit.response_scale
    region_col = region_col_for_context(ctx, spec)
    y, x_frame, _meta = _build_design_matrix(
        frame,
        spec,
        unified=ctx.unified,
        response_scale=scale,
        region_col=region_col,
        categorical_missing="keep_unknown",
    )
    if len(y) < built_min_fit_n() or x_frame.empty:
        return AssessedSideNote(
            n=int(len(y)),
            note="개별공시지가가 있는 거래만 쓴 식은 적합 건수가 부족합니다.",
        )
    try:
        import statsmodels.api as sm

        model = sm.OLS(y, sm.add_constant(x_frame, has_constant="add")).fit()
        if judge_exog(model.model.exog).tier == "blocked":
            return AssessedSideNote(
                n=int(len(y)),
                note="개별공시지가를 더한 식은 계산 불가입니다. 위의 순위가 아닙니다.",
            )
    except (AttributeError, TypeError, ValueError):
        return AssessedSideNote(
            n=int(len(y)),
            note="개별공시지가를 더한 식을 적합하지 못했습니다. 위의 순위가 아닙니다.",
        )
    search, _folds, _confirm, _cfolds, _skip = rolling_time_cv_split(
        frame,
        spec,
        unified=ctx.unified,
        response_scale=scale,
        region_col=region_col,
        time_adjuster=ctx.time_adjuster,
    )
    cv_text = f"{float(search):.1f}%" if search is not None else "없음"
    return AssessedSideNote(
        n=int(len(y)),
        cv_mape=None if search is None else float(search),
        note=(
            f"개별공시지가가 있는 거래 {int(len(y))}건으로 대표식에 그 열을 더한 식입니다. "
            f"CV-MAPE {cv_text}. 행이 달라 위의 예측형 순위가 아닙니다."
        ),
    )


def _build_stage1(conn, req: RegressionSelectionRequest) -> tuple:
    analysis_scope = resolve_built_analysis_scope(conn, req)

    ctx = resolve_selection_context(conn, req)
    ctx = _apply_region_features(ctx, req)
    include_structure = bool(getattr(req, "enrich", False)) and bool(
        getattr(req.variables, "structure_dummy", False)
    )
    base_pool = resolve_recommendation_pool(
        ctx, unified=ctx.unified, include_structure=include_structure
    )
    if getattr(req, "include_region_features", False):
        # region 공변량과 leaf 더미는 1차에서 동시 사용하지 않음
        base_pool = [b for b in base_pool if b != "region_leaf"]
        tier = normalize_region_feature_tier(getattr(req, "region_feature_tier", None))
        for b in region_blocks_for_asset(req.asset_type, tier=tier):
            if b not in base_pool:
                base_pool.append(b)  # type: ignore[arg-type]
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
    result = run_group_best_subset(ctx, req_for_fit, pool, eligible=fit_is_offerable)
    if result is None:
        raise ValueError("1단계 추천 모형을 적합할 수 없습니다. 표본·scope를 확인하세요.")

    primary_raw = pick_primary_predictive(result.by_cv_mape, result.by_mape, result.by_aic)
    if primary_raw is None:
        raise ValueError("적합된 후보 모형이 없습니다.")

    alternate_raw = pick_alternate_explanatory(result.by_aic)
    primary = candidate_from_compare(primary_raw)
    alternate = candidate_from_compare(alternate_raw) if alternate_raw else None

    primary_fit = primary_raw.fit
    grade_cv, grade_basis = grade_cv_basis(
        primary.metrics.cv_mape, primary_fit.confirm_cv_mape
    )
    grade = lookup_built_satisfaction(
        cv_mape=grade_cv,
        selection_n=ctx.selection_n,
        asset_slice=analysis_scope.asset_slice,
    )

    predictive_raw = result.by_cv_mape or result.by_mape
    predictive = [candidate_from_compare(c) for c in predictive_raw]
    judgments, parity_notes = annotate_predictive_band(
        predictive, ns=[c.fit.n for c in predictive_raw]
    )
    representative_confirmed, representative_note = representative_verdict(primary_fit)
    stage1 = RecommendationStage1(
        candidates_explanatory=[candidate_from_compare(c) for c in result.by_aic],
        candidates_predictive=predictive,
        predictive_judgments=judgments,
        parity_notes=parity_notes,
        primary=primary,
        alternate=alternate,
        selection_n=ctx.selection_n,
        fit_n=primary_raw.fit.n,
        candidate_pool=list(pool),
        satisfaction=RecommendationSatisfaction(
            grade=grade.grade,
            stars=grade.stars,
            cv_mape=grade_cv,
            label_ko=grade.label_ko,
            grade_basis=grade_basis,
        ),
        total_subsets=result.total_subsets,
        truncated=result.truncated,
        primary_confirm_cv_mape=primary_fit.confirm_cv_mape,
        primary_confirm_cv_folds=primary_fit.confirm_cv_folds,
        primary_confirm_note=_confirm_note(primary_fit),
        primary_cv_extreme_rate=primary_fit.cv_search.extreme_rate,
        primary_cv_median_ape=primary_fit.cv_search.median_ape,
        sample_drop_notes=list(ctx.numeric_drop_notes),
        provision_notes=_provision_notes(primary_fit),
        assessed_side=_assessed_side(ctx, primary_raw, req),
        representative_confirmed=representative_confirmed,
        representative_note=representative_note,
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

    warnings = _warnings_for_cv_mape(stage1.satisfaction.cv_mape)
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
    pred_fit = lookup_predictive_fit(
        cv_mape=stage1.satisfaction.cv_mape,
        asset_slice=analysis_scope.asset_slice,
    )
    twin_recommended = _twin_recommended(
        cv_mape=stage1.satisfaction.cv_mape,
        mape=primary.metrics.mape,
        selection_n=stage1.selection_n,
        scope_n_tx=analysis_scope.scope_n_tx,
        fit_n=stage1.fit_n,
        has_twins=has_twins,
        admin_level=analysis_scope.admin_level,
    )

    if (req.run_stage2 or req.run_stage2_research) and has_twins and _twin_opt_in_allowed(analysis_scope.admin_level):
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
    elif (req.run_stage2 or req.run_stage2_research) and not has_twins:
        skip_reason = "Profile Twin 후보가 전달되지 않았습니다."
        stage2 = RecommendationStage2(
            ran=False,
            skipped_reason=skip_reason,
            fixed_blocks=list(bundle.primary_raw.blocks),
            recommended_blocks=list(bundle.primary_raw.blocks),
            fixed_response_scale=bundle.primary_raw.fit.response_scale,
            local_cv_mape=stage1.satisfaction.cv_mape,
            twin_validation=build_twin_validation_verdict(
                ran=False,
                skipped_reason=skip_reason,
                local_cv_mape=stage1.satisfaction.cv_mape,
                decision="local",
                primary=None,
                pools=[],
            ),
        )
    elif (req.run_stage2 or req.run_stage2_research) and not _twin_opt_in_allowed(analysis_scope.admin_level):
        skip_reason = "시군구·구 초점에는 Twin 실험을 붙이지 않습니다."
        stage2 = RecommendationStage2(
            ran=False,
            skipped_reason=skip_reason,
            fixed_blocks=list(bundle.primary_raw.blocks),
            recommended_blocks=list(bundle.primary_raw.blocks),
            fixed_response_scale=bundle.primary_raw.fit.response_scale,
            local_cv_mape=stage1.satisfaction.cv_mape,
            twin_validation=build_twin_validation_verdict(
                ran=False,
                skipped_reason=skip_reason,
                local_cv_mape=stage1.satisfaction.cv_mape,
                decision="local",
                primary=None,
                pools=[],
            ),
        )

    termination = build_termination_r2(
        grade=grade,
        selection_n=stage1.selection_n,
        scope_n_tx=analysis_scope.scope_n_tx,
        primary=primary,
        alternate=alternate,
        truncated=stage1.truncated,
        stage2=stage2,
        proceed_twin=twin_recommended,
    )

    conclusion = build_recommendation_conclusion(
        cv_mape=stage1.satisfaction.cv_mape,
        mape=primary.metrics.mape,
        grade=grade,
        predictive_fit=pred_fit,
        scope_n_tx=analysis_scope.scope_n_tx,
        selection_n=stage1.selection_n,
        fit_n=stage1.fit_n,
        has_twins=has_twins,
        twin_recommended=twin_recommended,
        stage2=stage2,
        excluded_blocks=excluded_blocks,
        adj_r_squared=primary.metrics.adj_r_squared,
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
        twin_ran=bool(stage2 and stage2.ran),
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
