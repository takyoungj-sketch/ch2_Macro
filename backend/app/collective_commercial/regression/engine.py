"""집합상가·공장 cluster OLS 회귀 — 로그/선형 비교·예측구간."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
import statsmodels.api as sm

from app.collective.regression.engine import (
    _add_floor_columns,
    _build_model_comparison,
    _duan_smearing,
    _floor_row_for_predict,
)
from app.collective.schemas import ContinuousRange, RegressionCoeff
from app.collective_commercial.schemas import (
    ClusterFeOption,
    CommercialPredictOptions,
    CommercialRegressionPredictInputs,
    CommercialRegressionRequest,
    CommercialRegressionResponse,
)

MIN_CLUSTER_FE_GROUP = 5


@dataclass
class CommercialDesignMeta:
    floor_mode: str = "relative"
    max_floor: float | None = None
    floor_dummy_cols: list[str] = field(default_factory=list)
    continuous_ranges: dict[str, tuple[float | None, float | None]] = field(default_factory=dict)
    column_labels: dict[str, str] = field(default_factory=dict)
    zone_categories: list[str] = field(default_factory=list)
    zone_reference: str | None = None
    building_use_categories: list[str] = field(default_factory=list)
    building_use_reference: str | None = None
    road_width_categories: list[str] = field(default_factory=list)
    road_width_reference: str | None = None
    addr4_categories: list[str] = field(default_factory=list)
    addr4_reference: str | None = None
    cluster_counts: dict[str, int] = field(default_factory=dict)
    cluster_labels: dict[str, str] = field(default_factory=dict)
    cluster_reference_key: str | None = None
    cluster_fe_map: dict[str, str] = field(default_factory=dict)


def _add_cluster_fe_regression(
    work: pd.DataFrame,
    parts: list[pd.DataFrame],
    labels: dict[str, str],
    meta: CommercialDesignMeta,
    *,
    reference_key: str,
    cluster_display_names: dict[str, str] | None = None,
) -> None:
    if "cluster_key" not in work.columns:
        return
    keys = work["cluster_key"].astype(str)
    if keys.nunique() < 2:
        return
    names = cluster_display_names or {}
    meta.cluster_reference_key = reference_key
    for ck, cnt in work.groupby("cluster_key").size().items():
        ck_str = str(ck)
        meta.cluster_counts[ck_str] = int(cnt)
        meta.cluster_labels[ck_str] = names.get(ck_str, ck_str[:12])
    for ck in sorted(k for k in keys.unique() if k != reference_key):
        col = f"clst_{re.sub(r'[^a-zA-Z0-9]+', '_', str(ck))[:24]}"
        work[col] = (keys == ck).astype(float)
        if work[col].sum() >= MIN_CLUSTER_FE_GROUP:
            parts.append(work[[col]])
            nm = names.get(str(ck), str(ck)[:12])
            labels[col] = f"도로 {nm} (기준 대비)"
            meta.cluster_fe_map[str(ck)] = col


def _add_cat_dummies(
    work: pd.DataFrame,
    col: str,
    prefix: str,
    label_fn,
) -> tuple[pd.DataFrame, dict[str, str], str | None, list[str]]:
    if col not in work.columns or not work[col].notna().any():
        return pd.DataFrame(index=work.index), {}, None, []
    series = work[col].astype(str).str.strip()
    series = series.replace({"nan": pd.NA, "None": pd.NA, "": pd.NA})
    cats = sorted(c for c in series.dropna().unique() if c and c not in ("nan", "None"))
    if len(cats) < 2:
        return pd.DataFrame(index=work.index), {}, None, cats
    dummies = pd.get_dummies(series, prefix=prefix, drop_first=True)
    labels = {c: label_fn(c) for c in dummies.columns}
    return dummies, labels, cats[0], cats


def _add_time_dummies(work: pd.DataFrame, parts: list[pd.DataFrame], labels: dict[str, str]) -> None:
    if "contract_year" not in work.columns:
        return
    months = work["contract_month"] if "contract_month" in work.columns else pd.Series([None] * len(work))
    codes = []
    for y, m in zip(work["contract_year"], months):
        if y is None or pd.isna(y):
            codes.append(None)
            continue
        yi = int(y)
        if m is None or pd.isna(m):
            codes.append(f"{yi}")
        else:
            codes.append(f"{yi}H{1 if int(m) <= 6 else 2}")
    work["_period_code"] = codes
    counts = work["_period_code"].dropna().value_counts()
    if len(counts) < 2:
        return
    ref = str(counts.idxmax())
    for code, cnt in counts.items():
        if code == ref or cnt < 5:
            continue
        col = f"time_{code}"
        work[col] = (work["_period_code"] == code).astype(float)
        parts.append(work[[col]])
        labels[col] = f"거래시점 {code} (기준 대비)"


def _continuous_range(work: pd.DataFrame, col: str) -> tuple[float, float] | None:
    if col not in work.columns or not work[col].notna().any():
        return None
    s = work[col].astype(float)
    return float(s.min()), float(s.max())


def _prepare_work(df: pd.DataFrame, req: CommercialRegressionRequest) -> pd.DataFrame:
    work = df.copy()
    if "building_age" in work.columns and "building_year" in work.columns and "contract_year" in work.columns:
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
    cohort_mode: bool = False,
    cluster_display_names: dict[str, str] | None = None,
) -> tuple[pd.Series, pd.DataFrame, dict[str, str], CommercialDesignMeta, list[str]]:
    warnings: list[str] = []
    meta = CommercialDesignMeta(floor_mode=req.variables.floor_mode)
    labels: dict[str, str] = {"const": "절편"}
    parts: list[pd.DataFrame] = []

    if cohort_mode and "cluster_key" in work.columns and work["cluster_key"].nunique() > 1:
        ref_ck = str(work.groupby("cluster_key").size().idxmax())
        _add_cluster_fe_regression(
            work,
            parts,
            labels,
            meta,
            reference_key=ref_ck,
            cluster_display_names=cluster_display_names,
        )
        warnings.append(
            f"코호트 {work['cluster_key'].nunique()}개 도로 — cluster FE 적용 (기준: 거래 최다 도로)",
        )

    if req.variables.gross_area:
        parts.append(work[["gross_area"]].astype(float))
        labels["gross_area"] = "연면적"
        rng = _continuous_range(work, "gross_area")
        if rng:
            meta.continuous_ranges["gross_area"] = rng

    if req.variables.land_area and "land_area" in work.columns and work["land_area"].notna().any():
        land_vals = work["land_area"].astype(float)
        if (land_vals > 0).sum() >= 5:
            parts.append(land_vals.where(land_vals > 0).to_frame())
            labels["land_area"] = "대지면적"
            rng = _continuous_range(work, "land_area")
            if rng:
                meta.continuous_ranges["land_area"] = rng

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
        zone_part, zone_labels, zone_ref, zone_cats = _add_cat_dummies(
            work, "zone_type", "zone", lambda c: f"용도지역 {c.replace('zone_', '')} (기준 대비)"
        )
        if not zone_part.empty:
            parts.append(zone_part)
            labels.update(zone_labels)
            meta.zone_reference = zone_ref
            meta.zone_categories = zone_cats

    if req.variables.building_use:
        use_part, use_labels, use_ref, use_cats = _add_cat_dummies(
            work, "building_use", "use", lambda c: f"건축물용도 {c.replace('use_', '')} (기준 대비)"
        )
        if not use_part.empty:
            parts.append(use_part)
            labels.update(use_labels)
            meta.building_use_reference = use_ref
            meta.building_use_categories = use_cats

    if req.variables.road_width and is_shop:
        rw_part, rw_labels, rw_ref, rw_cats = _add_cat_dummies(
            work,
            "road_width_label",
            "roadw",
            lambda c: f"도로폭 {c.replace('roadw_', '')} (기준 대비)",
        )
        if not rw_part.empty:
            parts.append(rw_part)
            labels.update(rw_labels)
            meta.road_width_reference = rw_ref
            meta.road_width_categories = rw_cats

    if req.variables.addr4:
        addr_part, addr_labels, addr_ref, addr_cats = _add_cat_dummies(
            work, "addr4", "addr4", lambda c: f"동 {c.replace('addr4_', '')} (기준 대비)"
        )
        if not addr_part.empty:
            parts.append(addr_part)
            labels.update(addr_labels)
            meta.addr4_reference = addr_ref
            meta.addr4_categories = addr_cats

    _add_time_dummies(work, parts, labels)

    meta.column_labels = labels
    meta.floor_dummy_cols = floor_dummy_cols

    if not parts:
        empty_x = pd.DataFrame(index=work.index)
        return work["price"].astype(float), empty_x, labels, meta, warnings

    X = pd.concat(parts, axis=1).astype(float)
    y = work["price"].astype(float)
    return y, X, labels, meta, warnings


def _meta_to_predict_options(meta: CommercialDesignMeta, req: CommercialRegressionRequest) -> CommercialPredictOptions:
    opts = CommercialPredictOptions(floor_mode=req.variables.floor_mode, max_floor=meta.max_floor)

    for key, attr in [
        ("gross_area", "gross_area"),
        ("land_area", "land_area"),
        ("building_age", "building_age"),
        ("floor", "floor"),
        ("road_code", "road_code"),
    ]:
        if key in meta.continuous_ranges:
            lo, hi = meta.continuous_ranges[key]
            setattr(opts, attr, ContinuousRange(name=key, min=lo, max=hi))

    if req.variables.zone_type and meta.zone_categories:
        opts.zone_types = meta.zone_categories
        opts.zone_reference = meta.zone_reference
    if req.variables.building_use and meta.building_use_categories:
        opts.building_uses = meta.building_use_categories
        opts.building_use_reference = meta.building_use_reference
    if req.variables.road_width and meta.road_width_categories:
        opts.road_widths = meta.road_width_categories
        opts.road_width_reference = meta.road_width_reference
    if req.variables.addr4 and meta.addr4_categories:
        opts.addr4_list = meta.addr4_categories
        opts.addr4_reference = meta.addr4_reference

    if meta.cluster_reference_key:
        for ck, cnt in sorted(meta.cluster_counts.items(), key=lambda x: -x[1]):
            opts.clusters.append(
                ClusterFeOption(
                    cluster_key=ck,
                    display_label=meta.cluster_labels.get(ck, ck),
                    count=cnt,
                    is_reference=(ck == meta.cluster_reference_key),
                    has_fe=(ck in meta.cluster_fe_map),
                )
            )
    return opts


def _cat_predict_col(prefix: str, value: str, reference: str | None, row: dict[str, float]) -> None:
    if reference and value != reference:
        col = f"{prefix}_{value}"
        if col in row:
            row[col] = 1.0


def _inputs_to_x_row(
    X: pd.DataFrame,
    meta: CommercialDesignMeta,
    req: CommercialRegressionRequest,
    inputs: CommercialRegressionPredictInputs,
) -> pd.Series:
    row = {c: 0.0 for c in X.columns}

    if req.variables.gross_area and inputs.gross_area is not None:
        row["gross_area"] = float(inputs.gross_area)
    if req.variables.land_area and inputs.land_area is not None:
        row["land_area"] = float(inputs.land_area)
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

    if req.variables.zone_type and inputs.zone_type is not None:
        _cat_predict_col("zone", str(inputs.zone_type).strip(), meta.zone_reference, row)
    if req.variables.building_use and inputs.building_use is not None:
        _cat_predict_col("use", str(inputs.building_use).strip(), meta.building_use_reference, row)
    if req.variables.road_width and inputs.road_width is not None:
        _cat_predict_col("roadw", str(inputs.road_width).strip(), meta.road_width_reference, row)
    if req.variables.addr4 and inputs.addr4 is not None:
        _cat_predict_col("addr4", str(inputs.addr4).strip(), meta.addr4_reference, row)

    if inputs.cluster_key and meta.cluster_reference_key:
        ck = str(inputs.cluster_key)
        if ck != meta.cluster_reference_key and ck in meta.cluster_fe_map:
            col = meta.cluster_fe_map[ck]
            if col in row:
                row[col] = 1.0

    return pd.Series(row, index=X.columns)


def _extrapolation_warnings(
    meta: CommercialDesignMeta, inputs: CommercialRegressionPredictInputs
) -> list[str]:
    warns: list[str] = []
    for key, val in [
        ("gross_area", inputs.gross_area),
        ("land_area", inputs.land_area),
        ("building_age", inputs.building_age),
        ("floor", inputs.floor),
        ("road_code", inputs.road_code),
    ]:
        if val is None or key not in meta.continuous_ranges:
            continue
        lo, hi = meta.continuous_ranges[key]
        if lo is not None and val < lo:
            warns.append(f"{key}={val} — 표본 하한({lo}) 미만 (외삽)")
        if hi is not None and val > hi:
            warns.append(f"{key}={val} — 표본 상한({hi}) 초과 (외삽)")
    return warns


def _fit_regression(
    y: pd.Series,
    X: pd.DataFrame,
    labels: dict[str, str],
    meta: CommercialDesignMeta,
    req: CommercialRegressionRequest,
    base_warnings: list[str],
) -> tuple[sm.regression.linear_model.RegressionResultsWrapper | None, CommercialRegressionResponse]:
    if X.empty:
        return None, CommercialRegressionResponse(
            cluster_key="",
            display_label="",
            n=len(y),
            warnings=base_warnings + ["선택 변수 없음"],
        )

    X_const = sm.add_constant(X, has_constant="add")
    model_comparison = _build_model_comparison(y.astype(float), X_const)
    selected = req.model_type
    if model_comparison:
        if selected not in ("log", "linear") or (selected == "log" and (y <= 0).any()):
            selected = model_comparison.recommended
    else:
        selected = "linear"
    if selected == "log" and (y <= 0).any():
        selected = "linear"
        base_warnings = base_warnings + ["금액 0 이하 포함 — 선형 회귀로 전환"]

    y_fit = np.log(y.astype(float)) if selected == "log" else y.astype(float)

    try:
        model = sm.OLS(y_fit, X_const, missing="drop").fit(cov_type="HC3")
    except Exception as exc:
        return None, CommercialRegressionResponse(
            cluster_key="",
            display_label="",
            n=len(y),
            warnings=base_warnings + [f"회귀 실패: {exc}"],
        )

    warnings = list(base_warnings)
    n = int(model.nobs)
    if n < 30:
        warnings.append(f"n={n} — 참고용 (권장 n≥30)")

    dep_label = "ln(금액)" if selected == "log" else "금액(만원)"
    warnings.insert(0, f"종속변수: {dep_label} · HC3 강건 SE · 시점(반기) 통제 포함")

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

    predict_options = _meta_to_predict_options(meta, req)
    return model, CommercialRegressionResponse(
        cluster_key="",
        display_label="",
        n=n,
        model_type=selected,
        r_squared=float(model.rsquared) if model.rsquared is not None else None,
        adj_r_squared=float(model.rsquared_adj) if model.rsquared_adj is not None else None,
        coefficients=coefs,
        model_comparison=model_comparison,
        warnings=warnings,
        predict_options=predict_options,
    )


def _run_regression_core(
    df: pd.DataFrame,
    req: CommercialRegressionRequest,
    *,
    is_shop: bool,
    cohort_mode: bool = False,
    cluster_display_names: dict[str, str] | None = None,
) -> tuple[sm.regression.linear_model.RegressionResultsWrapper | None, pd.DataFrame, CommercialDesignMeta, CommercialRegressionResponse]:
    if df.empty:
        resp = CommercialRegressionResponse(
            cluster_key="",
            display_label="",
            n=0,
            warnings=["거래 표본 없음"],
        )
        return None, pd.DataFrame(), CommercialDesignMeta(), resp

    work = _prepare_work(df, req)
    n = len(work)
    if n < 5:
        resp = CommercialRegressionResponse(
            cluster_key="",
            display_label="",
            n=n,
            warnings=[f"n={n} — 회귀 최소 표본 부족"],
        )
        return None, pd.DataFrame(), CommercialDesignMeta(), resp

    y, X, labels, meta, fe_warnings = _build_design_matrix(
        work,
        req,
        is_shop=is_shop,
        cohort_mode=cohort_mode,
        cluster_display_names=cluster_display_names,
    )
    model, resp = _fit_regression(y, X, labels, meta, req, fe_warnings)
    return model, X, meta, resp


def run_commercial_regression(
    df: pd.DataFrame,
    cluster_key: str,
    display_label: str,
    req: CommercialRegressionRequest,
    *,
    is_shop: bool,
    cohort_mode: bool = False,
    cluster_display_names: dict[str, str] | None = None,
) -> CommercialRegressionResponse:
    _, _, _, resp = _run_regression_core(
        df,
        req,
        is_shop=is_shop,
        cohort_mode=cohort_mode,
        cluster_display_names=cluster_display_names,
    )
    resp.cluster_key = cluster_key
    resp.display_label = display_label
    return resp


def predict_commercial_regression(
    df: pd.DataFrame,
    req: CommercialRegressionRequest,
    inputs: CommercialRegressionPredictInputs,
    *,
    is_shop: bool,
    cohort_mode: bool = False,
    cluster_display_names: dict[str, str] | None = None,
) -> dict:
    model, X, meta, fit_resp = _run_regression_core(
        df,
        req,
        is_shop=is_shop,
        cohort_mode=cohort_mode,
        cluster_display_names=cluster_display_names,
    )
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

    model_type = fit_resp.model_type or "linear"
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
