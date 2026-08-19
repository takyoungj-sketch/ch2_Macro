"""트랙 A — 본선 M1-A(토지) vs 진단 M1-B(구시세). SSOT §3."""

from __future__ import annotations

from typing import Any, Literal

import numpy as np
import pandas as pd
import statsmodels.api as sm

from app.collective.new_apt.constants import (
    BUILDER_OTHER,
    FOCUS_COEF_NAMES,
    HOLD_OUT_FRAC,
    MATCH_TIERS,
    MIN_BUILDINGS_PER_BUILDER,
    NEW_AGE_MAX,
    STRUCTURE_REFERENCE,
    VINTAGE_REFERENCE,
)

LocationMode = Literal[
    "none",
    "land",
    "sigungu",
    "both",
    "gu_fe",
    "gu_fe_land",
    "sido_fe",
    "sido_fe_land",
]
ProductLevel = Literal["M0", "M1", "M2", "M3"]


def _ln(s: pd.Series) -> pd.Series:
    return np.log(s.astype(float).clip(lower=1e-6))


def holdout_buildings(df: pd.DataFrame, *, seed: int = 42) -> set[str]:
    new_b = df.loc[df["age"].notna() & (df["age"] >= 0) & (df["age"] <= NEW_AGE_MAX), "building_key"]
    keys = list(new_b.dropna().astype(str).unique())
    rng = np.random.default_rng(seed)
    rng.shuffle(keys)
    n = max(1, int(round(len(keys) * HOLD_OUT_FRAC))) if len(keys) else 0
    return set(keys[:n])


def land_dispersion(df: pd.DataFrame) -> dict[str, Any]:
    """동 안 vs 대전 전체 — 토지 P50이 어디서 움직이는지."""
    s = df["land_p50"].astype(float).dropna()
    if s.empty:
        return {}
    work = df.dropna(subset=["land_p50"]).copy()
    work["eup"] = work["beopjungri_code"].astype(str).str[:8]
    overall = float(s.std() / s.mean()) if float(s.mean()) else None
    within_eup = work.groupby("eup")["land_p50"].agg(["std", "mean", "size"])
    within_eup = within_eup[within_eup["size"] >= 3]
    cv_eup = (within_eup["std"] / within_eup["mean"].replace(0, np.nan)).dropna()
    within_sg = work.groupby("sigungu_code")["land_p50"].agg(["std", "mean", "size"])
    within_sg = within_sg[within_sg["size"] >= 3]
    cv_sg = (within_sg["std"] / within_sg["mean"].replace(0, np.nan)).dropna()
    return {
        "land_cv_daejeon": round(overall, 4) if overall is not None else None,
        "land_cv_mean_within_eup": round(float(cv_eup.mean()), 4) if len(cv_eup) else None,
        "land_cv_mean_within_sigungu": round(float(cv_sg.mean()), 4) if len(cv_sg) else None,
        "n_eup_with_3plus": int(len(within_eup)),
        "note": "동 내부 CV가 대전 전체 CV보다 작으면 토지는 동 내부가 아니라 대전 입지 변수",
    }


def _collapse_builder(train: pd.DataFrame) -> pd.Series:
    vc = train.dropna(subset=["builder_group"]).groupby("builder_group")["building_key"].nunique()
    keep = set(vc[vc >= MIN_BUILDINGS_PER_BUILDER].index.astype(str))
    s = train["builder_group"].fillna(BUILDER_OTHER).astype(str)
    return s.where(s.isin(keep) | (s == BUILDER_OTHER), other=BUILDER_OTHER)


def _design(
    df: pd.DataFrame,
    *,
    product: ProductLevel,
    location: LocationMode,
    builder_map: pd.Series | None = None,
) -> tuple[pd.DataFrame, pd.Series, pd.Series]:
    work = df.copy()
    parts: list[pd.DataFrame] = []
    yr = work["calendar_year"].astype(str)
    yd = pd.get_dummies(yr, prefix="yr", drop_first=True)
    parts.append(yd.astype(float))

    if location in ("land", "both", "gu_fe_land", "sido_fe_land"):
        parts.append(_ln(work["land_p50"]).to_frame("ln_land_p50"))
    if location in ("sigungu", "both"):
        lag = work["sigungu_sale_p50_lag"] if "sigungu_sale_p50_lag" in work.columns else pd.Series(np.nan, index=work.index)
        parts.append(_ln(lag).to_frame("ln_sigungu_sale_lag"))
    if location in ("gu_fe", "gu_fe_land"):
        gd = pd.get_dummies(work["sigungu_code"].astype(str), prefix="gu", drop_first=True)
        parts.append(gd.astype(float))
    if location in ("sido_fe", "sido_fe_land"):
        sd = pd.get_dummies(work["sido_code"].astype(str), prefix="sido", drop_first=True)
        parts.append(sd.astype(float))

    if product in ("M2", "M3"):
        parts.append(_ln(work["households"]).to_frame("ln_households"))
        parts.append(work[["max_floor"]].astype(float))
        parts.append(work[["parking_per_household"]].astype(float))
        vt = work["vintage"].fillna(VINTAGE_REFERENCE).astype(str)
        dum = pd.get_dummies(vt, prefix="vintage", drop_first=False)
        ref = f"vintage_{VINTAGE_REFERENCE}"
        if ref in dum.columns:
            dum = dum.drop(columns=[ref])
        parts.append(dum.astype(float))
    if product == "M3":
        b = builder_map if builder_map is not None else work["builder_group"].fillna(BUILDER_OTHER)
        dum = pd.get_dummies(b.astype(str), prefix="builder", drop_first=False)
        ref = f"builder_{BUILDER_OTHER}"
        if ref in dum.columns:
            dum = dum.drop(columns=[ref])
        parts.append(dum.astype(float))
        st = work["structure_group"].fillna(STRUCTURE_REFERENCE).astype(str)
        sd = pd.get_dummies(st, prefix="struct", drop_first=False)
        sref = f"struct_{STRUCTURE_REFERENCE}"
        if sref in sd.columns:
            sd = sd.drop(columns=[sref])
        parts.append(sd.astype(float))

    x = pd.concat(parts, axis=1) if parts else pd.DataFrame(index=work.index)
    x = x.replace([np.inf, -np.inf], np.nan)
    ok = x.notna().all(axis=1) & work["y_median_unit_price"].notna()
    x = sm.add_constant(x.loc[ok].astype(float), has_constant="add")
    y = _ln(work.loc[ok, "y_median_unit_price"])
    w = work.loc[ok, "n_tx"].astype(float).clip(lower=1)
    return x, y, w


def _metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    err = y_pred - y_true
    mae = float(np.mean(np.abs(err)))
    mape = float(np.mean(np.abs(err / np.clip(y_true, 1e-6, None))) * 100)
    return {"mae": round(mae, 4), "mape": round(mape, 2)}


def _equation(params: pd.Series) -> str:
    bits = ["ln(P) ="]
    for name, c in params.items():
        if name == "const":
            bits.append(f" {float(c):.3f}")
            continue
        sign = "+" if float(c) >= 0 else "−"
        bits.append(f" {sign} {abs(float(c)):.3f}·[{name}]")
    return "".join(bits)


def _coef_table(model: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for name in model.params.index:
        coef = float(model.params[name])
        se = float(model.bse[name]) if name in model.bse.index else None
        t = float(model.tvalues[name]) if name in model.tvalues.index else None
        p = float(model.pvalues[name]) if name in model.pvalues.index else None
        plain = f"{(np.exp(coef) - 1) * 100:.1f}%" if str(name).startswith("ln_") else f"{coef:.4f}"
        rows.append(
            {
                "name": str(name),
                "coef": round(coef, 6),
                "se": round(se, 6) if se is not None else None,
                "t": round(t, 3) if t is not None else None,
                "p": round(p, 5) if p is not None else None,
                "plain": plain,
            }
        )
    return rows


def focus_coefs(coefficients: list[dict[str, Any]]) -> dict[str, Any]:
    by_name = {c["name"]: c for c in coefficients}
    out: dict[str, Any] = {}
    for name in FOCUS_COEF_NAMES:
        row = by_name.get(name)
        if not row or row.get("coef") is None:
            out[name] = {"coef": None, "t": None, "p": None, "sign": None}
            continue
        coef = float(row["coef"])
        out[name] = {
            "coef": round(coef, 6),
            "t": row.get("t"),
            "p": row.get("p"),
            "sign": "+" if coef >= 0 else "−",
        }
    return out


def fit_spec(
    train: pd.DataFrame,
    hold: pd.DataFrame,
    *,
    product: ProductLevel,
    location: LocationMode,
    track: str,
) -> dict[str, Any]:
    t = train.copy()
    builder_map = _collapse_builder(t) if product == "M3" else None
    if product == "M3":
        t["_builder_term"] = builder_map
    x, y, w = _design(t, product=product, location=location, builder_map=builder_map)
    out: dict[str, Any] = {
        "track": track,
        "product": product,
        "location": location,
        "n_train": int(len(y)),
        "adj_r_squared": None,
        "holdout_mae": None,
        "holdout_mape": None,
        "n_holdout": 0,
        "land_coef": None,
        "households_coef": None,
        "floor_coef": None,
        "parking_coef": None,
        "focus": {name: {"coef": None, "t": None, "p": None, "sign": None} for name in FOCUS_COEF_NAMES},
        "equation": "",
        "coefficients": [],
        "builder_gamma": [],
        "warnings": [],
    }
    if len(y) < 30 or x.shape[1] >= len(y):
        out["warnings"].append("표본 부족")
        return out
    try:
        model = sm.WLS(y, x, weights=w).fit(cov_type="HC3")
    except Exception as exc:  # noqa: BLE001
        out["warnings"].append(str(exc))
        return out
    out["adj_r_squared"] = round(float(model.rsquared_adj), 5)
    out["equation"] = _equation(model.params)
    out["coefficients"] = _coef_table(model)
    out["focus"] = focus_coefs(out["coefficients"])
    if "ln_land_p50" in model.params.index:
        out["land_coef"] = round(float(model.params["ln_land_p50"]), 4)
    if "ln_households" in model.params.index:
        out["households_coef"] = round(float(model.params["ln_households"]), 4)
    if "max_floor" in model.params.index:
        out["floor_coef"] = round(float(model.params["max_floor"]), 4)
    if "parking_per_household" in model.params.index:
        out["parking_coef"] = round(float(model.params["parking_per_household"]), 4)
    if product == "M3":
        for name, coef in model.params.items():
            if str(name).startswith("builder_"):
                se = float(model.bse[name]) if name in model.bse.index else None
                out["builder_gamma"].append(
                    {
                        "term": str(name),
                        "coef": round(float(coef), 6),
                        "pct": round((np.exp(float(coef)) - 1) * 100, 2),
                        "se": round(se, 6) if se is not None else None,
                    }
                )
    if hold is not None and not hold.empty:
        h = hold.copy()
        hmap = None
        if product == "M3":
            keep = set(t["_builder_term"].unique())
            h["_builder_term"] = h["builder_group"].fillna(BUILDER_OTHER).astype(str)
            h["_builder_term"] = h["_builder_term"].where(h["_builder_term"].isin(keep), BUILDER_OTHER)
            hmap = h["_builder_term"]
        xh, yh, _ = _design(h, product=product, location=location, builder_map=hmap)
        xh = xh.reindex(columns=x.columns, fill_value=0.0)
        if len(yh):
            pred_ln = model.predict(xh)
            met = _metrics(np.exp(yh.to_numpy()), np.exp(np.asarray(pred_ln)))
            out["holdout_mae"] = met["mae"]
            out["holdout_mape"] = met["mape"]
            out["n_holdout"] = int(len(yh))
    return out


def prepare_track_a(df: pd.DataFrame) -> pd.DataFrame:
    work = df.copy()
    if "match_tier" in work.columns:
        work = work[work["match_tier"].isin(MATCH_TIERS)]
    if "attr_quality_flags" in work.columns:
        flags = work["attr_quality_flags"].fillna("")
        work.loc[flags.str.contains("hh_zero|scale_inconsistent", regex=True), "households"] = np.nan
        work.loc[flags.str.contains("floor_implausible"), "max_floor"] = np.nan
        work.loc[flags.str.contains("parking_implausible"), "parking_per_household"] = np.nan
    work = work[work["y_median_unit_price"].notna()]
    return work


def run_comparison(df: pd.DataFrame) -> dict[str, Any]:
    work = prepare_track_a(df)
    hold_keys = holdout_buildings(work)
    land_ok = work["land_p50"].notna()
    hold_new = work[work["building_key"].astype(str).isin(hold_keys) & (work["age"] <= NEW_AGE_MAX) & land_ok]
    train_all = work[~work["building_key"].astype(str).isin(hold_keys) & land_ok]
    train_new = train_all[train_all["age"].notna() & (train_all["age"] >= 0) & (train_all["age"] <= NEW_AGE_MAX)]

    ladder: list[tuple[str, ProductLevel, LocationMode]] = [
        ("main", "M0", "none"),
        ("main", "M1", "land"),
        ("main", "M2", "land"),
        ("main", "M3", "land"),
        ("diag_b", "M1", "sigungu"),
        ("diag_b", "M1", "both"),
        ("diag_b", "M2", "both"),
        ("diag_b", "M3", "both"),
        ("diag_c", "M1", "gu_fe"),
        ("diag_c", "M1", "gu_fe_land"),
    ]
    rows: list[dict[str, Any]] = []
    for sample, train, hold in (("A-1-land", train_all, hold_new), ("A-2-land", train_new, hold_new)):
        for track, product, location in ladder:
            result = fit_spec(train, hold, product=product, location=location, track=track)
            result["sample"] = sample
            result["n_train_buildings"] = int(train["building_key"].nunique()) if not train.empty else 0
            result["is_baseline"] = (
                track == "main" and product == "M2" and location == "land" and sample == "A-1-land"
            )
            rows.append(result)

    return {
        "n_cells_land": int(land_ok.sum()),
        "n_holdout_buildings": len(hold_keys),
        "n_holdout_new_cells": int(len(hold_new)),
        "land_dispersion": land_dispersion(work[land_ok]),
        "table": rows,
        "notes": [
            "본선(main): 연도 + 토지 → 상품 → 시공사. 구 아파트 P50 없음",
            "진단 B: 구 시세 대비 토지 추가 설명력",
            "진단 C: 구 FE — 분석용, 신규 예측기에 넣지 않음",
            "hold-out은 준공 0~5년 단지 20%, MAE/MAPE는 만원/㎡",
        ],
    }


def m2_complete(df: pd.DataFrame) -> pd.Series:
    return (
        df["land_p50"].notna()
        & df["households"].notna()
        & df["max_floor"].notna()
        & df["parking_per_household"].notna()
        & df["y_median_unit_price"].notna()
        & df["calendar_year"].notna()
    )


def fit_wls(
    train: pd.DataFrame,
    *,
    product: ProductLevel,
    location: LocationMode,
) -> Any | None:
    x, y, w = _design(train, product=product, location=location)
    if len(y) < 30 or x.shape[1] >= len(y):
        return None
    try:
        return sm.WLS(y, x, weights=w).fit(cov_type="HC3")
    except Exception:  # noqa: BLE001
        return None


def predict_unit_price(
    model: Any,
    target: pd.DataFrame,
    *,
    product: ProductLevel,
    location: LocationMode,
) -> pd.Series:
    xh, yh, _ = _design(target, product=product, location=location)
    xh = xh.reindex(columns=model.params.index, fill_value=0.0)
    pred_ln = model.predict(xh)
    return pd.Series(np.exp(np.asarray(pred_ln)), index=yh.index, name="yhat")
