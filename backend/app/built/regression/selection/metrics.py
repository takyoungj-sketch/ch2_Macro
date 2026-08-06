"""적합 지표 — AIC/BIC/MAPE · linear/log 비교."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from app.built.regression.engine import _duan_smearing, _insample_mape_pct, _uses_log_y
from app.built.schemas import ModelComparison, ModelMetrics, ResponseScale

CV_MIN_N = 25


def _insample_price_pred(model, x_const, scale: ResponseScale) -> np.ndarray:
    fitted = np.asarray(model.fittedvalues, dtype=float)
    if _uses_log_y(scale):
        return np.exp(fitted) * _duan_smearing(model.resid.to_numpy())
    return fitted


def _orig_scale_metrics(
    y_price: np.ndarray, pred: np.ndarray, k_params: int
) -> tuple[float | None, float | None, float | None]:
    mask = np.isfinite(y_price) & np.isfinite(pred) & (y_price != 0)
    if mask.sum() < 2:
        return None, None, None
    y = y_price[mask]
    p = pred[mask]
    ss_res = float(np.sum((y - p) ** 2))
    ss_tot = float(np.sum((y - np.mean(y)) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else None
    n = int(mask.sum())
    adj = None
    if r2 is not None and n > k_params + 1:
        adj = 1.0 - (1.0 - r2) * (n - 1) / (n - k_params - 1)
    mape = float(np.mean(np.abs(y - p) / np.abs(y))) * 100
    rmse = float(np.sqrt(np.mean((y - p) ** 2)))
    return (
        round(adj, 4) if adj is not None else None,
        round(mape, 2),
        round(rmse, 1),
    )


def _confidence_rating(mape: float | None, n: int) -> tuple[int, str]:
    if mape is None:
        return 0, "평가 불가"
    if mape <= 5 and n >= 100:
        return 5, "매우 높음"
    if mape <= 8 and n >= 50:
        return 4, "높음"
    if mape <= 12:
        return 3, "보통"
    if mape <= 20:
        return 2, "낮음"
    return 1, "매우 낮음"


def build_model_comparison(y_price: pd.Series, x_const: pd.DataFrame) -> ModelComparison | None:
    import statsmodels.api as sm

    y = pd.to_numeric(y_price, errors="coerce").astype(float)
    if y.shape[0] < 5 or x_const.empty:
        return None
    k_params = max(x_const.shape[1] - 1, 0)
    n = int(y.shape[0])
    metrics: dict[str, ModelMetrics] = {}

    for mt in ("linear", "log"):
        if mt == "log" and (y <= 0).any():
            continue
        try:
            y_fit = np.log(y) if mt == "log" else y
            model = sm.OLS(y_fit, x_const, missing="drop").fit()
        except Exception:
            continue
        pred = _insample_price_pred(model, x_const, mt)  # type: ignore[arg-type]
        adj, mape, rmse = _orig_scale_metrics(y.to_numpy(), pred, k_params)
        metrics[mt] = ModelMetrics(
            model_type=mt, adj_r_squared=adj, mape=mape, rmse=rmse
        )

    if not metrics:
        return None

    def _mape_of(mt: str) -> float:
        m = metrics.get(mt)
        return m.mape if (m and m.mape is not None) else float("inf")

    if "log" in metrics and "linear" in metrics:
        recommended = "log" if _mape_of("log") <= _mape_of("linear") else "linear"
    else:
        recommended = next(iter(metrics))
    stars, label = _confidence_rating(_mape_of(recommended), n)
    return ModelComparison(
        log=metrics.get("log"),
        linear=metrics.get("linear"),
        recommended=recommended,
        metric_basis="insample",
        confidence_stars=stars,
        confidence_label=label,
    )
