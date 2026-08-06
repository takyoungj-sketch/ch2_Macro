"""dual rank — explanatory vs predictive (R1)."""

from __future__ import annotations

from app.built.regression.selection.best_subset import CompareCandidate
from app.built.regression.selection.blocks import spec_from_blocks
from app.built.regression.selection.service import _fit_metrics
from app.recommendation.coefficients import coefficients_from_block_fit
from app.built.schemas import ModelCandidate, ModelMetrics


def candidate_from_compare(c: CompareCandidate) -> ModelCandidate:
    fit = c.fit
    return ModelCandidate(
        rank=c.rank,
        blocks=list(c.blocks),
        variables=spec_from_blocks(c.blocks),
        response_scale=fit.response_scale,
        metrics=_fit_metrics(fit),
        model_comparison=c.model_comparison,  # type: ignore[arg-type]
        aic=fit.aic,
        bic=fit.bic,
        joint_f_tests=fit.joint_f_tests,
        coefficients=coefficients_from_block_fit(fit),
    )


def pick_primary_predictive(
    by_cv_mape: list[CompareCandidate],
    by_mape: list[CompareCandidate],
    by_aic: list[CompareCandidate],
) -> CompareCandidate | None:
    """예측형 1위 — CV-MAPE → MAPE → AIC 순 fallback."""
    if by_cv_mape:
        return by_cv_mape[0]
    if by_mape:
        return by_mape[0]
    return by_aic[0] if by_aic else None


def pick_alternate_explanatory(by_aic: list[CompareCandidate]) -> CompareCandidate | None:
    return by_aic[0] if by_aic else None
