"""단일 건물 OLS — 층·동 더미."""

from __future__ import annotations

import pandas as pd
import statsmodels.api as sm

from app.collective.schemas import (
    CollectiveRegressionRequest,
    CollectiveRegressionResponse,
    RegressionCoeff,
)

# 상대 층(단지 max 층 대비) — 참고 preprocess_floor_dummies 규격
_REL_FLOOR_LABELS: dict[str, str] = {
    "floor_rel_1": "1층",
    "floor_rel_top": "최상층",
    "floor_rel_low": "저층부",
    "floor_rel_mid": "중층부",
    "floor_rel_high": "고층부",
}


def relative_floor_group(floor: float, max_floor: float) -> str:
    """단지 내 max(층) 대비 백분위 구간 + 1층·최상층 독립."""
    if pd.isna(floor):
        return "floor_rel_mid"
    f = float(floor)
    mx = float(max_floor) if pd.notna(max_floor) and float(max_floor) > 0 else f
    if f == 1:
        return "floor_rel_1"
    if f == mx:
        return "floor_rel_top"
    ratio = f / mx if mx > 0 else 0.5
    if f > 1 and ratio <= 0.3:
        return "floor_rel_low"
    if 0.3 < ratio <= 0.7:
        return "floor_rel_mid"
    if ratio > 0.7 and f < mx:
        return "floor_rel_high"
    return "floor_rel_mid"


def _floor_group_label(floor: float) -> str:
    if floor <= 5:
        return "floor_grp_1-5"
    if floor <= 15:
        return "floor_grp_6-15"
    return "floor_grp_16+"


def _add_floor_columns(work: pd.DataFrame, mode: str) -> tuple[pd.DataFrame, dict[str, str]]:
    labels: dict[str, str] = {}
    if not work["floor"].notna().any():
        return pd.DataFrame(index=work.index), labels

    if mode == "linear":
        fl = work["floor"].astype(float).fillna(0)
        out = fl.to_frame("floor")
        labels["floor"] = "층(선형)"
        return out, labels

    fl = work["floor"].astype(float)

    if mode == "relative":
        max_floor = fl.max()
        grp = fl.apply(
            lambda x: relative_floor_group(x, max_floor) if pd.notna(x) else "floor_rel_mid"
        )
        dummies = pd.get_dummies(grp, prefix="", prefix_sep="", drop_first=True)
        for c in dummies.columns:
            base = _REL_FLOOR_LABELS.get(c, c)
            labels[c] = f"{base} (기준 대비)"
        return dummies, labels

    if mode == "grouped":
        grp = fl.apply(lambda x: _floor_group_label(x) if pd.notna(x) else "floor_grp_unknown")
        dummies = pd.get_dummies(grp, prefix="", prefix_sep="", drop_first=True)
    else:
        floor_str = fl.apply(
            lambda x: (
                str(int(x))
                if pd.notna(x) and float(x) == int(float(x))
                else (f"{float(x):g}" if pd.notna(x) else None)
            )
        )
        dummies = pd.get_dummies(floor_str, prefix="floor", drop_first=True)

    if dummies.empty:
        return pd.DataFrame(index=work.index), labels

    for c in dummies.columns:
        if c.startswith("floor_grp_"):
            labels[c] = c.replace("floor_grp_", "층 ") + " (기준 대비)"
        elif c.startswith("floor_rel_"):
            labels[c] = _REL_FLOOR_LABELS.get(c, c) + " (기준 대비)"
        else:
            labels[c] = f"층 {c.replace('floor_', '')} (기준 대비)"
    return dummies, labels


def run_building_regression(
    df: pd.DataFrame,
    building_key: str,
    display_name: str,
    req: CollectiveRegressionRequest,
) -> CollectiveRegressionResponse:
    warnings: list[str] = []
    if df.empty:
        return CollectiveRegressionResponse(
            building_key=building_key,
            display_name=display_name,
            n=0,
            warnings=["거래 표본 없음"],
        )

    work = df.copy()
    work = work.dropna(subset=["price"])
    if req.exclude_outliers_iqr and len(work) >= 4:
        up = work["unit_price"].astype(float)
        q1, q3 = up.quantile(0.25), up.quantile(0.75)
        iqr = q3 - q1
        mult = req.outlier_iqr_multiplier
        lo, hi = q1 - mult * iqr, q3 + mult * iqr
        work = work[(up >= lo) & (up <= hi)]

    n = len(work)
    if n < 5:
        return CollectiveRegressionResponse(
            building_key=building_key,
            display_name=display_name,
            n=n,
            warnings=[f"n={n} — 회귀 최소 표본 부족"],
        )

    y = work["price"].astype(float)
    parts: list[pd.DataFrame] = []
    labels: dict[str, str] = {"const": "절편"}

    if req.variables.exclusive_area:
        parts.append(work[["exclusive_area"]].astype(float).rename(columns={"exclusive_area": "exclusive_area"}))
        labels["exclusive_area"] = "전용면적"
    if req.variables.building_age:
        parts.append(work[["building_age"]].astype(float).rename(columns={"building_age": "building_age"}))
        labels["building_age"] = "연식"

    if req.variables.floor and work["floor"].notna().any():
        floor_part, floor_labels = _add_floor_columns(work, req.variables.floor_mode)
        if not floor_part.empty:
            parts.append(floor_part)
            labels.update(floor_labels)

    if req.variables.dong and work["dong"].notna().any():
        dummies = pd.get_dummies(work["dong"].astype(str).str.strip(), prefix="dong", drop_first=True)
        if not dummies.empty:
            parts.append(dummies)
            for c in dummies.columns:
                labels[c] = f"동 {c.replace('dong_', '')}"

    if not parts:
        return CollectiveRegressionResponse(
            building_key=building_key,
            display_name=display_name,
            n=n,
            warnings=["선택 변수 없음"],
        )

    X = pd.concat(parts, axis=1).astype(float)
    X = sm.add_constant(X, has_constant="add")
    try:
        model = sm.OLS(y, X, missing="drop").fit()
    except Exception as exc:
        return CollectiveRegressionResponse(
            building_key=building_key,
            display_name=display_name,
            n=n,
            warnings=[f"회귀 실패: {exc}"],
        )

    if n < 30:
        warnings.append(f"n={n} — 참고용 (권장 n≥30)")

    coefs: list[RegressionCoeff] = []
    for name in X.columns:
        if name not in model.params.index:
            continue
        coefs.append(
            RegressionCoeff(
                name=name,
                label=labels.get(name, name),
                coef=float(model.params[name]),
                se=float(model.bse[name]) if name in model.bse.index else None,
                t=float(model.tvalues[name]) if name in model.tvalues.index else None,
                p=float(model.pvalues[name]) if name in model.pvalues.index else None,
            )
        )

    return CollectiveRegressionResponse(
        building_key=building_key,
        display_name=display_name,
        n=int(model.nobs),
        r_squared=float(model.rsquared) if model.rsquared is not None else None,
        adj_r_squared=float(model.rsquared_adj) if model.rsquared_adj is not None else None,
        coefficients=coefs,
        warnings=warnings,
    )
