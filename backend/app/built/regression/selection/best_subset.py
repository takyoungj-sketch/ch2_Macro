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
)
from app.built.regression.selection.metrics import build_model_comparison_from_fits
from app.built.schemas import RegressionRunRequest

MAX_SUBSETS = 128
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


def _rank_candidates(
    scored: list[tuple[list[BlockId], BlockFitResult, object | None]],
    key: str,
) -> list[CompareCandidate]:
    if key == "mape":
        valid = [(b, f, c) for b, f, c in scored if f.mape is not None]
        valid.sort(key=lambda x: x[1].mape)  # type: ignore[arg-type]
    elif key == "cv_mape":
        valid = [(b, f, c) for b, f, c in scored if f.cv_mape is not None]
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
        )
        if not fits:
            continue
        pred = pick_predictive_scale(fits)
        df_cmp = common_scale_frame(ctx.df, blocks)
        pred = attach_joint_f_tests(
            df_cmp,
            pred,
            unified=ctx.unified,
            region_col=region_col,
            admin_level=ctx.admin_level,
        )
        cmp = build_model_comparison_from_fits(fits, recommended=pred.response_scale)
        scored_pred.append((blocks, pred, cmp))
        expl = pick_explanatory_scale(fits)
        if expl is None:
            continue
        if expl.response_scale != pred.response_scale:
            expl = attach_joint_f_tests(
                df_cmp,
                expl,
                unified=ctx.unified,
                region_col=region_col,
                admin_level=ctx.admin_level,
            )
        else:
            expl = pred
        scored_expl.append((blocks, expl, cmp))

    if not scored_pred:
        return None

    return CompareResult(
        by_aic=_rank_candidates(scored_expl, "aic"),
        by_bic=_rank_candidates(scored_expl, "bic"),
        by_mape=_rank_candidates(scored_pred, "mape"),
        by_cv_mape=_rank_candidates(scored_pred, "cv_mape"),
        total_subsets=len(subsets),
        truncated=truncated,
    )
