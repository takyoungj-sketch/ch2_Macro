"""집합상가·공장 cluster OLS 회귀 + 예측."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
import statsmodels.api as sm

from app.collective.regression.engine import (
    _add_floor_columns,
    _duan_smearing,
    _floor_row_for_predict,
    count_significant_coefficients,
    fit_model_price_metrics,
)
from app.collective.regression.presentation import enrich_regression_response
from app.collective.schemas import ContinuousRange
from app.collective_commercial.schemas import (
    CommercialPredictOptions,
    CommercialRegressionPredictInputs,
    CommercialRegressionRequest,
    CommercialRegressionResponse,
    RegressionCoeff,
)


@dataclass
class CommercialRegressionDesignMeta:
    floor_mode: str = "relative"
    max_floor: float | None = None
    floor_dummy_cols: list[str] = field(default_factory=list)
    continuous_ranges: dict[str, tuple[float, float]] = field(default_factory=dict)
    column_labels: dict[str, str] = field(default_factory=dict)
    zone_categories: list[str] = field(default_factory=list)
    zone_reference: str | None = None
    building_use_categories: list[str] = field(default_factory=list)
    building_use_reference: str | None = None
    road_width_categories: list[str] = field(default_factory=list)
    road_width_reference: str | None = None


def _add_cat_dummies(
    work: pd.DataFrame,
    col: str,
    prefix: str,
    label_fn,
) -> tuple[pd.DataFrame, dict[str, str], list[str], str | None]:
    if col not in work.columns or not work[col].notna().any():
        return pd.DataFrame(index=work.index), {}, [], None
    series = work[col].astype(str).str.strip()
    series = series.replace({"nan": pd.NA, "None": pd.NA, "": pd.NA})
    cats = sorted(c for c in series.dropna().unique() if c and c not in ("nan", "None"))
    if len(cats) < 2:
        return pd.DataFrame(index=work.index), {}, [], None
    dummies = pd.get_dummies(series, prefix=prefix, drop_first=True)
    labels = {c: label_fn(c) for c in dummies.columns}
    return dummies, labels, cats, cats[0]


def _continuous_range(work: pd.DataFrame, col: str) -> tuple[float, float] | None:
    if col not in work.columns or not work[col].notna().any():
        return None
    s = work[col].astype(float)
    return float(s.min()), float(s.max())


def _prepare_work(df: pd.DataFrame, req: CommercialRegressionRequest) -> pd.DataFrame:
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
    return work


def _build_design_matrix(
    work: pd.DataFrame,
    req: CommercialRegressionRequest,
    *,
    is_shop: bool,
) -> tuple[pd.Series, pd.DataFrame, dict[str, str], CommercialRegressionDesignMeta, list[str]]:
    warnings: list[str] = []
    meta = CommercialRegressionDesignMeta(floor_mode=req.variables.floor_mode)
    labels: dict[str, str] = {"const": "절편"}
    parts: list[pd.DataFrame] = []

    if req.variables.gross_area:
        parts.append(work[["gross_area"]].astype(float))
        labels["gross_area"] = "연면적"
        rng = _continuous_range(work, "gross_area")
        if rng:
            meta.continuous_ranges["gross_area"] = rng

    if req.variables.building_age and work["building_age"].notna().any():
        parts.append(work[["building_age"]].astype(float))
        labels["building_age"] = "연식"
        rng = _continuous_range(work, "building_age")
        if rng:
            meta.continuous_ranges["building_age"] = rng

    if req.variables.road_code and not is_shop and work["road_code"].notna().any():
        parts.append(work[["road_code"]].astype(float))
        labels["road_code"] = "도로폭(m)"
        rng = _continuous_range(work, "road_code")
        if rng:
            meta.continuous_ranges["road_code"] = rng

    floor_dummy_cols: list[str] = []
    if req.variables.floor and work["floor"].notna().any():
        meta.max_floor = float(work["floor"].astype(float).max())
        floor_part, floor_labels, floor_dummy_cols = _add_floor_columns(
            work, req.variables.floor_mode, max_floor=meta.max_floor
        )
        if not floor_part.empty:
            parts.append(floor_part)
            labels.update(floor_labels)
        rng = _continuous_range(work, "floor")
        if rng:
            meta.continuous_ranges["floor"] = rng

    if req.variables.zone_type:
        zone_part, zone_labels, zone_cats, zone_ref = _add_cat_dummies(
            work, "zone_type", "zone", lambda c: f"용도지역 {c.replace('zone_', '')} (기준 대비)"
        )
        if not zone_part.empty:
            parts.append(zone_part)
            labels.update(zone_labels)
            meta.zone_categories = zone_cats
            meta.zone_reference = zone_ref

    if req.variables.building_use:
        use_part, use_labels, use_cats, use_ref = _add_cat_dummies(
            work, "building_use", "use", lambda c: f"건축물용도 {c.replace('use_', '')} (기준 대비)"
        )
        if not use_part.empty:
            parts.append(use_part)
            labels.update(use_labels)
            meta.building_use_categories = use_cats
            meta.building_use_reference = use_ref

    if req.variables.road_width and is_shop:
        rw_part, rw_labels, rw_cats, rw_ref = _add_cat_dummies(
            work,
            "road_width_label",
            "roadw",
            lambda c: f"도로폭 {c.replace('roadw_', '')} (기준 대비)",
        )
        if not rw_part.empty:
            parts.append(rw_part)
            labels.update(rw_labels)
            meta.road_width_categories = rw_cats
            meta.road_width_reference = rw_ref

    meta.column_labels = labels
    meta.floor_dummy_cols = floor_dummy_cols

    if not parts:
        empty_x = pd.DataFrame(index=work.index)
        return work["price"].astype(float), empty_x, labels, meta, warnings

    X = pd.concat(parts, axis=1).astype(float)
    y = work["price"].astype(float)
    return y, X, labels, meta, warnings


def _meta_to_predict_options(
    meta: CommercialRegressionDesignMeta,
    req: CommercialRegressionRequest,
) -> CommercialPredictOptions:
    opts = CommercialPredictOptions(floor_mode=req.variables.floor_mode, max_floor=meta.max_floor)

    if req.variables.gross_area and "gross_area" in meta.continuous_ranges:
        lo, hi = meta.continuous_ranges["gross_area"]
        opts.gross_area = ContinuousRange(name="gross_area", min=lo, max=hi)
    if req.variables.building_age and "building_age" in meta.continuous_ranges:
        lo, hi = meta.continuous_ranges["building_age"]
        opts.building_age = ContinuousRange(name="building_age", min=lo, max=hi)
    if req.variables.floor and "floor" in meta.continuous_ranges:
        lo, hi = meta.continuous_ranges["floor"]
        opts.floor = ContinuousRange(name="floor", min=lo, max=hi)
    if req.variables.road_code and "road_code" in meta.continuous_ranges:
        lo, hi = meta.continuous_ranges["road_code"]
        opts.road_code = ContinuousRange(name="road_code", min=lo, max=hi)

    if req.variables.zone_type and meta.zone_categories:
        opts.zone_types = meta.zone_categories
        opts.zone_type_reference = meta.zone_reference
    if req.variables.building_use and meta.building_use_categories:
        opts.building_uses = meta.building_use_categories
        opts.building_use_reference = meta.building_use_reference
    if req.variables.road_width and meta.road_width_categories:
        opts.road_width_labels = meta.road_width_categories
        opts.road_width_reference = meta.road_width_reference

    return opts


def _extrapolation_warnings(
    meta: CommercialRegressionDesignMeta,
    inputs: CommercialRegressionPredictInputs,
) -> list[str]:
    warns: list[str] = []
    labels = {
        "gross_area": "연면적",
        "building_age": "연식",
        "floor": "층",
        "road_code": "도로폭(m)",
    }
    for key, val in [
        ("gross_area", inputs.gross_area),
        ("building_age", inputs.building_age),
        ("floor", inputs.floor),
        ("road_code", inputs.road_code),
    ]:
        if val is None or key not in meta.continuous_ranges:
            continue
        lo, hi = meta.continuous_ranges[key]
        label = labels.get(key, key)
        if val < lo:
            warns.append(f"{label}={val} — 표본 하한({lo}) 미만 (외삽)")
        if val > hi:
            warns.append(f"{label}={val} — 표본 상한({hi}) 초과 (외삽)")
    return warns


def _cat_predict_col(prefix: str, value: str | None, reference: str | None) -> str | None:
    if value is None or reference is None:
        return None
    val = str(value).strip()
    if not val or val == reference:
        return None
    return f"{prefix}_{val}"


def _inputs_to_x_row(
    X: pd.DataFrame,
    meta: CommercialRegressionDesignMeta,
    req: CommercialRegressionRequest,
    inputs: CommercialRegressionPredictInputs,
) -> pd.Series:
    row = {c: 0.0 for c in X.columns}
    if req.variables.gross_area and inputs.gross_area is not None:
        row["gross_area"] = float(inputs.gross_area)
    if req.variables.building_age and inputs.building_age is not None:
        row["building_age"] = float(inputs.building_age)
    if req.variables.road_code and inputs.road_code is not None:
        row["road_code"] = float(inputs.road_code)

    if req.variables.floor and meta.floor_dummy_cols:
        mx = float(meta.max_floor or inputs.floor or 1)
        floor_vals = _floor_row_for_predict(inputs.floor, req.variables.floor_mode, mx, meta.floor_dummy_cols)
        for c, v in floor_vals.items():
            if c in row:
                row[c] = v

    zone_col = _cat_predict_col("zone", inputs.zone_type, meta.zone_reference)
    if zone_col and zone_col in row:
        row[zone_col] = 1.0

    use_col = _cat_predict_col("use", inputs.building_use, meta.building_use_reference)
    if use_col and use_col in row:
        row[use_col] = 1.0

    rw_col = _cat_predict_col("roadw", inputs.road_width_label, meta.road_width_reference)
    if rw_col and rw_col in row:
        row[rw_col] = 1.0

    return pd.Series(row, index=X.columns)


def _run_regression_core(
    df: pd.DataFrame,
    req: CommercialRegressionRequest,
    *,
    is_shop: bool,
) -> tuple[sm.regression.linear_model.RegressionResultsWrapper | None, pd.DataFrame, CommercialRegressionDesignMeta, CommercialRegressionResponse]:
    if df.empty:
        resp = CommercialRegressionResponse(
            cluster_key="",
            display_label="",
            n=0,
            warnings=["거래 표본 없음"],
        )
        return None, pd.DataFrame(), CommercialRegressionDesignMeta(), resp

    work = _prepare_work(df, req)
    n = len(work)
    if n < 5:
        resp = CommercialRegressionResponse(
            cluster_key="",
            display_label="",
            n=n,
            warnings=[f"n={n} — 회귀 최소 표본 부족"],
        )
        return None, pd.DataFrame(), CommercialRegressionDesignMeta(), resp

    y, X, labels, meta, base_warnings = _build_design_matrix(work, req, is_shop=is_shop)
    if X.empty:
        resp = CommercialRegressionResponse(
            cluster_key="",
            display_label="",
            n=n,
            warnings=base_warnings + ["선택 변수 없음"],
        )
        return None, pd.DataFrame(), meta, resp

    X_const = sm.add_constant(X, has_constant="add")

    warnings = list(base_warnings)
    model_type = req.model_type
    if model_type == "log" and (y <= 0).any():
        warnings.append("price≤0 거래가 있어 선형모델로 대체")
        model_type = "linear"
    y_fit = np.log(y) if model_type == "log" else y
    try:
        model = sm.OLS(y_fit, X_const, missing="drop").fit()
    except Exception as exc:
        resp = CommercialRegressionResponse(
            cluster_key="",
            display_label="",
            n=n,
            warnings=warnings + [f"회귀 실패: {exc}"],
        )
        return None, X, meta, resp

    if int(model.nobs) < 30:
        warnings.append(f"n={int(model.nobs)} — 참고용 (권장 n≥30)")

    metrics = fit_model_price_metrics(y, X_const, model, model_type)

    coefs: list[RegressionCoeff] = []
    for name in X_const.columns:
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

    equation, enriched, price_adj = enrich_regression_response(
        coefs,
        model_type=model_type,
        price_adj_r_squared=metrics.get("price_adj_r_squared"),
    )
    coefs = [RegressionCoeff(**row) for row in enriched]
    sig_count = count_significant_coefficients(coefs)

    predict_options = _meta_to_predict_options(meta, req)
    resp = CommercialRegressionResponse(
        cluster_key="",
        display_label="",
        n=int(model.nobs),
        model_type=model_type,
        r_squared=float(model.rsquared) if model.rsquared is not None else None,
        adj_r_squared=float(model.rsquared_adj) if model.rsquared_adj is not None else None,
        price_adj_r_squared=price_adj,
        mape=metrics.get("mape"),
        f_p_value=float(model.f_pvalue) if model.f_pvalue is not None else None,
        significant_count=sig_count,
        equation=equation,
        coefficients=coefs,
        warnings=warnings,
        predict_options=predict_options,
        model_comparison=None,
    )
    return model, X, meta, resp


def run_commercial_regression(
    df: pd.DataFrame,
    cluster_key: str,
    display_label: str,
    req: CommercialRegressionRequest,
    *,
    is_shop: bool,
) -> CommercialRegressionResponse:
    model, _, _, resp = _run_regression_core(df, req, is_shop=is_shop)
    if model is None:
        return resp.model_copy(update={"cluster_key": cluster_key, "display_label": display_label})
    return resp.model_copy(update={"cluster_key": cluster_key, "display_label": display_label})


def predict_commercial_regression(
    df: pd.DataFrame,
    req: CommercialRegressionRequest,
    inputs: CommercialRegressionPredictInputs,
    *,
    is_shop: bool,
) -> dict:
    model, X, meta, fit_resp = _run_regression_core(df, req, is_shop=is_shop)
    if model is None or X.empty:
        raise ValueError("; ".join(fit_resp.warnings) or "예측 불가 — 회귀 미추정")

    x_row = _inputs_to_x_row(X, meta, req, inputs)
    vals: dict[str, float] = {"const": 1.0}
    vals.update(x_row.to_dict())
    x_df = pd.DataFrame([vals]).reindex(columns=model.params.index, fill_value=0.0)
    frame = model.get_prediction(x_df).summary_frame(alpha=0.05)
    row = frame.iloc[0]

    warnings = _extrapolation_warnings(meta, inputs)
    if fit_resp.n < 30:
        warnings.insert(0, f"n={fit_resp.n} — 참고용 (권장 n≥30, 예측구간 넓음)")

    model_type = fit_resp.model_type
    if model_type == "log":
        duan = _duan_smearing(model.resid)
        y_hat = float(np.exp(float(row["mean"])) * duan)
        pi_lower = float(np.exp(float(row["obs_ci_lower"])))
        pi_upper = float(np.exp(float(row["obs_ci_upper"])))
        ci_lower = float(np.exp(float(row["mean_ci_lower"])) * duan)
        ci_upper = float(np.exp(float(row["mean_ci_upper"])) * duan)
    else:
        y_hat = float(row["mean"])
        pi_lower = float(row["obs_ci_lower"])
        pi_upper = float(row["obs_ci_upper"])
        ci_lower = float(row["mean_ci_lower"])
        ci_upper = float(row["mean_ci_upper"])

    gross = inputs.gross_area
    unit_hat = round(y_hat / float(gross), 2) if gross and float(gross) > 0 else None

    return {
        "n": fit_resp.n,
        "model_type": model_type,
        "y_hat": round(y_hat, 1),
        "pi_lower": round(pi_lower, 1),
        "pi_upper": round(pi_upper, 1),
        "ci_lower": round(ci_lower, 1),
        "ci_upper": round(ci_upper, 1),
        "unit_price_hat": unit_hat,
        "warnings": warnings,
    }
