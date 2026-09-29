"""같은 거래 표본에서 변수 블록 × 선형/로그를 탐색한다.

행은 호출자가 넘긴 설계행렬 그대로다. 사용자가 미리 켠 변수로 후보를 자르지 않는다.
"""

from __future__ import annotations

from collections.abc import Callable
from itertools import combinations

import numpy as np
import pandas as pd

MAX_SUBSETS = 511
FULL_CV_LIMIT = 80
PREDICTIVE_SHORTLIST = 12
TOP_K = 3


def iter_block_subsets(fields: list[str]):
    """블록 수가 적은 조합부터. 상한에 걸리면 큰 조합만 빠진다."""
    emitted = 0
    for size in range(1, len(fields) + 1):
        for combo in combinations(fields, size):
            yield list(combo)
            emitted += 1
            if emitted >= MAX_SUBSETS:
                return


def _fit_scales(y: pd.Series, x: pd.DataFrame) -> list[dict]:
    from app.collective.regression.engine import _insample_price_pred, _orig_scale_metrics
    import statsmodels.api as sm

    frame = pd.concat([y.rename("__y"), x], axis=1)
    frame = frame.replace([np.inf, -np.inf], np.nan).dropna()
    if len(frame) < 5:
        return []
    yv = frame["__y"].astype(float)
    xv = sm.add_constant(frame.drop(columns="__y"), has_constant="add")
    k_params = max(xv.shape[1] - 1, 0)
    out: list[dict] = []
    for model_type in ("linear", "log"):
        if model_type == "log" and (yv <= 0).any():
            continue
        y_fit = np.log(yv) if model_type == "log" else yv
        try:
            model = sm.OLS(y_fit, xv, missing="drop").fit()
        except Exception:
            continue
        pred = _insample_price_pred(model, xv, model_type)
        adj, mape, _rmse = _orig_scale_metrics(yv.to_numpy(), pred, k_params)
        if adj is None and mape is None:
            continue
        out.append(
            {
                "model_type": model_type,
                "n": int(model.nobs),
                "adj_r_squared": adj,
                "mape": mape,
                "cv_mape": None,
            }
        )
    return out


def _attach_cv(row: dict, y: pd.Series, x: pd.DataFrame) -> None:
    from app.collective.regression.engine import _cv_price_metrics
    import statsmodels.api as sm

    frame = pd.concat([y.rename("__y"), x], axis=1)
    frame = frame.replace([np.inf, -np.inf], np.nan).dropna()
    if len(frame) < 5:
        return
    yv = frame["__y"].astype(float)
    if row["model_type"] == "log" and (yv <= 0).any():
        return
    xv = sm.add_constant(frame.drop(columns="__y"), has_constant="add")
    cv_mape, _rmse = _cv_price_metrics(yv.to_numpy(), xv.to_numpy(), row["model_type"])
    row["cv_mape"] = cv_mape


def search_block_models(
    pool: list[str],
    build_xy: Callable[[list[str]], tuple[pd.Series, pd.DataFrame] | None],
) -> list[dict]:
    """예측형·설명형 각 상위 후보. blocks 는 요청한 변수 이름이다."""
    if not pool:
        return []
    cache: dict[tuple[str, ...], tuple[pd.Series, pd.DataFrame] | None] = {}

    def xy_for(blocks: list[str]):
        key = tuple(blocks)
        if key not in cache:
            try:
                cache[key] = build_xy(blocks)
            except Exception:
                cache[key] = None
        return cache[key]

    best: dict[tuple, dict] = {}
    for blocks in iter_block_subsets(pool):
        built = xy_for(blocks)
        if built is None:
            continue
        y, x = built
        if x is None or x.empty or len(y) < 5:
            continue
        sig = tuple(sorted(str(col) for col in x.columns))
        if not sig:
            continue
        for row in _fit_scales(y, x):
            row["blocks"] = list(blocks)
            row["sig"] = sig
            key = (sig, row["model_type"])
            prev = best.get(key)
            if prev is not None and len(prev["blocks"]) <= len(blocks):
                continue
            best[key] = row

    rows = list(best.values())
    if not rows:
        return []

    def insample_mape(row: dict) -> float:
        mape = row.get("mape")
        return float(mape) if mape is not None else float("inf")

    def adj_key(row: dict):
        adj = row.get("adj_r_squared")
        return -(float(adj) if adj is not None else float("-inf"))

    by_mape = sorted(rows, key=insample_mape)
    by_adj = sorted(rows, key=adj_key)
    if len(rows) <= FULL_CV_LIMIT:
        cv_rows = rows
    else:
        picked: list[dict] = []
        seen: set[int] = set()
        for row in by_mape[:PREDICTIVE_SHORTLIST] + by_adj[:TOP_K]:
            ident = id(row)
            if ident in seen:
                continue
            seen.add(ident)
            picked.append(row)
        cv_rows = picked
    for row in cv_rows:
        built = xy_for(row["blocks"])
        if built is None:
            continue
        _attach_cv(row, built[0], built[1])

    def pred_key(row: dict):
        cv = row.get("cv_mape")
        mape = insample_mape(row)
        if cv is not None:
            return (0, float(cv), len(row["blocks"]), mape, tuple(row["blocks"]), row["model_type"])
        return (1, mape, len(row["blocks"]), tuple(row["blocks"]), row["model_type"])

    def expl_key(row: dict):
        return (
            adj_key(row),
            insample_mape(row),
            len(row["blocks"]),
            tuple(row["blocks"]),
            row["model_type"],
        )

    out: list[dict] = []
    for purpose, ordered in (
        ("predictive", sorted(rows, key=pred_key)),
        ("explanatory", sorted(rows, key=expl_key)),
    ):
        # 교차검증을 일부만 한 경우, 예측형 순위는 그 후보 안에서만 매긴다.
        pool_rows = ordered
        if purpose == "predictive" and len(rows) > FULL_CV_LIMIT:
            pool_rows = [row for row in ordered if row.get("cv_mape") is not None] or ordered
        for rank, row in enumerate(pool_rows[:TOP_K], start=1):
            out.append(
                {
                    "rank": rank,
                    "purpose": purpose,
                    "blocks": list(row["blocks"]),
                    "model_type": row["model_type"],
                    "n": row["n"],
                    "adj_r_squared": row.get("adj_r_squared"),
                    "mape": row.get("mape"),
                    "cv_mape": row.get("cv_mape"),
                }
            )
    return out
