"""Group Forward — AIC 기준 블록 순차 추가."""

from __future__ import annotations

from dataclasses import dataclass

from app.built.regression.selection.blocks import BlockId, candidate_blocks_from_spec
from app.built.regression.selection.context import SelectionContext, region_col_for_context
from app.built.regression.selection.fit import BlockFitResult, fit_best_scale, fit_block_subset
from app.built.schemas import RegressionRunRequest, ResponseScale


@dataclass
class ForwardStep:
    added: BlockId
    aic_before: float
    aic_after: float


@dataclass
class ForwardResult:
    selected_blocks: list[BlockId]
    fit: BlockFitResult
    model_comparison: object | None
    steps: list[ForwardStep]
    stopped_early: bool
    never_tried: list[BlockId]


def run_group_forward(
    ctx: SelectionContext,
    req: RegressionRunRequest,
) -> ForwardResult | None:
    candidates = candidate_blocks_from_spec(req.variables, unified=ctx.unified)
    if not candidates:
        return None

    region_col = region_col_for_context(ctx, req.variables)
    selected: list[BlockId] = []
    steps: list[ForwardStep] = []
    never_tried: list[BlockId] = []

    current, _cmp = fit_best_scale(
        ctx.df,
        selected,
        unified=ctx.unified,
        region_col=region_col,
        admin_level=ctx.admin_level,
    )
    if current is None:
        return None

    remaining = list(candidates)
    while remaining:
        best_block: BlockId | None = None
        best_fit: BlockFitResult | None = None
        best_aic = current.aic

        for b in remaining:
            trial_blocks = selected + [b]
            trial, _ = fit_best_scale(
                ctx.df,
                trial_blocks,
                unified=ctx.unified,
                region_col=region_col,
                admin_level=ctx.admin_level,
            )
            if trial is None:
                continue
            if trial.aic < best_aic - 1e-9:
                best_aic = trial.aic
                best_block = b
                best_fit = trial

        if best_block is None or best_fit is None:
            never_tried = list(remaining)
            break

        steps.append(
            ForwardStep(
                added=best_block,
                aic_before=current.aic,
                aic_after=best_fit.aic,
            )
        )
        selected.append(best_block)
        remaining.remove(best_block)
        current = best_fit

    _, cmp = fit_best_scale(
        ctx.df,
        selected,
        unified=ctx.unified,
        region_col=region_col,
        admin_level=ctx.admin_level,
    )

    return ForwardResult(
        selected_blocks=selected,
        fit=current,
        model_comparison=cmp,
        steps=steps,
        stopped_early=bool(never_tried),
        never_tried=never_tried,
    )
