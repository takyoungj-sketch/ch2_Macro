"""같은 행으로 7개 모형을 비교한다.

예측 점수는 만원/㎡로 되돌린 MAE·MAPE다. 설명 비교는 log(단가) 식끼리만 한다.
면적 제곱은 학습 평균으로 중심화한 log(면적)이다.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import statsmodels.api as sm

SEED = 20261025
N_SPLITS = 5
ALPHAS = np.logspace(-3, 2, 10)
MAPE_WIN = 1.0


def _finite_mask(*cols: np.ndarray) -> np.ndarray:
    mask = np.ones(len(cols[0]), dtype=bool)
    for col in cols:
        mask &= np.isfinite(col)
    return mask


def _mape(y: np.ndarray, yhat: np.ndarray) -> float | None:
    ok = np.isfinite(y) & np.isfinite(yhat) & (y > 0)
    if int(ok.sum()) < 5:
        return None
    return float(np.mean(np.abs(yhat[ok] - y[ok]) / y[ok]) * 100.0)


def _mae(y: np.ndarray, yhat: np.ndarray) -> float | None:
    ok = np.isfinite(y) & np.isfinite(yhat) & (y > 0)
    if int(ok.sum()) < 5:
        return None
    return float(np.mean(np.abs(yhat[ok] - y[ok])))


def _standardize(train: np.ndarray, test: np.ndarray, cont: int) -> tuple[np.ndarray, np.ndarray]:
    """연속열만 학습 평균·표준편차로 맞춘다. 더미는 0/1로 둔다."""
    tr = train.copy()
    te = test.copy()
    if cont <= 0:
        return tr, te
    mu = tr[:, :cont].mean(axis=0)
    sd = tr[:, :cont].std(axis=0)
    sd[sd < 1e-8] = 1.0
    tr[:, :cont] = (tr[:, :cont] - mu) / sd
    te[:, :cont] = (te[:, :cont] - mu) / sd
    return tr, te


def _folds(n: int, k: int, seed: int) -> list[tuple[np.ndarray, np.ndarray]]:
    idx = np.arange(n)
    rng = np.random.default_rng(seed)
    rng.shuffle(idx)
    out = []
    for i, chunk in enumerate(np.array_split(idx, k)):
        te = chunk
        tr = np.concatenate([c for j, c in enumerate(np.array_split(idx, k)) if j != i])
        if len(tr) < 8 or len(te) < 4:
            continue
        out.append((tr, te))
    return out


def _ols_fit(x: np.ndarray, y: np.ndarray) -> tuple[float, np.ndarray]:
    xa = np.column_stack([np.ones(len(x)), x])
    coef, *_ = np.linalg.lstsq(xa, y, rcond=None)
    return float(coef[0]), np.asarray(coef[1:], dtype=float)


def _predict(intercept: float, coef: np.ndarray, x: np.ndarray) -> np.ndarray:
    return intercept + x @ coef


def _ridge_fit(x: np.ndarray, y: np.ndarray, alpha: float) -> tuple[float, np.ndarray]:
    mu = float(y.mean())
    yc = y - mu
    xtx = x.T @ x
    pen = float(alpha) * np.eye(x.shape[1])
    coef = np.linalg.solve(xtx + pen, x.T @ yc)
    return mu, coef


def _lasso_fit(x: np.ndarray, y: np.ndarray, alpha: float) -> tuple[float, np.ndarray]:
    """절편은 벌점 밖. 계수는 좌표하강."""
    mu = float(y.mean())
    yc = y - mu
    p = x.shape[1]
    coef = np.zeros(p)
    xtx_diag = np.sum(x * x, axis=0)
    xtx_diag[xtx_diag < 1e-12] = 1.0
    for _ in range(80):
        for j in range(p):
            resid = yc - x @ coef + coef[j] * x[:, j]
            rho = float(x[:, j] @ resid)
            coef[j] = np.sign(rho) * max(abs(rho) - alpha, 0.0) / xtx_diag[j]
    return mu, coef


def penalized_fit(kind: str, xtr: np.ndarray, ytr: np.ndarray, xte: np.ndarray) -> tuple[np.ndarray, np.ndarray, float]:
    """강도는 학습 겹 안 3겹 MSE로만 고른다. 반환 계수는 표준화된 열 기준."""
    best_a = float(ALPHAS[0])
    best_score = math.inf
    for alpha in ALPHAS:
        losses: list[float] = []
        for inn_tr, inn_te in _folds(len(ytr), 3, SEED):
            fit = _ridge_fit if kind == "ridge" else _lasso_fit
            intercept, coef = fit(xtr[inn_tr], ytr[inn_tr], float(alpha))
            hat = _predict(intercept, coef, xtr[inn_te])
            losses.append(float(np.mean((hat - ytr[inn_te]) ** 2)))
        score = float(np.mean(losses)) if losses else math.inf
        if score < best_score:
            best_score = score
            best_a = float(alpha)
    fit = _ridge_fit if kind == "ridge" else _lasso_fit
    intercept, coef = fit(xtr, ytr, best_a)
    return _predict(intercept, coef, xte), coef, best_a


def _penalized_predict(kind: str, xtr: np.ndarray, ytr: np.ndarray, xte: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    pred, coef, _alpha = penalized_fit(kind, xtr, ytr, xte)
    return pred, coef


def _pack_cv(maes: list[float], mapes: list[float]) -> dict[str, Any]:
    if not mapes:
        return {"mape": None, "mae": None, "folds": 0}
    return {
        "mape": round(float(np.mean(mapes)), 2),
        "mae": round(float(np.mean(maes)), 2) if maes else None,
        "folds": len(mapes),
    }


def turning_area(beta: float, beta2: float, center: float) -> float | None:
    if not math.isfinite(beta2) or abs(beta2) < 1e-12:
        return None
    c_star = -beta / (2.0 * beta2)
    area = math.exp(c_star + center)
    if not math.isfinite(area) or area <= 0:
        return None
    return float(area)


def fit_cell(
    *,
    y: np.ndarray,
    size: np.ndarray,
    controls: np.ndarray | None,
    n_cont: int,
    p10: float,
    p90: float,
) -> dict[str, Any]:
    """y·size는 양수. controls의 앞 n_cont열은 연속, 나머지는 더미."""
    y = np.asarray(y, dtype=float)
    size = np.asarray(size, dtype=float)
    extra = None
    if controls is not None and np.size(controls):
        extra = np.asarray(controls, dtype=float)
        extra = extra.reshape(len(y), -1) if extra.ndim == 1 else extra
    mask = _finite_mask(y, size)
    if extra is not None:
        mask &= np.isfinite(extra).all(axis=1)
    mask &= (y > 0) & (size > 0)
    y = y[mask]
    size = size[mask]
    extra = extra[mask] if extra is not None else None
    n = int(len(y))
    if n < 30:
        return {"n": n, "status": "n<30"}

    log_y = np.log(y)
    log_s = np.log(size)
    center = float(log_s.mean())
    c = log_s - center
    c2 = c ** 2
    raw_corr = float(np.corrcoef(log_s, log_s ** 2)[0, 1]) if n > 2 else None
    cen_corr = float(np.corrcoef(c, c2)[0, 1]) if n > 2 else None

    def design(parts: list[np.ndarray]) -> np.ndarray:
        blocks = [p.reshape(n, -1) if p.ndim == 1 else p for p in parts]
        if extra is not None:
            blocks.append(extra)
        return np.column_stack(blocks)

    x_lin = design([size])
    x_log = design([c])
    x_quad = design([c, c2])
    cont_lin = 1 + (n_cont if extra is not None else 0)
    cont_log = cont_lin
    cont_quad = cont_lin + 1

    splits = _folds(n, N_SPLITS, SEED)
    buckets: dict[str, list[list[float]]] = {
        k: [[], []] for k in ("linear", "loglog", "quad", "ridge", "lasso", "quad_ridge", "quad_lasso")
    }
    sign_log: list[int] = []
    sign_sq: list[int] = []
    lasso_keep_sq = 0
    lasso_folds = 0

    specs = (
        ("linear", x_lin, y, False, cont_lin, None),
        ("loglog", x_log, log_y, True, cont_log, "log"),
        ("quad", x_quad, log_y, True, cont_quad, "quad"),
        ("ridge", x_log, log_y, True, cont_log, "ridge"),
        ("lasso", x_log, log_y, True, cont_log, "lasso"),
        ("quad_ridge", x_quad, log_y, True, cont_quad, "ridge"),
        ("quad_lasso", x_quad, log_y, True, cont_quad, "lasso"),
    )

    for tr, te in splits:
        for name, x, target, is_log, ncont, kind in specs:
            xtr, xte = x[tr], x[te]
            ytr = target[tr]
            y_orig = y[te]
            try:
                if kind in (None, "log", "quad"):
                    intercept, coef_src = _ols_fit(xtr, ytr)
                    hat = _predict(intercept, coef_src, xte)
                else:
                    xtr_s, xte_s = _standardize(xtr, xte, ncont)
                    hat, coef_src = _penalized_predict(kind, xtr_s, ytr, xte_s)
                if is_log:
                    hat = np.exp(np.clip(hat, -20, 20))
                mae = _mae(y_orig, hat)
                mape = _mape(y_orig, hat)
                if mae is None or mape is None:
                    continue
                buckets[name][0].append(mae)
                buckets[name][1].append(mape)
                if name == "loglog" and len(coef_src):
                    sign_log.append(1 if coef_src[0] > 0 else -1 if coef_src[0] < 0 else 0)
                if name == "quad" and len(coef_src) > 1:
                    sign_sq.append(1 if coef_src[1] > 0 else -1 if coef_src[1] < 0 else 0)
                if name == "quad_lasso" and len(coef_src) > 1:
                    lasso_folds += 1
                    if abs(float(coef_src[1])) > 1e-8:
                        lasso_keep_sq += 1
            except Exception:
                continue

    def sm_fit(x: np.ndarray, target: np.ndarray):
        try:
            return sm.OLS(target, sm.add_constant(x, has_constant="add")).fit()
        except Exception:
            return None

    res_log = sm_fit(x_log, log_y)
    res_quad = sm_fit(x_quad, log_y)

    def coef_pack(res: Any, name: str) -> dict[str, Any]:
        if res is None or name not in res.params.index:
            return {"beta": None, "p": None}
        return {
            "beta": round(float(res.params[name]), 4),
            "p": round(float(res.pvalues[name]), 4),
        }

    # statsmodels names columns x1, x2 when the design has no names.
    def named(res: Any, idx: int) -> dict[str, Any]:
        if res is None or idx >= len(res.params):
            return {"beta": None, "p": None}
        beta = float(np.asarray(res.params)[idx])
        pval = float(np.asarray(res.pvalues)[idx])
        return {"beta": round(beta, 4), "p": round(pval, 4)}

    b1 = named(res_quad, 1)
    b2 = named(res_quad, 2)
    beta = b1["beta"]
    beta2 = b2["beta"]
    area_star = turning_area(beta, beta2, center) if beta is not None and beta2 is not None else None
    in_range = bool(area_star is not None and p10 <= area_star <= p90)
    aic_log = round(float(res_log.aic), 1) if res_log is not None else None
    aic_quad = round(float(res_quad.aic), 1) if res_quad is not None else None
    explain = bool(
        aic_log is not None
        and aic_quad is not None
        and aic_quad <= aic_log - 2
        and b2["p"] is not None
        and b2["p"] < 0.05
        and in_range
    )
    stable = bool(sign_log) and len(set(sign_log)) == 1

    out_models = {name: _pack_cv(mae, mape) for name, (mae, mape) in buckets.items()}
    return {
        "n": n,
        "status": "ok",
        "center_corr": None if cen_corr is None else round(cen_corr, 3),
        "raw_sq_corr": None if raw_corr is None else round(raw_corr, 3),
        "loglog_beta": named(res_log, 1),
        "quad_beta2": b2,
        "turning_area": None if area_star is None else round(area_star, 1),
        "turning_in_range": in_range,
        "aic_log": aic_log,
        "aic_quad": aic_quad,
        "explain_gain": explain,
        "sign_stable": stable,
        "square_sign_stable": bool(sign_sq) and len(set(sign_sq)) == 1,
        "lasso_keeps_square": lasso_keep_sq,
        "lasso_square_folds": lasso_folds,
        "models": out_models,
    }


def summarize(cells: list[dict[str, Any]]) -> dict[str, str]:
    ok = [c for c in cells if c.get("fit", {}).get("status") == "ok"]
    full = [c for c in ok if not c.get("thin")]
    thin = [c for c in ok if c.get("thin")]

    def mape(cell: dict[str, Any], key: str) -> float | None:
        pack = (cell.get("fit") or {}).get("models", {}).get(key) or {}
        val = pack.get("mape")
        return float(val) if val is not None else None

    gained = [c["role_label"] for c in full if c.get("fit", {}).get("explain_gain")]
    if not full:
        explain = "비교할 만큼 표본이 있는 칸이 없다."
    elif not gained:
        explain = "표본이 충분한 칸에서는 2차 항이 관측 면적 안의 규모효과를 log-log보다 더 설명하지 못했다."
    else:
        explain = "2차 항이 관측 면적 안에서 log-log보다 설명을 더한 칸은 " + ", ".join(gained) + "이다."

    wins = []
    for c in full:
        base = mape(c, "loglog")
        best = None
        for key in ("ridge", "lasso", "quad_ridge", "quad_lasso"):
            val = mape(c, key)
            if val is None:
                continue
            best = val if best is None else min(best, val)
        if base is not None and best is not None and best <= base - MAPE_WIN:
            wins.append(c["role_label"])
    if not full:
        predict = "검증 MAPE를 견줄 칸이 없다."
    elif not wins:
        predict = "Ridge·Lasso가 log-log보다 검증 MAPE를 1%p 이상 낮춘 칸은 없다."
    else:
        predict = (
            f"수축 모형이 log-log보다 검증 MAPE를 1%p 이상 낮춘 칸은 {len(full)}곳 중 {len(wins)}곳"
            f"({', '.join(wins)})이다."
        )
        if len(wins) < max(1, (len(full) + 1) // 2):
            predict += " 과반이 아니라 일관된 우위로 두지 않는다."

    thin_win = False
    for c in thin:
        base = mape(c, "loglog")
        best = min((mape(c, k) for k in ("ridge", "lasso") if mape(c, k) is not None), default=None)
        if base is not None and best is not None and best <= base - MAPE_WIN:
            thin_win = True
    if thin_win and len(wins) == 0:
        recommend = "수축이 이긴 곳은 표본이 얇은 칸뿐이다. 표본 수로 모형을 고르는 규칙은 아직 두지 않는다."
    elif len(wins) >= max(3, len(full) - 1) and len(full) >= 3:
        recommend = "수축이 여러 유형에서 반복됐다. 그래도 이번 칸만으로 제품 모형추천 규칙으로 두지 않는다."
    else:
        recommend = "다섯 유형에서 같은 방향이 반복되지 않아, 표본 수나 공선성으로 모형을 고르는 규칙은 두지 않는다."
    return {"explain": explain, "predict": predict, "recommend": recommend}
