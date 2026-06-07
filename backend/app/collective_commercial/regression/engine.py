"""집합상가·공장 cluster OLS 회귀."""

from __future__ import annotations

import pandas as pd
import statsmodels.api as sm

from app.collective.regression.engine import _add_floor_columns
from app.collective_commercial.schemas import (
    CommercialRegressionRequest,
    CommercialRegressionResponse,
    RegressionCoeff,
)


def _add_cat_dummies(
    work: pd.DataFrame,
    col: str,
    prefix: str,
    label_fn,
) -> tuple[pd.DataFrame, dict[str, str]]:
    if col not in work.columns or not work[col].notna().any():
        return pd.DataFrame(index=work.index), {}
    series = work[col].astype(str).str.strip()
    series = series.replace({"nan": pd.NA, "None": pd.NA, "": pd.NA})
    if series.dropna().nunique() < 2:
        return pd.DataFrame(index=work.index), {}
    dummies = pd.get_dummies(series, prefix=prefix, drop_first=True)
    labels = {c: label_fn(c) for c in dummies.columns}
    return dummies, labels


def run_commercial_regression(
    df: pd.DataFrame,
    cluster_key: str,
    display_label: str,
    req: CommercialRegressionRequest,
    *,
    is_shop: bool,
) -> CommercialRegressionResponse:
    warnings: list[str] = []
    if df.empty:
        return CommercialRegressionResponse(
            cluster_key=cluster_key,
            display_label=display_label,
            n=0,
            warnings=["거래 표본 없음"],
        )

    work = df.copy()
    mask = work["building_age"].isna() & work["building_year"].notna() & work["contract_year"].notna()
    work.loc[mask, "building_age"] = (
        work.loc[mask, "contract_year"].astype(float) - work.loc[mask, "building_year"].astype(float)
    )

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
        return CommercialRegressionResponse(
            cluster_key=cluster_key,
            display_label=display_label,
            n=n,
            warnings=[f"n={n} — 회귀 최소 표본 부족"],
        )

    y = work["price"].astype(float)
    parts: list[pd.DataFrame] = []
    labels: dict[str, str] = {"const": "절편"}

    if req.variables.gross_area:
        parts.append(work[["gross_area"]].astype(float))
        labels["gross_area"] = "연면적"
    if req.variables.land_area and "land_area" in work.columns and work["land_area"].notna().any():
        land_vals = work["land_area"].astype(float)
        if (land_vals > 0).sum() >= 5:
            parts.append(land_vals.where(land_vals > 0).to_frame())
            labels["land_area"] = "대지면적"
    if req.variables.building_age and work["building_age"].notna().any():
        parts.append(work[["building_age"]].astype(float))
        labels["building_age"] = "연식"
    if req.variables.road_code and not is_shop and work["road_code"].notna().any():
        parts.append(work[["road_code"]].astype(float))
        labels["road_code"] = "도로폭(m)"

    if req.variables.floor and work["floor"].notna().any():
        floor_part, floor_labels = _add_floor_columns(work, req.variables.floor_mode)
        if not floor_part.empty:
            parts.append(floor_part)
            labels.update(floor_labels)

    if req.variables.zone_type:
        zone_part, zone_labels = _add_cat_dummies(
            work, "zone_type", "zone", lambda c: f"용도지역 {c.replace('zone_', '')} (기준 대비)"
        )
        if not zone_part.empty:
            parts.append(zone_part)
            labels.update(zone_labels)

    if req.variables.building_use:
        use_part, use_labels = _add_cat_dummies(
            work, "building_use", "use", lambda c: f"건축물용도 {c.replace('use_', '')} (기준 대비)"
        )
        if not use_part.empty:
            parts.append(use_part)
            labels.update(use_labels)

    if req.variables.road_width and is_shop:
        rw_part, rw_labels = _add_cat_dummies(
            work,
            "road_width_label",
            "roadw",
            lambda c: f"도로폭 {c.replace('roadw_', '')} (기준 대비)",
        )
        if not rw_part.empty:
            parts.append(rw_part)
            labels.update(rw_labels)

    if req.variables.addr4:
        addr_part, addr_labels = _add_cat_dummies(
            work, "addr4", "addr4", lambda c: f"동 {c.replace('addr4_', '')} (기준 대비)"
        )
        if not addr_part.empty:
            parts.append(addr_part)
            labels.update(addr_labels)

    if not parts:
        return CommercialRegressionResponse(
            cluster_key=cluster_key,
            display_label=display_label,
            n=n,
            warnings=["선택 변수 없음"],
        )

    X = pd.concat(parts, axis=1).astype(float)
    X = sm.add_constant(X, has_constant="add")
    try:
        model = sm.OLS(y, X, missing="drop").fit()
    except Exception as exc:
        return CommercialRegressionResponse(
            cluster_key=cluster_key,
            display_label=display_label,
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

    return CommercialRegressionResponse(
        cluster_key=cluster_key,
        display_label=display_label,
        n=int(model.nobs),
        r_squared=float(model.rsquared) if model.rsquared is not None else None,
        adj_r_squared=float(model.rsquared_adj) if model.rsquared_adj is not None else None,
        coefficients=coefs,
        warnings=warnings,
    )
