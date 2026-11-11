"""Group Best Subset — 2^k 블록 조합 랭킹."""

from __future__ import annotations

from dataclasses import dataclass

from app.built.regression.selection.blocks import BlockId, enumerate_block_subsets
from app.built.regression.selection.context import SelectionContext, region_col_for_context
from app.built.regression.selection.fit import (
    BlockFitResult,
    attach_joint_f_tests,
    common_scale_frame,
    fit_scale_candidates,
    pick_explanatory_scale,
    pick_predictive_scale,
    search_evaluation_complete,
)
from app.built.regression.selection.metrics import build_model_comparison_from_fits
from app.built.schemas import RegressionRunRequest

# 제품 SSOT 풀은 최대 9블록(기본 7 + 유형 + 지역) = 511 조합이라 자르지 않는다.
# 랩의 지역 공변량 풀처럼 더 넓을 때만 잘리고, 그때는 블록 수가 작은 조합이 남는다.
MAX_SUBSETS = 511
TOP_K = 5


@dataclass
class CompareCandidate:
    rank: int
    blocks: list[BlockId]
    fit: BlockFitResult
    model_comparison: object | None


@dataclass
class CompareResult:
    by_aic: list[CompareCandidate]
    by_bic: list[CompareCandidate]
    by_mape: list[CompareCandidate]
    by_cv_mape: list[CompareCandidate]
    total_subsets: int
    truncated: bool
    # R-1: 탐색 CV를 끝까지 채점한 후보가 없을 때만 쓴다. 평가 서명이 같은 부분 CV
    # 후보끼리만 순위를 낸다 (서명이 다르면 채점 거래가 달라 비교할 수 없다).
    by_partial_cv: list[CompareCandidate] | None = None
    partial_cv_years: tuple[int, ...] = ()


def _rank_partial_cv(
    scored: list[tuple[list[BlockId], BlockFitResult, object | None]],
) -> tuple[list[CompareCandidate], tuple[int, ...]]:
    """부분 완료 탐색 CV 후보를 같은 evaluation_signature 그룹 안에서만 순위 짓는다.

    여러 서명이 있으면 후보가 가장 많은 그룹(동률이면 채점 거래가 많은 쪽)을 쓴다.
    """
    groups: dict[str, list[tuple[list[BlockId], BlockFitResult, object | None]]] = {}
    for blocks, fit, cmp in scored:
        phase = fit.cv_search
        if phase.mape is None or not phase.evaluation_signature:
            continue
        if search_evaluation_complete(phase):
            continue
        groups.setdefault(phase.evaluation_signature, []).append((blocks, fit, cmp))
    if not groups:
        return [], ()
    best = max(
        groups.values(),
        key=lambda rows: (len(rows), max(r[1].cv_search.n_trades for r in rows)),
    )
    best.sort(key=lambda x: float(x[1].cv_search.mape))  # type: ignore[arg-type]
    years = tuple(best[0][1].cv_search.years)
    out = [
        CompareCandidate(rank=i + 1, blocks=b, fit=f, model_comparison=c)
        for i, (b, f, c) in enumerate(best[:TOP_K])
    ]
    return out, years


def _rank_candidates(
    scored: list[tuple[list[BlockId], BlockFitResult, object | None]],
    key: str,
) -> list[CompareCandidate]:
    if key == "mape":
        valid = [(b, f, c) for b, f, c in scored if f.mape is not None]
        valid.sort(key=lambda x: x[1].mape)  # type: ignore[arg-type]
    elif key == "cv_mape":
        valid = [(b, f, c) for b, f, c in scored if search_evaluation_complete(f.cv_search)]
        valid.sort(key=lambda x: x[1].cv_mape)  # type: ignore[arg-type]
    elif key == "bic":
        valid = sorted(scored, key=lambda x: x[1].bic)
    else:
        valid = sorted(scored, key=lambda x: x[1].aic)
    out: list[CompareCandidate] = []
    for i, (blocks, fit, cmp) in enumerate(valid[:TOP_K]):
        out.append(CompareCandidate(rank=i + 1, blocks=blocks, fit=fit, model_comparison=cmp))
    return out


def run_group_best_subset(
    ctx: SelectionContext,
    req: RegressionRunRequest,
    candidates: list[BlockId],
    *,
    eligible=None,
) -> CompareResult | None:
    if not candidates:
        return None

    region_col = region_col_for_context(ctx, req.variables)
    from app.built.regression.selection.blocks import subset_count

    total = subset_count(candidates)
    truncated = total > MAX_SUBSETS
    subsets = enumerate_block_subsets(candidates, max_count=MAX_SUBSETS)

    scored_pred: list[tuple[list[BlockId], BlockFitResult, object | None]] = []
    scored_expl: list[tuple[list[BlockId], BlockFitResult, object | None]] = []
    for blocks in subsets:
        fits = fit_scale_candidates(
            ctx.df,
            blocks,
            unified=ctx.unified,
            region_col=region_col,
            admin_level=ctx.admin_level,
            time_adjuster=ctx.time_adjuster,
        )
        if not fits:
            continue
        pred = pick_predictive_scale(fits)
        cmp = build_model_comparison_from_fits(fits, recommended=pred.response_scale)
        if eligible is None or eligible(pred):
            scored_pred.append((blocks, pred, cmp))
        expl = pick_explanatory_scale(fits)
        if expl is None:
            continue
        if expl.response_scale == pred.response_scale:
            expl = pred
        if eligible is not None and not eligible(expl):
            continue
        scored_expl.append((blocks, expl, cmp))

    if not scored_pred:
        return None

    result = CompareResult(
        by_aic=_rank_candidates(scored_expl, "aic"),
        by_bic=_rank_candidates(scored_expl, "bic"),
        by_mape=_rank_candidates(scored_pred, "mape"),
        by_cv_mape=_rank_candidates(scored_pred, "cv_mape"),
        total_subsets=total,
        truncated=truncated,
    )
    if not result.by_cv_mape:
        result.by_partial_cv, result.partial_cv_years = _rank_partial_cv(scored_pred)
    _attach_joint_f_to_ranked(ctx, result, region_col=region_col)
    return result


def _attach_joint_f_to_ranked(
    ctx: SelectionContext,
    result: CompareResult,
    *,
    region_col: str | None,
) -> None:
    """랭킹에 오른 후보만 Joint F를 붙인다 — 순위 산정에는 쓰이지 않는다."""
    done: set[tuple[tuple[BlockId, ...], str]] = set()
    for ranking in (
        result.by_cv_mape, result.by_partial_cv or [], result.by_mape, result.by_aic, result.by_bic
    ):
        for candidate in ranking:
            key = (tuple(candidate.blocks), candidate.fit.response_scale)
            if key in done:
                continue
            done.add(key)
            attach_joint_f_tests(
                common_scale_frame(ctx.df, candidate.blocks),
                candidate.fit,
                unified=ctx.unified,
                region_col=region_col,
                admin_level=ctx.admin_level,
                time_adjuster=ctx.time_adjuster,
            )
