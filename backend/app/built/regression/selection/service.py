"""모형 추천·비교 API 오케스트레이션."""

from __future__ import annotations

from dataclasses import dataclass

from app.built.regression.selection.best_subset import run_group_best_subset
from app.built.regression.candidates import (
    CandidateContext,
    CandidateSpec,
    LocalCandidateProvider,
    ProfileTwinCandidateProvider,
    generate_candidates,
    region_counts_from_db,
)
from app.built.regression.selection.blocks import (
    BlockId,
    block_label,
    candidate_blocks_from_spec,
    spec_from_blocks,
    subset_count,
)
from app.built.regression.selection.context import (
    region_col_for_context,
    resolve_selection_context,
    with_complete_case,
)
from app.built.regression.selection.fit import BlockFitResult
from app.built.regression.selection.forward import run_group_forward
from app.built.regression.selection.pooling import (
    accepted_twin_region_codes,
    evaluate_pooling_candidates,
)
from app.built.regression.selection.reasons import build_excluded_reasons
from app.built.schemas import (
    ForwardStepInfo,
    ModelCandidate,
    ModelMetrics,
    PoolingEvaluation,
    RegressionCompareResponse,
    RegressionSelectionRequest,
    RegressionSuggestResponse,
    CandidateValidationSummary,
)

MIN_SELECTION_N = 30
MAX_COMPARE_SUBSETS = 128


def _resolve_candidates(req: RegressionSelectionRequest, unified: bool) -> list[BlockId]:
    if req.candidate_blocks:
        return list(req.candidate_blocks)  # type: ignore[list-item]
    return candidate_blocks_from_spec(req.variables, unified=unified)


def _fit_metrics(fit: BlockFitResult) -> ModelMetrics:
    return ModelMetrics(
        model_type=fit.response_scale,
        adj_r_squared=fit.adj_r_squared,
        mape=fit.mape,
        cv_mape=fit.cv_mape,
        cv_folds=fit.cv_folds,
        cv_method="rolling_time" if fit.cv_folds else None,
    )


def _warnings_for_n(n: int, *, compare: bool = False) -> list[str]:
    out: list[str] = []
    if n < MIN_SELECTION_N:
        out.append(f"표본 n={n} — 신뢰도 낮을 수 있습니다 (권장 n≥{MIN_SELECTION_N}).")
    if compare and n < MIN_SELECTION_N:
        out.append("모형 비교는 표본이 충분할 때 해석하세요.")
    return out


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


@dataclass(frozen=True)
class _CandidateValidationResult:
    summaries: list[CandidateValidationSummary]
    accepted: tuple[CandidateSpec, ...]
    anchor_codes: tuple[str, ...]


def _candidate_validations(
    conn, ctx, req: RegressionSelectionRequest, candidates: list[BlockId]
) -> _CandidateValidationResult:
    """anchor + Twin 등 모든 후보 지역을 원장에서 별도 조회해 검증한다.

    ctx.df는 이미 anchor 지역으로 좁혀진 표본이라 Twin 후보 지역의 건수를
    셀 수 없다 (항상 0건으로 나와 region_coverage가 항상 실패한다).
    따라서 후보가 실제로 제안하는 지역 코드 전체에 대해 built 원장을
    별도 조회한다.
    """
    code_column = {
        "sigungu": "sigungu_code",
        "gu": "sigungu_code",
        "eupmyeondong": "eupmyeondong_code",
        "beopjungri": "beopjungri_code",
    }.get(ctx.admin_level)
    anchor_codes = tuple(
        str(code).strip()
        for code in (req.region_codes or [])
        if str(code).strip()
    )
    if not anchor_codes and code_column and code_column in ctx.df.columns:
        anchor_codes = tuple(
            str(code).strip()
            for code in ctx.df[code_column].dropna().unique()
            if str(code).strip()
        )
    context = CandidateContext(
        admin_level=ctx.admin_level,
        anchor_region_codes=anchor_codes,
        profile_version=req.profile_version,
        profile_as_of_month=req.profile_as_of_month,
        profile_window_years=req.profile_window_years,
    )
    providers = [LocalCandidateProvider(candidates)]
    if req.profile_twin_neighbors:
        providers.append(
            ProfileTwinCandidateProvider(req.profile_twin_neighbors, candidates)
        )

    all_region_codes: set[str] = set(anchor_codes)
    for provider in providers:
        for spec in provider.generate(context):
            all_region_codes.update(spec.region_codes)

    region_counts = region_counts_from_db(
        conn,
        admin_level=ctx.admin_level,
        region_codes=tuple(all_region_codes),
        asset_type=req.asset_type,
        contract_year_from=req.contract_year_from,
        contract_year_to=req.contract_year_to,
        as_of_month=req.as_of_month,
        window_years=req.window_years,
    )
    result = generate_candidates(
        providers,
        context=context,
        region_counts=region_counts,
    )
    return _CandidateValidationResult(
        summaries=[
            CandidateValidationSummary(
                candidate_id=item.candidate_id,
                accepted=item.accepted,
                checks=item.checks,
                reasons=list(item.reasons),
                warnings=list(item.warnings),
            )
            for item in result.validations
        ],
        accepted=result.accepted,
        anchor_codes=anchor_codes,
    )


def suggest_regression(conn, req: RegressionSelectionRequest) -> RegressionSuggestResponse:
    ctx = resolve_selection_context(conn, req)
    candidates = _resolve_candidates(req, ctx.unified)
    if not candidates:
        raise ValueError("후보 변수 블록이 없습니다. 변수 체크박스를 선택하세요.")
    ctx = with_complete_case(
        ctx,
        candidates,
        region_col=region_col_for_context(ctx, req.variables),
    )
    candidate_result = _candidate_validations(conn, ctx, req, candidates)

    forward = run_group_forward(ctx, req)
    if forward is None:
        raise ValueError("추천 모형을 적합할 수 없습니다. 표본·변수를 확인하세요.")

    spec = spec_from_blocks(forward.selected_blocks)
    excluded = build_excluded_reasons(ctx, req, forward, candidates)
    steps = [
        ForwardStepInfo(
            added_block=s.added,
            block_label=block_label(s.added),
            aic_before=s.aic_before,
            aic_after=s.aic_after,
        )
        for s in forward.steps
    ]

    pooling_evaluation = evaluate_pooling_candidates(
        conn,
        local_ctx=ctx,
        req=req,
        blocks=forward.selected_blocks,
        local_fit=forward.fit,
        anchor_region_codes=candidate_result.anchor_codes,
        twin_region_codes=accepted_twin_region_codes(
            candidate_result.accepted, candidate_result.anchor_codes
        ),
        admin_level=ctx.admin_level,
        region_col=region_col_for_context(ctx, req.variables),
    )

    return RegressionSuggestResponse(
        recommended_blocks=list(forward.selected_blocks),
        recommended_variables=spec,
        response_scale=forward.fit.response_scale,
        model_comparison=forward.model_comparison,
        metrics=_fit_metrics(forward.fit),
        excluded=excluded,
        forward_steps=steps,
        n=forward.fit.n,
        selection_n=ctx.selection_n,
        candidate_union_variables=list(ctx.sample_columns),
        validation_contract_version="v1-complete-case",
        joint_f_tests=forward.fit.joint_f_tests,
        candidate_validations=candidate_result.summaries,
        pooling_evaluation=pooling_evaluation,
        scope_label=ctx.scope_label,
        warnings=_warnings_for_n(forward.fit.n)
        + _warnings_for_cv_mape(forward.fit.cv_mape),
    )


def _candidate_from_compare(c) -> ModelCandidate:
    fit = c.fit
    return ModelCandidate(
        rank=c.rank,
        blocks=list(c.blocks),
        variables=spec_from_blocks(c.blocks),
        response_scale=fit.response_scale,
        metrics=_fit_metrics(fit),
        model_comparison=c.model_comparison,
        aic=fit.aic,
        bic=fit.bic,
        joint_f_tests=fit.joint_f_tests,
    )


def compare_regression(conn, req: RegressionSelectionRequest) -> RegressionCompareResponse:
    ctx = resolve_selection_context(conn, req)
    candidates = _resolve_candidates(req, ctx.unified)
    if not candidates:
        raise ValueError("후보 변수 블록이 없습니다. 변수 체크박스를 선택하세요.")
    ctx = with_complete_case(
        ctx,
        candidates,
        region_col=region_col_for_context(ctx, req.variables),
    )
    candidate_result = _candidate_validations(conn, ctx, req, candidates)

    total = subset_count(candidates)
    if total > MAX_COMPARE_SUBSETS:
        raise ValueError(
            f"후보 블록 {len(candidates)}개 → {total}개 조합 (상한 {MAX_COMPARE_SUBSETS}). "
            "후보 변수를 줄이세요."
        )

    result = run_group_best_subset(ctx, req, candidates)
    if result is None:
        raise ValueError("모형 비교를 적합할 수 없습니다. 표본·변수를 확인하세요.")

    n = result.by_aic[0].fit.n if result.by_aic else 0
    warnings = _warnings_for_n(n, compare=True)
    if result.by_cv_mape:
        warnings.extend(_warnings_for_cv_mape(result.by_cv_mape[0].fit.cv_mape))
    if result.truncated:
        warnings.append(f"조합 {result.total_subsets}개 중 {MAX_COMPARE_SUBSETS}개만 평가했습니다.")

    # 예측형 1차 지표(CV-MAPE) 상위 후보를 기준으로 Local vs Twin Pooling을 비교한다.
    # CV-MAPE 랭킹이 비어 있으면(fold 부족 등) AIC 상위 후보로 대체한다.
    top_candidate = (result.by_cv_mape or result.by_aic)[0] if (result.by_cv_mape or result.by_aic) else None
    pooling_evaluation: PoolingEvaluation | None = None
    if top_candidate is not None:
        pooling_evaluation = evaluate_pooling_candidates(
            conn,
            local_ctx=ctx,
            req=req,
            blocks=top_candidate.blocks,
            local_fit=top_candidate.fit,
            anchor_region_codes=candidate_result.anchor_codes,
            twin_region_codes=accepted_twin_region_codes(
                candidate_result.accepted, candidate_result.anchor_codes
            ),
            admin_level=ctx.admin_level,
            region_col=region_col_for_context(ctx, req.variables),
        )

    return RegressionCompareResponse(
        candidates_by_aic=[_candidate_from_compare(c) for c in result.by_aic],
        candidates_by_bic=[_candidate_from_compare(c) for c in result.by_bic],
        candidates_by_mape=[_candidate_from_compare(c) for c in result.by_mape],
        candidates_by_cv_mape=[_candidate_from_compare(c) for c in result.by_cv_mape],
        n=n,
        selection_n=ctx.selection_n,
        candidate_union_variables=list(ctx.sample_columns),
        validation_contract_version="v1-complete-case",
        candidate_validations=candidate_result.summaries,
        pooling_evaluation=pooling_evaluation,
        scope_label=ctx.scope_label,
        total_subsets=result.total_subsets,
        truncated=result.truncated,
        warnings=warnings,
    )
