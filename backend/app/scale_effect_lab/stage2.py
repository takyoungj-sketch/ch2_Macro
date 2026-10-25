"""규모효과 2단계. 1단계가 고른 네 칸만 다시 읽는다.

1단계 JSON은 쓰지 않는다. 제품 회귀 식도 읽기만 한다.
"""

from __future__ import annotations

import json
import math
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import statsmodels.api as sm

from app.scale_effect_lab.fit import (
    ALPHAS,
    N_SPLITS,
    SEED,
    _folds,
    _mae,
    _mape,
    _ols_fit,
    _predict,
    _standardize,
    penalized_fit,
    turning_area,
)
from app.scale_effect_lab.run import (
    _collapse,
    _cols,
    _load_rows,
    _prefix_bounds,
    _window,
    _zone_group,
)

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "docs" / "lab" / "scale_effect_stage2.json"
BAND = 1.2


def _r(v: float | None, nd: int = 2) -> float | None:
    if v is None or not math.isfinite(float(v)):
        return None
    return round(float(v), nd)


def _corr(a: np.ndarray, b: np.ndarray) -> float | None:
    if len(a) < 3:
        return None
    val = float(np.corrcoef(a, b)[0, 1])
    return None if not math.isfinite(val) else val


def _vif(target: np.ndarray, others: np.ndarray) -> float | None:
    if len(target) < 8:
        return None
    xa = np.column_stack([np.ones(len(target)), others]) if others.size else np.ones((len(target), 1))
    coef, *_ = np.linalg.lstsq(xa, target, rcond=None)
    hat = xa @ coef
    resid = float(np.sum((target - hat) ** 2))
    tot = float(np.sum((target - target.mean()) ** 2))
    if tot < 1e-12:
        return None
    r2 = 1.0 - resid / tot
    if r2 >= 0.999:
        return 999.0
    return 1.0 / (1.0 - r2)


def _sm(x: np.ndarray, y: np.ndarray):
    try:
        return sm.OLS(y, sm.add_constant(x, has_constant="add")).fit()
    except Exception:
        return None


def _coef(res: Any, idx: int) -> dict[str, float | None]:
    if res is None or idx >= len(res.params):
        return {"beta": None, "p": None}
    return {"beta": _r(float(np.asarray(res.params)[idx]), 4), "p": _r(float(np.asarray(res.pvalues)[idx]), 4)}


def _extremum(beta2: float | None) -> str | None:
    if beta2 is None or not math.isfinite(beta2) or abs(beta2) < 1e-12:
        return None
    return "극솟값" if beta2 > 0 else "극댓값"


def _prepare(df: pd.DataFrame, cont: list[str], dummies: np.ndarray) -> dict[str, Any] | None:
    if df.empty:
        return None
    unit = pd.to_numeric(df["y"], errors="coerce").to_numpy(dtype=float)
    size = pd.to_numeric(df["size"], errors="coerce").to_numpy(dtype=float)
    blocks: list[np.ndarray] = []
    n_cont = 0
    for col in cont:
        if col not in df:
            continue
        val = pd.to_numeric(df[col], errors="coerce")
        med = float(val.median()) if val.notna().any() else 0.0
        blocks.append((val.fillna(med) - med).to_numpy(dtype=float))
        n_cont += 1
    if dummies.size:
        blocks.append(dummies)
    extra = np.column_stack(blocks) if blocks else None
    mask = np.isfinite(unit) & np.isfinite(size) & (unit > 0) & (size > 0)
    if extra is not None:
        mask &= np.isfinite(extra).all(axis=1)
    unit = unit[mask]
    size = size[mask]
    extra = extra[mask] if extra is not None else None
    if len(unit) < 30:
        return None
    return {"unit": unit, "size": size, "extra": extra, "n_cont": n_cont}


def _design(parts: list[np.ndarray], extra: np.ndarray | None) -> np.ndarray:
    blocks = [p.reshape(len(p), -1) if p.ndim == 1 else p for p in parts]
    if extra is not None:
        blocks.append(extra)
    return np.column_stack(blocks)


def _score_pair(unit_hat: np.ndarray, size: np.ndarray, unit: np.ndarray) -> dict[str, float | None]:
    total = unit * size
    total_hat = unit_hat * size
    return {
        "mape_unit": _r(_mape(unit, unit_hat)),
        "mae_unit": _r(_mae(unit, unit_hat)),
        "mape_total": _r(_mape(total, total_hat)),
        "mae_total": _r(_mae(total, total_hat)),
    }


def diagnose(pack: dict[str, Any]) -> dict[str, Any]:
    unit = pack["unit"]
    size = pack["size"]
    extra = pack["extra"]
    n_cont = int(pack["n_cont"])
    n = int(len(unit))
    log_u = np.log(unit)
    log_s = np.log(size)
    log_p = log_u + log_s
    center = float(log_s.mean())
    c = log_s - center
    c2 = c ** 2
    p10 = float(np.percentile(size, 10))
    p50 = float(np.percentile(size, 50))
    p90 = float(np.percentile(size, 90))

    x_log = _design([c], extra)
    x_quad = _design([c, c2], extra)
    cont_log = 1 + (n_cont if extra is not None else 0)
    cont_quad = cont_log + 1
    others_c = _design([c2], extra)
    others_c2 = _design([c], extra)

    res_u = _sm(x_quad, log_u)
    res_p = _sm(x_quad, log_p)
    res_ll_u = _sm(x_log, log_u)
    res_ll_p = _sm(x_log, log_p)
    b1 = _coef(res_u, 1)
    b2 = _coef(res_u, 2)
    beta = b1["beta"]
    beta2 = b2["beta"]
    area = turning_area(float(beta), float(beta2), center) if beta is not None and beta2 is not None else None
    kind = _extremum(None if beta2 is None else float(beta2))
    in_range = bool(area is not None and p10 <= area <= p90)
    if area is None:
        near = {"band": "전환면적 ±20%", "n": None, "share": None, "n_below": None, "percentile": None}
    else:
        lo, hi = area / BAND, area * BAND
        band = (size >= lo) & (size <= hi)
        near = {
            "band": "전환면적 ±20%",
            "n": int(band.sum()),
            "share": _r(float(band.mean()) * 100.0, 1),
            "n_below": int(np.sum(size <= area)),
            "percentile": _r(float(np.mean(size <= area)) * 100.0, 1),
        }

    raw_corr = _corr(log_s, log_s ** 2)
    cen_corr = _corr(c, c2)
    vif_c = _vif(c, others_c)
    vif_c2 = _vif(c2, others_c2)

    splits = _folds(n, N_SPLITS, SEED)
    fold_rows: list[dict[str, Any]] = []
    buckets: dict[str, list[float]] = {k: [] for k in ("loglog_unit", "quad_unit", "loglog_total", "quad_total", "ridge", "lasso", "quad_ridge", "quad_lasso")}
    alphas: dict[str, list[float]] = {k: [] for k in ("ridge", "lasso", "quad_ridge", "quad_lasso")}
    square_signs: list[int] = []
    turnings: list[float] = []
    lasso_keep = 0

    for i, (tr, te) in enumerate(splits, start=1):
        row: dict[str, Any] = {"fold": i, "n_test": int(len(te))}
        yte_u = unit[te]
        yte_s = size[te]
        try:
            intercept, coef = _ols_fit(x_quad[tr], log_u[tr])
            b1_f, b2_f = float(coef[0]), float(coef[1])
            turn = turning_area(b1_f, b2_f, center)
            square_signs.append(1 if b2_f > 0 else -1 if b2_f < 0 else 0)
            if turn is not None:
                turnings.append(turn)
            row["beta2"] = _r(b2_f, 4)
            row["extremum"] = _extremum(b2_f)
            row["turning_area"] = _r(turn, 1)
            train_size = size[tr]
            t10, t90 = float(np.percentile(train_size, 10)), float(np.percentile(train_size, 90))
            row["turning_in_train_range"] = bool(turn is not None and t10 <= turn <= t90)
            hat_u = np.exp(np.clip(_predict(intercept, coef, x_quad[te]), -20, 20))
            sc = _score_pair(hat_u, yte_s, yte_u)
            row["quad_unit"] = sc
            buckets["quad_unit"].append(float(sc["mape_unit"]))
        except Exception:
            row["turning_area"] = None
        try:
            intercept, coef = _ols_fit(x_log[tr], log_u[tr])
            hat_u = np.exp(np.clip(_predict(intercept, coef, x_log[te]), -20, 20))
            sc = _score_pair(hat_u, yte_s, yte_u)
            row["loglog_unit"] = sc
            buckets["loglog_unit"].append(float(sc["mape_unit"]))
        except Exception:
            pass
        try:
            intercept, coef = _ols_fit(x_quad[tr], log_p[tr])
            log_hat = _predict(intercept, coef, x_quad[te]) - np.log(yte_s)
            hat_u = np.exp(np.clip(log_hat, -20, 20))
            sc = _score_pair(hat_u, yte_s, yte_u)
            row["quad_total"] = sc
            buckets["quad_total"].append(float(sc["mape_unit"]))
        except Exception:
            pass
        try:
            intercept, coef = _ols_fit(x_log[tr], log_p[tr])
            log_hat = _predict(intercept, coef, x_log[te]) - np.log(yte_s)
            hat_u = np.exp(np.clip(log_hat, -20, 20))
            sc = _score_pair(hat_u, yte_s, yte_u)
            row["loglog_total"] = sc
            buckets["loglog_total"].append(float(sc["mape_unit"]))
        except Exception:
            pass

        for name, x, nstd, pen_kind in (
            ("ridge", x_log, cont_log, "ridge"),
            ("lasso", x_log, cont_log, "lasso"),
            ("quad_ridge", x_quad, cont_quad, "ridge"),
            ("quad_lasso", x_quad, cont_quad, "lasso"),
        ):
            try:
                xtr, xte = _standardize(x[tr], x[te], nstd)
                hat, coef, alpha = penalized_fit(pen_kind, xtr, log_u[tr], xte)
                hat_u = np.exp(np.clip(hat, -20, 20))
                sc = _score_pair(hat_u, yte_s, yte_u)
                kept = None
                sq = None
                if name.startswith("quad"):
                    sq = float(coef[1]) if len(coef) > 1 else None
                    kept = bool(sq is not None and abs(sq) > 1e-8)
                    if name == "quad_lasso" and kept:
                        lasso_keep += 1
                row[name] = {
                    "mape_unit": sc["mape_unit"],
                    "alpha": _r(alpha, 4),
                    "size_coef": _r(float(coef[0]), 4) if len(coef) else None,
                    "square_coef": _r(sq, 4) if sq is not None else None,
                    "square_kept": kept,
                }
                if sc["mape_unit"] is not None:
                    buckets[name].append(float(sc["mape_unit"]))
                alphas[name].append(float(alpha))
            except Exception:
                continue
        fold_rows.append(row)

    def mean(xs: list[float]) -> float | None:
        return _r(float(np.mean(xs))) if xs else None

    def spread(xs: list[float]) -> dict[str, float | None]:
        if not xs:
            return {"min": None, "max": None, "mean": None}
        return {"min": _r(min(xs), 1), "max": _r(max(xs), 1), "mean": _r(float(np.mean(xs)), 1)}

    same_sign = len(set(square_signs)) == 1 and bool(square_signs)
    b1_total = _coef(res_p, 1)["beta"]
    b2_total = _coef(res_p, 2)["beta"]
    shift = None if b1_total is None or beta is None else _r(b1_total - (beta + 1.0), 4)
    out = {
        "n": n,
        "p10": _r(p10, 1),
        "p50": _r(p50, 1),
        "p90": _r(p90, 1),
        "quadratic": {
            "beta1": b1,
            "beta2": b2,
            "extremum": kind,
            "turning_area": _r(area, 1),
            "turning_in_range": in_range,
            "near": near,
            "cv_turning": spread(turnings),
            "cv_same_sign": same_sign,
            "cv_sign_folds": len(square_signs),
            "raw_sq_corr": _r(raw_corr, 3),
            "center_corr": _r(cen_corr, 3),
            "vif_size": _r(vif_c, 2),
            "vif_square": _r(vif_c2, 2),
        },
        "outcomes": {
            "unit_loglog_beta": _coef(res_ll_u, 1),
            "total_loglog_beta": _coef(res_ll_p, 1),
            "total_quad_beta1": _coef(res_p, 1),
            "total_quad_beta2": _coef(res_p, 2),
            "beta_shift_from_plus_one": shift,
            "cv_mape_unit": {k: mean(v) for k, v in buckets.items()},
        },
        "penalty": {
            "standardize": "연속열(중심화 로그면적, 그 제곱, 연도·연식·층)만 학습 겹의 평균과 표준편차로 맞춘다. 더미는 0/1이다.",
            "alpha_grid": [ _r(float(a), 4) for a in ALPHAS ],
            "alpha_rule": "정규화 강도는 학습 겹 안의 3겹 평균제곱오차로만 고른다.",
            "alphas": {k: [_r(a, 4) for a in v] for k, v in alphas.items()},
            "lasso_keeps_square": lasso_keep,
            "lasso_folds": len(splits),
        },
        "folds": fold_rows,
    }
    out["reading"] = _reading(out)
    return out


def _fmt(v: float | None, nd: int = 1) -> str:
    if v is None:
        return "—"
    return f"{v:.{nd}f}"


def _reading(d: dict[str, Any]) -> dict[str, str]:
    q = d["quadratic"]
    b2 = (q["beta2"] or {}).get("beta")
    p2 = (q["beta2"] or {}).get("p")
    near = q["near"]
    turn = q["cv_turning"]
    mape = d["outcomes"]["cv_mape_unit"]
    structure = (
        f"2차 계수는 {_fmt(b2, 4)} (p {_fmt(p2, 4)})로 {'양수' if (b2 or 0) > 0 else '음수'}이다. "
        f"전환면적 {_fmt(q['turning_area'])}㎡는 단가의 {q['extremum'] or '미정'}이다. "
        f"P10–P90({_fmt(d['p10'])}–{_fmt(d['p90'])}㎡) {'안' if q['turning_in_range'] else '밖'}이다. "
        f"그 면적 ±20% 거래는 {near['n']}건, 전체의 {_fmt(near['share'])}%이고, "
        f"그 면적 이하인 거래 비율은 {_fmt(near['percentile'])}%이다. "
        f"학습 겹만 바꿔 다시 맞춘 전환면적은 {_fmt(turn['min'])}–{_fmt(turn['max'])}㎡"
        f"({q['cv_sign_folds']}겹, 부호 {'같음' if q['cv_same_sign'] else '갈림'})이다. "
        f"면적과 제곱의 상관은 중심화 전 {_fmt(q['raw_sq_corr'], 3)}, 중심화 후 {_fmt(q['center_corr'], 3)}이고 "
        f"VIF는 면적 {_fmt(q['vif_size'], 2)}, 제곱 {_fmt(q['vif_square'], 2)}이다."
    )
    prediction = (
        f"검증 MAPE(㎡당 단가)는 log-log {_fmt(mape.get('loglog_unit'))}%, "
        f"2차 {_fmt(mape.get('quad_unit'))}%, "
        f"Ridge {_fmt(mape.get('ridge'))}%, Lasso {_fmt(mape.get('lasso'))}%, "
        f"2차+Ridge {_fmt(mape.get('quad_ridge'))}%, 2차+Lasso {_fmt(mape.get('quad_lasso'))}%이다. "
        f"2차와 log-log의 차이는 {_fmt((mape.get('quad_unit') or 0) - (mape.get('loglog_unit') or 0))}%p이다."
    )
    ou = d["outcomes"]

    def gap(a: float | None, b: float | None) -> float | None:
        if a is None or b is None:
            return None
        return abs(float(a) - float(b))

    gq = gap(mape.get("quad_unit"), mape.get("quad_total"))
    gl = gap(mape.get("loglog_unit"), mape.get("loglog_total"))
    close = gq is not None and gl is not None and gq < 0.05 and gl < 0.05
    converted = "환산 MAPE는 소수점 한 자리까지 같다." if close else f"환산 MAPE 차이는 2차 {_fmt(gq)}%p, log-log {_fmt(gl)}%p이다."
    y_compare = (
        f"같은 행으로 환산한 검증 MAPE는 단가 2차 {_fmt(mape.get('quad_unit'))}%, "
        f"총액 2차 {_fmt(mape.get('quad_total'))}%, "
        f"단가 log-log {_fmt(mape.get('loglog_unit'))}%, "
        f"총액 log-log {_fmt(mape.get('loglog_total'))}%이다. "
        f"총액 log-log 기울기 {_fmt((ou['total_loglog_beta'] or {}).get('beta'), 4)}와 "
        f"단가 기울기+1의 차이는 {_fmt(ou['beta_shift_from_plus_one'], 4)}이다. "
        f"총액 2차의 제곱계수는 {_fmt((ou['total_quad_beta2'] or {}).get('beta'), 4)}이다. "
        f"{converted} 금액 MAE는 큰 면적에 더 실린다."
    )
    pen = d["penalty"]
    penalty = (
        f"{pen['standardize']} {pen['alpha_rule']} "
        f"겹별 Ridge 강도는 {pen['alphas'].get('ridge')}이고, "
        f"2차+Ridge 강도는 {pen['alphas'].get('quad_ridge')}이다. "
        f"Lasso가 2차항을 남긴 겹은 {pen['lasso_keeps_square']}/{pen['lasso_folds']}이다. "
        "2차항이 없는 수축과 2차항이 있는 수축은 위의 MAPE로 갈라 둔다."
    )
    return {"structure": structure, "prediction": prediction, "y_compare": y_compare, "penalty": penalty}


def _land(engine: Engine, code: str, cat: str) -> dict[str, Any] | None:
    with engine.connect() as conn:
        cols = _cols(conn, "land_transactions")
        y0, y1 = _window(conn, "land_transactions", cols)
        lo, hi = _prefix_bounds(code)
        df = _load_rows(
            conn,
            """
            SELECT area_sqm::float8 AS size, unit_price_per_sqm::float8 AS y,
                   contract_year::float8 AS year, road_condition, zone_type
            FROM land_transactions
            WHERE is_valid = TRUE
              AND COALESCE(is_cancelled, FALSE) = FALSE
              AND COALESCE(is_partial_ownership, FALSE) = FALSE
              AND contract_year BETWEEN :y0 AND :y1
              AND area_sqm > 0 AND unit_price_per_sqm > 0
              AND btrim(land_category::text) = :cat
              AND beopjungri_code >= :lo AND beopjungri_code < :hi
            ORDER BY id
            """,
            {"y0": y0, "y1": y1, "cat": cat, "lo": lo, "hi": hi},
        )
        road = _collapse(df["road_condition"]) if not df.empty else np.zeros((0, 0))
        zone = _collapse(_zone_group(df["zone_type"]), k=4) if not df.empty else np.zeros((0, 0))
        parts = [a for a in (road, zone) if getattr(a, "size", 0)]
        dummies = np.column_stack(parts) if parts else np.zeros((len(df), 0))
        pack = _prepare(df, ["year"], dummies)
        return None if pack is None else {"years": (y0, y1), "pack": pack}


def _built(engine: Engine, code: str, cat: str) -> dict[str, Any] | None:
    with engine.connect() as conn:
        cols = _cols(conn, "built_transactions")
        y0, y1 = _window(conn, "built_transactions", cols)
        code_col = "eupmyeondong_code" if "eupmyeondong_code" in cols else "beopjungri_code"
        df = _load_rows(
            conn,
            f"""
            SELECT gross_area::float8 AS size, (price / gross_area)::float8 AS y,
                   building_age::float8 AS age, road_width_label, zone_type
            FROM built_transactions
            WHERE is_valid = TRUE
              AND contract_year BETWEEN :y0 AND :y1
              AND gross_area > 0 AND price > 0
              AND btrim(asset_type::text) = :cat
              AND left(btrim({code_col}::text), 8) = :code
            ORDER BY id
            """,
            {"y0": y0, "y1": y1, "cat": cat, "code": code},
        )
        road = _collapse(df["road_width_label"]) if not df.empty and "road_width_label" in df else np.zeros((len(df), 0))
        zone = _collapse(_zone_group(df["zone_type"]), k=4) if not df.empty and "zone_type" in df else np.zeros((len(df), 0))
        parts = [a for a in (road, zone) if getattr(a, "size", 0)]
        dummies = np.column_stack(parts) if parts else np.zeros((len(df), 0))
        pack = _prepare(df, ["age"], dummies)
        return None if pack is None else {"years": (y0, y1), "pack": pack}


def _collective(engine: Engine, code: str, *, commercial: bool, cat: str | None) -> dict[str, Any] | None:
    table = "collective_commercial_transactions" if commercial else "collective_transactions"
    size_col = "gross_area" if commercial else "exclusive_area"
    with engine.connect() as conn:
        cols = _cols(conn, table)
        y0, y1 = _window(conn, table, cols)
        code_col = "eupmyeondong_code" if "eupmyeondong_code" in cols else "beopjungri_code"
        floor = "floor::float8 AS floor" if "floor" in cols else "NULL::float8 AS floor"
        asset_clause = "" if cat is None else "AND btrim(asset_type::text) = :cat"
        params: dict[str, Any] = {"y0": y0, "y1": y1, "code": code}
        if cat is not None:
            params["cat"] = cat
        df = _load_rows(
            conn,
            f"""
            SELECT {size_col}::float8 AS size, unit_price::float8 AS y,
                   contract_year::float8 AS year, {floor}
            FROM {table}
            WHERE is_valid = TRUE
              AND contract_year BETWEEN :y0 AND :y1
              AND {size_col} > 0 AND unit_price > 0
              AND left(btrim({code_col}::text), 8) = :code
              {asset_clause}
            ORDER BY id
            """,
            params,
        )
        pack = _prepare(df, ["year", "floor"], np.zeros((len(df), 0)))
        return None if pack is None else {"years": (y0, y1), "pack": pack}


def _cell(spec: dict[str, Any], loaded: dict[str, Any] | None) -> dict[str, Any]:
    base = {
        "id": spec["id"],
        "name": spec["name"],
        "domain": spec["domain"],
        "slice": spec["slice"],
        "size_label": spec["size_label"],
        "controls": spec["controls"],
        "ask": spec["ask"],
        "sample_note": spec["sample_note"],
    }
    if loaded is None:
        base["status"] = "행 없음"
        return base
    y0, y1 = loaded["years"]
    base["year_from"] = y0
    base["year_to"] = y1
    base["status"] = "ok"
    base["fit"] = diagnose(loaded["pack"])
    return base


def main() -> None:
    from app.built.db import get_built_engine
    from app.collective.db import get_collective_engine
    from app.db import engine as land_engine

    built_engine = get_built_engine()
    collective_engine = get_collective_engine()
    if built_engine is None or collective_engine is None:
        raise RuntimeError("built 또는 collective DB 연결이 없다")
    jobs = (
        (
            {"id": "pyeongtaek", "name": "경기도 평택시 평택동", "domain": "집합주거", "slice": "아파트", "size_label": "전용면적", "controls": "연도·층", "ask": "2차항이 예측오차를 얼마나 줄이는가", "sample_note": "1단계 외곽 개발 칸과 같은 아파트 거래."},
            lambda: _collective(collective_engine, "41220113", commercial=False, cat="apartment"),
        ),
        (
            {"id": "hannam", "name": "서울특별시 용산구 한남동", "domain": "토지", "slice": "대", "size_label": "계약면적", "controls": "연도·도로·용도", "ask": "68㎡ 전환면적이 어떤 극값이고 주변에 거래가 있는가", "sample_note": "1단계 도시 주거 칸과 같은 대지 거래."},
            lambda: _land(land_engine, "11170131", "대"),
        ),
        (
            {"id": "gojan", "name": "경기도 안산시 고잔동", "domain": "복합", "slice": "상업", "size_label": "연면적", "controls": "연식·도로·용도", "ask": "정규화 모형의 오차 감소가 2차항에서 오는가", "sample_note": "1단계 용도 혼재 칸과 같은 상업 거래."},
            lambda: _built(built_engine, "41273101", "commercial"),
        ),
        (
            {"id": "juan", "name": "인천광역시 미추홀구 주안동", "domain": "비주거", "slice": "상가·공장", "size_label": "연면적", "controls": "연도·층", "ask": "표본이 커도 비선형 예측 개선이 작은가", "sample_note": "1단계 유형 혼재 칸과 같이 이 읍면동의 상가·공장을 함께 썼다."},
            lambda: _collective(collective_engine, "28177105", commercial=True, cat=None),
        ),
    )
    cells = []
    for spec, loader in jobs:
        print(f"run {spec['id']}", flush=True)
        try:
            cells.append(_cell(spec, loader()))
            print(f"done {spec['id']}", flush=True)
        except Exception as exc:
            cells.append({**spec, "status": "fail", "note": f"{type(exc).__name__}: {exc}"})
            print(f"fail {spec['id']}: {type(exc).__name__}: {exc}", flush=True)
    payload = {
        "title": "규모효과 회귀실험 2단계",
        "generated": date.today().isoformat(),
        "keeps": "1단계 기록은 그대로 둔다.",
        "method": "같은 거래와 같은 통제. 면적 제곱은 칸 전체 로그면적 평균으로 중심화. 예측은 ㎡당 단가와 총액(단가×면적)으로 환산한 5겹 MAPE.",
        "score_note": "단가 식과 총액 식은 같은 행이다. 총액 예측은 관측 면적으로 ㎡당 단가 MAPE에 맞춘다. 총액 log-log 기울기는 단가 기울기+1과 같다.",
        "cells": cells,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {OUT}", flush=True)


if __name__ == "__main__":
    main()
