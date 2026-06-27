"""Group Best Subset — 2^k 블록 조합 랭킹."""

from __future__ import annotations

from dataclasses import dataclass

from app.built.regression.selection.blocks import BlockId, enumerate_block_subsets
from app.built.regression.selection.context import SelectionContext, region_col_for_context
from app.built.regression.selection.fit import BlockFitResult, fit_best_scale
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
    total_subsets: int
    truncated: bool


def _rank_candidates(
    scored: list[tuple[list[BlockId], BlockFitResult, object | None]],
    key: str,
) -> list[CompareCandidate]:
    if key == "mape":
        valid = [(b, f, c) for b, f, c in scored if f.mape is not None]
        valid.sort(key=lambda x: x[1].mape)  # type: ignore[arg-type]
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

    scored: list[tuple[list[BlockId], BlockFitResult, object | None]] = []
    for blocks in subsets:
        fit, cmp = fit_best_scale(
            ctx.df,
            blocks,
            unified=ctx.unified,
            region_col=region_col,
            admin_level=ctx.admin_level,
        )
        if fit is not None:
            scored.append((blocks, fit, cmp))

    if not scored:
        return None

    return CompareResult(
        by_aic=_rank_candidates(scored, "aic"),
        by_bic=_rank_candidates(scored, "bic"),
        by_mape=_rank_candidates(scored, "mape"),
        total_subsets=len(subsets),
        truncated=truncated,
    )
