"""모형 추천·비교 API 오케스트레이션."""

from __future__ import annotations

from app.built.regression.selection.best_subset import run_group_best_subset
from app.built.regression.selection.blocks import (
    BlockId,
    block_label,
    candidate_blocks_from_spec,
    spec_from_blocks,
    subset_count,
)
from app.built.regression.selection.context import resolve_selection_context
from app.built.regression.selection.fit import BlockFitResult
from app.built.regression.selection.forward import run_group_forward
from app.built.regression.selection.reasons import build_excluded_reasons
from app.built.schemas import (
    ForwardStepInfo,
    ModelCandidate,
    ModelMetrics,
    RegressionCompareResponse,
    RegressionSelectionRequest,
    RegressionSuggestResponse,
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
    )


def _warnings_for_n(n: int, *, compare: bool = False) -> list[str]:
    out: list[str] = []
    if n < MIN_SELECTION_N:
        out.append(f"표본 n={n} — 신뢰도 낮을 수 있습니다 (권장 n≥{MIN_SELECTION_N}).")
    if compare and n < MIN_SELECTION_N:
        out.append("모형 비교는 표본이 충분할 때 해석하세요.")
    return out


def suggest_regression(conn, req: RegressionSelectionRequest) -> RegressionSuggestResponse:
    ctx = resolve_selection_context(conn, req)
    candidates = _resolve_candidates(req, ctx.unified)
    if not candidates:
        raise ValueError("후보 변수 블록이 없습니다. 변수 체크박스를 선택하세요.")

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

    return RegressionSuggestResponse(
        recommended_blocks=list(forward.selected_blocks),
        recommended_variables=spec,
        response_scale=forward.fit.response_scale,
        model_comparison=forward.model_comparison,
        metrics=_fit_metrics(forward.fit),
        excluded=excluded,
        forward_steps=steps,
        n=forward.fit.n,
        scope_label=ctx.scope_label,
        warnings=_warnings_for_n(forward.fit.n),
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
    )


def compare_regression(conn, req: RegressionSelectionRequest) -> RegressionCompareResponse:
    ctx = resolve_selection_context(conn, req)
    candidates = _resolve_candidates(req, ctx.unified)
    if not candidates:
        raise ValueError("후보 변수 블록이 없습니다. 변수 체크박스를 선택하세요.")

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
    if result.truncated:
        warnings.append(f"조합 {result.total_subsets}개 중 {MAX_COMPARE_SUBSETS}개만 평가했습니다.")

    return RegressionCompareResponse(
        candidates_by_aic=[_candidate_from_compare(c) for c in result.by_aic],
        candidates_by_bic=[_candidate_from_compare(c) for c in result.by_bic],
        candidates_by_mape=[_candidate_from_compare(c) for c in result.by_mape],
        n=n,
        scope_label=ctx.scope_label,
        total_subsets=result.total_subsets,
        truncated=result.truncated,
        warnings=warnings,
    )
