"""BlockFitResult → RegressionCoeff (R4)."""

from __future__ import annotations

from app.built.regression.selection.fit import BlockFitResult
from app.built.schemas import RegressionCoeff


def coefficients_from_block_fit(fit: BlockFitResult) -> list[RegressionCoeff]:
    model = fit.model
    if model is None or not hasattr(model, "params"):
        return []
    out: list[RegressionCoeff] = []
    for name in model.params.index:
        if str(name) == "const":
            continue
        out.append(
            RegressionCoeff(
                name=str(name),
                estimate=float(model.params[name]),
                std_err=float(model.bse[name]) if name in model.bse else None,
                t_value=float(model.tvalues[name]) if name in model.tvalues else None,
                p_value=float(model.pvalues[name]) if name in model.pvalues else None,
            )
        )
    return out
