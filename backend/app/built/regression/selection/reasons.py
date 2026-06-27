"""제외 블록 사유 — p_value · AIC · adj_r2 · MAPE · forward_stop."""

from __future__ import annotations

from app.built.regression.selection.blocks import BlockId, block_label
from app.built.regression.selection.context import SelectionContext, region_col_for_context
from app.built.regression.selection.fit import fit_block_subset
from app.built.regression.selection.forward import ForwardResult
from app.built.schemas import ExcludedBlock, ExcludedBlockReason, RegressionRunRequest


def _p_value_reason(model, block: BlockId) -> ExcludedBlockReason | None:
    """블록 관련 계수 p-value."""
    params = getattr(model, "params", None)
    pvals = getattr(model, "pvalues", None)
    if params is None or pvals is None:
        return None
    prefixes = {
        "gross_area": ("gross_area",),
        "land_area": ("land_area",),
        "building_age": ("building_age",),
        "road_width": ("road_",),
        "zone_type": ("zone_",),
        "building_use": ("use_",),
        "asset_type": ("atype_",),
        "region_leaf": ("loc_",),
    }
    keys = prefixes.get(block, ())
    related = [str(k) for k in params.index if any(str(k).startswith(p) for p in keys)]
    if not related:
        return None
    max_p = max(float(pvals[k]) for k in related if k in pvals.index)
    if max_p <= 0.05:
        return None
    return ExcludedBlockReason(
        code="p_value",
        message=f"블록 '{block}' 계수 p-value 최대 {max_p:.3f} (> 0.05)",
        metric_value=round(max_p, 4),
    )


def build_excluded_reasons(
    ctx: SelectionContext,
    req: RegressionRunRequest,
    forward: ForwardResult,
    all_candidates: list[BlockId],
) -> list[ExcludedBlock]:
    selected = set(forward.selected_blocks)
    excluded_ids = [b for b in all_candidates if b not in selected]
    region_col = region_col_for_context(ctx, req.variables)
    base = forward.fit

    out: list[ExcludedBlock] = []
    for b in excluded_ids:
        reasons: list[ExcludedBlockReason] = []

        if b in forward.never_tried:
            reasons.append(
                ExcludedBlockReason(
                    code="forward_stop",
                    message="Forward 단계에서 AIC 개선 없어 탐색 중단 후 미평가",
                )
            )
        else:
            trial = fit_block_subset(
                ctx.df,
                list(selected) + [b],
                unified=ctx.unified,
                response_scale=base.response_scale,
                region_col=region_col,
                admin_level=ctx.admin_level,
            )
            if trial is not None:
                delta_aic = trial.aic - base.aic
                if delta_aic >= 0:
                    reasons.append(
                        ExcludedBlockReason(
                            code="aic",
                            message=f"AIC 증가 (+{delta_aic:.1f}) — 포함 시 적합도 악화",
                            metric_value=round(delta_aic, 2),
                        )
                    )
                if trial.adj_r_squared is not None and base.adj_r_squared is not None:
                    delta_adj = trial.adj_r_squared - base.adj_r_squared
                    if delta_adj < 0.001:
                        reasons.append(
                            ExcludedBlockReason(
                                code="adj_r2",
                                message=f"조정 R² 개선 미미 ({delta_adj:+.4f})",
                                metric_value=round(delta_adj, 4),
                            )
                        )
                if trial.mape is not None and base.mape is not None:
                    delta_mape = base.mape - trial.mape
                    if delta_mape < 0.1:
                        reasons.append(
                            ExcludedBlockReason(
                                code="mape",
                                message=f"MAPE 개선 미미 ({delta_mape:+.2f}%p)",
                                metric_value=round(delta_mape, 2),
                            )
                        )
                if trial.model is not None:
                    pr = _p_value_reason(trial.model, b)
                    if pr:
                        reasons.append(pr)

        if not reasons:
            reasons.append(
                ExcludedBlockReason(
                    code="forward_stop",
                    message="다른 블록이 동일 단계에서 더 큰 AIC 개선",
                )
            )
        out.append(ExcludedBlock(block_id=b, label=block_label(b), reasons=reasons))
    return out
