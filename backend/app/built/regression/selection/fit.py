"""블록 subset OLS 적합."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from app.built.regression.engine import _build_design_matrix, _insample_mape_pct
from app.built.regression.selection.blocks import BlockId, spec_from_blocks
from app.built.schemas import RegressionVariableSpec, ResponseScale


@dataclass
class BlockFitResult:
    blocks: list[BlockId]
    variables: RegressionVariableSpec
    response_scale: ResponseScale
    n: int
    n_params: int
    aic: float
    bic: float
    adj_r_squared: float | None
    mape: float | None
    model: object
    x_const: pd.DataFrame
    y_price: np.ndarray


def fit_block_subset(
    df: pd.DataFrame,
    blocks: list[BlockId] | list[str],
    *,
    unified: bool,
    response_scale: ResponseScale,
    region_col: str | None,
    admin_level: str,
) -> BlockFitResult | None:
    import statsmodels.api as sm

    spec = spec_from_blocks(blocks)
    y_raw = pd.to_numeric(df["price"], errors="coerce")
    region_col_use = region_col if spec.region_leaf_dummy and admin_level == "eupmyeondong" else None

    y, X, _meta = _build_design_matrix(
        df,
        spec,
        unified=unified,
        response_scale=response_scale,
        region_col=region_col_use,
    )
    if y_raw.notna().sum() < 5:
        return None

    mask = y_raw.notna()
    y_price = y_raw.loc[mask].astype(float).to_numpy()

    if X.empty:
        y_fit = y_price.copy()
        if response_scale == "log":
            if (y_fit <= 0).any():
                return None
            y_fit = np.log(y_fit)
        x_const = pd.DataFrame({"const": np.ones(len(y_fit))})
        try:
            model = sm.OLS(y_fit, x_const).fit()
        except Exception:
            return None
    else:
        if len(y) < max(5, X.shape[1] + 1):
            return None
        y_fit = y.astype(float)
        x_const = sm.add_constant(X.astype(float), has_constant="add")
        try:
            model = sm.OLS(y_fit, x_const).fit()
        except Exception:
            return None
        y_price = pd.to_numeric(df["price"], errors="coerce").loc[y.index].astype(float).to_numpy()

    mape = _insample_mape_pct(y_price, model, response_scale=response_scale)
    return BlockFitResult(
        blocks=list(blocks),
        variables=spec,
        response_scale=response_scale,
        n=int(model.nobs),
        n_params=int(len(model.params)),
        aic=float(model.aic),
        bic=float(model.bic),
        adj_r_squared=float(model.rsquared_adj) if model.rsquared_adj is not None else None,
        mape=mape,
        model=model,
        x_const=x_const,
        y_price=y_price,
    )


def fit_best_scale(
    df: pd.DataFrame,
    blocks: list[BlockId] | list[str],
    *,
    unified: bool,
    region_col: str | None,
    admin_level: str,
) -> tuple[BlockFitResult | None, object | None]:
    """linear·log 중 AIC 최소 scale 선택 + ModelComparison."""
    from app.built.regression.selection.metrics import build_model_comparison

    fits: dict[str, BlockFitResult] = {}
    for scale in ("linear", "log"):
        r = fit_block_subset(
            df,
            blocks,
            unified=unified,
            response_scale=scale,  # type: ignore[arg-type]
            region_col=region_col,
            admin_level=admin_level,
        )
        if r is not None:
            fits[scale] = r
    if not fits:
        return None, None
    best = min(fits.values(), key=lambda r: r.aic)
    cmp = None
    if best.x_const is not None and len(best.x_const):
        y_s = pd.Series(best.y_price)
        cmp = build_model_comparison(y_s, best.x_const)
    return best, cmp
