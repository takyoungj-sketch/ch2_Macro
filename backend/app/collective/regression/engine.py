"""단일 건물 OLS — 층·동 더미."""

from __future__ import annotations

import pandas as pd
import statsmodels.api as sm

from app.collective.schemas import (
    CollectiveRegressionRequest,
    CollectiveRegressionResponse,
    RegressionCoeff,
)


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
        fl = work["floor"].astype(float).fillna(0)
        parts.append(fl.to_frame("floor"))
        labels["floor"] = "층"

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
