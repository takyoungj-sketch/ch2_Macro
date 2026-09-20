"""1차 선정 칸에 모형 A/B/C (Raw vs 단가 Robust).

면적 IQR 없음. B는 동 가드 미달이면 B_skip. turning point는 P10–P90 안일 때만.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np
import pandas as pd
import statsmodels.api as sm
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.land_lab.area_elasticity import n_tier
from app.land_lab.area_elasticity_screen import (
    fetch_cell_transactions,
    period_bounds_for_window,
)
from app.land_regression import _pick_reference_road

B_MIN_DONGS = 5
B_MIN_DONG_MEDIAN = 8
C_MIN_N = 150
P_CURVE = 0.05


def _iqr_mask(values: np.ndarray, multiplier: float = 1.5) -> np.ndarray:
    q1, q3 = np.percentile(values, 25), np.percentile(values, 75)
    iqr = q3 - q1
    return (values >= q1 - multiplier * iqr) & (values <= q3 + multiplier * iqr)


def _road_dummies(series: pd.Series) -> tuple[pd.DataFrame, str | None]:
    col = series.fillna("미상").astype(str).str.strip()
    cats = sorted(col.unique())
    if len(cats) < 2:
        return pd.DataFrame(index=series.index), None
    ref = _pick_reference_road(cats)
    dummies = pd.get_dummies(col, prefix="road", drop_first=False).astype(float)
    dummies = dummies.drop(columns=[f"road_{ref}"], errors="ignore")
    dummies.columns = [c.replace(" ", "_") for c in dummies.columns]
    return dummies, ref


def _beop_dummies(series: pd.Series) -> tuple[pd.DataFrame, str | None, list[str]]:
    col = series.fillna("미상").astype(str).str.strip()
    if col.nunique() < 2:
        return pd.DataFrame(index=series.index), None, ["beop_cats<2"]
    ref = str(col.value_counts().idxmax())
    dummies = pd.get_dummies(col, prefix="beop", drop_first=False).astype(float)
    dummies = dummies.drop(columns=[f"beop_{ref}"], errors="ignore")
    small = [c for c in dummies.columns if dummies[c].sum() < 3]
    notes = []
    if small:
        dummies = dummies.drop(columns=small)
        notes.append(f"beop_dropped_small={len(small)}")
    if dummies.empty:
        return pd.DataFrame(index=series.index), None, notes + ["beop_empty"]
    return dummies, ref, notes


def _ols(y: pd.Series, X: pd.DataFrame) -> sm.regression.linear_model.RegressionResultsWrapper | None:
    if X.shape[0] < 8 or X.shape[1] < 2:
        return None
    try:
        return sm.OLS(y.astype(float), X.astype(float), missing="drop").fit()
    except Exception:
        return None


def _coef(res, name: str) -> dict[str, float | None]:
    if res is None or name not in res.params.index:
        return {"beta": None, "se": None, "p": None}
    return {
        "beta": round(float(res.params[name]), 4),
        "se": round(float(res.bse[name]), 4),
        "p": round(float(res.pvalues[name]), 4),
    }


def _prepare(rows: list[dict[str, Any]]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["area_sqm"] = pd.to_numeric(df["area_sqm"], errors="coerce")
    df["unit_price_per_sqm"] = pd.to_numeric(df["unit_price_per_sqm"], errors="coerce")
    df["contract_year"] = pd.to_numeric(df["contract_year"], errors="coerce")
    df = df.dropna(subset=["area_sqm", "unit_price_per_sqm", "contract_year"])
    df = df[(df["area_sqm"] > 0) & (df["unit_price_per_sqm"] > 0)].copy()
    df["log_area"] = np.log(df["area_sqm"].clip(lower=0.01))
    df["log_price"] = np.log(df["unit_price_per_sqm"])
    df["year_trend"] = df["contract_year"] - df["contract_year"].mean()
    if "beopjungri_code" in df.columns:
        df["beop"] = df["beopjungri_code"].fillna("미상").astype(str).str.strip()
    else:
        df["beop"] = "미상"
    return df


def _design_a(df: pd.DataFrame, *, quadratic: bool = False) -> pd.DataFrame:
    parts = [df[["log_area", "year_trend"]].astype(float)]
    if quadratic:
        parts.append((df["log_area"] ** 2).rename("log_area_sq").to_frame())
    roads, _ref = _road_dummies(df["road_condition"] if "road_condition" in df.columns else pd.Series("미상", index=df.index))
    if not roads.empty:
        parts.append(roads)
    X = pd.concat(parts, axis=1)
    return sm.add_constant(X, has_constant="add")


def _tercile_medians(df: pd.DataFrame) -> dict[str, float | None]:
    if len(df) < 9:
        return {"low": None, "mid": None, "high": None}
    try:
        bins = pd.qcut(df["area_sqm"], 3, labels=["low", "mid", "high"], duplicates="drop")
    except ValueError:
        return {"low": None, "mid": None, "high": None}
    med = df.groupby(bins, observed=True)["unit_price_per_sqm"].median()
    return {
        "low": _round(med.get("low")),
        "mid": _round(med.get("mid")),
        "high": _round(med.get("high")),
    }


def _turning_point(res, p10: float | None, p90: float | None) -> dict[str, Any]:
    empty = {"area_star": None, "in_range": False, "beta2_sig": False}
    if res is None or "log_area" not in res.params.index or "log_area_sq" not in res.params.index:
        return empty
    b1 = float(res.params["log_area"])
    b2 = float(res.params["log_area_sq"])
    p2 = float(res.pvalues["log_area_sq"])
    sig = p2 < P_CURVE and abs(b2) > 0
    if not sig or b2 == 0:
        return {**empty, "beta2_sig": sig, "beta2": round(b2, 4), "p2": round(p2, 4)}
    x_star = -b1 / (2.0 * b2)
    area_star = float(np.exp(x_star))
    in_range = (
        p10 is not None
        and p90 is not None
        and p10 <= area_star <= p90
    )
    return {
        "area_star": round(area_star, 1),
        "in_range": bool(in_range),
        "beta2_sig": True,
        "beta2": round(b2, 4),
        "p2": round(p2, 4),
    }


def _b_guard(df: pd.DataFrame) -> tuple[bool, str]:
    counts = df["beop"].value_counts()
    n_dongs = int(len(counts))
    med = float(counts.median()) if n_dongs else 0.0
    if n_dongs < B_MIN_DONGS or med < B_MIN_DONG_MEDIAN:
        return False, "B_skip"
    return True, "B_ok"


def fit_cell(rows: list[dict[str, Any]]) -> dict[str, Any]:
    df = _prepare(rows)
    n = int(len(df))
    p10 = float(df["area_sqm"].quantile(0.10)) if n else None
    p90 = float(df["area_sqm"].quantile(0.90)) if n else None
    out: dict[str, Any] = {
        "n_raw": n,
        "n_tier": n_tier(n),
        "A": None,
        "A_robust": None,
        "B": "B_skip",
        "C": None,
        "tercile_median_unit_price": _tercile_medians(df) if n else None,
        "notes": [],
    }
    if n < 50:
        out["notes"].append("n<50")
        return out

    y = df["log_price"]
    xa = _design_a(df, quadratic=False)
    res_a = _ols(y, xa)
    out["A"] = _coef(res_a, "log_area")
    if res_a is not None:
        out["A"]["n"] = int(res_a.nobs)
        out["A"]["r2"] = round(float(res_a.rsquared), 3)

    mask = _iqr_mask(df["unit_price_per_sqm"].to_numpy())
    df_r = df.loc[mask].copy()
    if len(df_r) >= 50:
        y_r = df_r["log_price"]
        xr = _design_a(df_r, quadratic=False)
        res_r = _ols(y_r, xr)
        out["A_robust"] = _coef(res_r, "log_area")
        if res_r is not None:
            out["A_robust"]["n"] = int(res_r.nobs)
    else:
        out["notes"].append("robust_n<50")

    ok_b, b_label = _b_guard(df)
    if ok_b and n >= 50:
        beop, _ref, notes = _beop_dummies(df["beop"])
        out["notes"].extend(notes)
        if not beop.empty:
            xb = pd.concat([xa, beop], axis=1)
            res_b = _ols(y, xb)
            coef = _coef(res_b, "log_area")
            coef["status"] = "ok"
            if res_b is not None:
                coef["n"] = int(res_b.nobs)
            out["B"] = coef
        else:
            out["B"] = "B_skip"
    else:
        out["B"] = b_label

    if n >= 80:
        xc = _design_a(df, quadratic=True)
        res_c = _ols(y, xc)
        c_pack = {
            "log_area": _coef(res_c, "log_area"),
            "log_area_sq": _coef(res_c, "log_area_sq"),
            "turning": _turning_point(res_c, p10, p90),
            "status": "ok" if n >= C_MIN_N else "note",
        }
        out["C"] = c_pack
    else:
        out["notes"].append("C_skip_n<80")
    return out


def attach_phase1_fits(payload: dict[str, Any], *, engine_bind: Engine) -> dict[str, Any]:
    as_of = date.fromisoformat(str(payload["as_of_month"]))
    window = int(payload["window_years"])
    period_start, period_end = period_bounds_for_window(as_of, window)
    SessionLocal = sessionmaker(bind=engine_bind, autocommit=False, autoflush=False)
    db = SessionLocal()
    fits: list[dict[str, Any]] = []
    try:
        for cell in payload.get("phase1") or []:
            rows = fetch_cell_transactions(
                db,
                sigungu_code=str(cell["sigungu_code"]),
                land_category=str(cell["land_category"]),
                period_start=period_start,
                period_end=period_end,
            )
            rec = {
                "sido_name": cell["sido_name"],
                "sigungu_name": cell["sigungu_name"],
                "sigungu_code": cell["sigungu_code"],
                "land_category": cell["land_category"],
                "region_type": cell["region_type"],
                "n_screen": cell["n"],
            }
            rec.update(fit_cell(rows))
            fits.append(rec)
    finally:
        db.close()
    payload = dict(payload)
    payload["status"] = "phase1_fit"
    payload["phase1_fits"] = fits
    payload["phase1_fit_summary"] = _fit_summary(fits)
    return payload


def _fit_summary(fits: list[dict[str, Any]]) -> dict[str, Any]:
    betas = []
    signs_match = 0
    both = 0
    neg = 0
    turn_in = 0
    turn_n = 0
    for f in fits:
        a = f.get("A") or {}
        b = a.get("beta")
        if b is None:
            continue
        betas.append(float(b))
        if b < 0:
            neg += 1
        rb = (f.get("A_robust") or {}).get("beta")
        if rb is not None:
            both += 1
            if (b < 0) == (float(rb) < 0):
                signs_match += 1
        turning = ((f.get("C") or {}) or {}).get("turning") or {}
        if turning.get("beta2_sig"):
            turn_n += 1
            if turning.get("in_range"):
                turn_in += 1
    n = len(betas)
    return {
        "n_fits": n,
        "beta_a_median": round(float(np.median(betas)), 4) if betas else None,
        "share_negative": round(neg / n, 3) if n else None,
        "raw_robust_sign_match": round(signs_match / both, 3) if both else None,
        "turning_in_range_given_sig": round(turn_in / turn_n, 3) if turn_n else None,
    }


def _round(v: Any) -> float | None:
    if v is None or (isinstance(v, float) and v != v):
        return None
    try:
        return round(float(v), 2)
    except (TypeError, ValueError):
        return None
