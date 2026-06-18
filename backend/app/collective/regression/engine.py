"""단일·코호트 OLS — 층·동 더미, 단지 FE, 예측."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import pandas as pd
import statsmodels.api as sm

from app.collective.schemas import (
    BuildingFeOption,
    CollectivePredictOptions,
    CollectiveRegressionPredictInputs,
    CollectiveRegressionRequest,
    CollectiveRegressionResponse,
    ContinuousRange,
    RegressionCoeff,
)

MIN_BUILDING_FE_GROUP = 5

# 상대 층(단지 max 층 대비)
_REL_FLOOR_LABELS: dict[str, str] = {
    "floor_rel_1": "1층",
    "floor_rel_top": "최상층",
    "floor_rel_low": "저층부",
    "floor_rel_mid": "중층부",
    "floor_rel_high": "고층부",
}


def relative_floor_group(floor: float, max_floor: float) -> str:
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


def _sanitize_key(key: str, prefix: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "_", str(key).strip())[:40]
    return f"{prefix}_{s}" if s else f"{prefix}_unknown"


@dataclass
class RegressionDesignMeta:
    column_labels: dict[str, str] = field(default_factory=dict)
    floor_mode: str = "relative"
    max_floor: float | None = None
    dong_reference: str | None = None
    dong_categories: list[str] = field(default_factory=list)
    housing_subtype_reference: str | None = None
    housing_subtype_categories: list[str] = field(default_factory=list)
    building_reference_key: str | None = None
    building_fe_map: dict[str, str] = field(default_factory=dict)  # building_key -> col
    building_labels: dict[str, str] = field(default_factory=dict)
    building_counts: dict[str, int] = field(default_factory=dict)
    continuous_ranges: dict[str, tuple[float | None, float | None]] = field(default_factory=dict)
    floor_dummy_cols: list[str] = field(default_factory=list)


def _add_floor_columns(
    work: pd.DataFrame,
    mode: str,
    *,
    max_floor: float | None = None,
) -> tuple[pd.DataFrame, dict[str, str], list[str]]:
    """Returns dummies, labels, dummy column names (excl. reference)."""
    labels: dict[str, str] = {}
    if not work["floor"].notna().any():
        return pd.DataFrame(index=work.index), labels, []

    if mode == "linear":
        fl = work["floor"].astype(float).fillna(0)
        out = fl.to_frame("floor")
        labels["floor"] = "층(선형)"
        return out, labels, ["floor"]

    fl = work["floor"].astype(float)

    if mode == "relative":
        mx = float(max_floor if max_floor is not None else fl.max())
        grp = fl.apply(lambda x: relative_floor_group(x, mx) if pd.notna(x) else "floor_rel_mid")
        dummies = pd.get_dummies(grp, prefix="", prefix_sep="", drop_first=True)
        dummy_cols = list(dummies.columns)
        for c in dummies.columns:
            base = _REL_FLOOR_LABELS.get(c, c)
            labels[c] = f"{base} (기준 대비)"
        return dummies, labels, dummy_cols

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

    dummy_cols = list(dummies.columns)
    if dummies.empty:
        return pd.DataFrame(index=work.index), labels, []

    for c in dummies.columns:
        if c.startswith("floor_grp_"):
            labels[c] = c.replace("floor_grp_", "층 ") + " (기준 대비)"
        elif c.startswith("floor_rel_"):
            labels[c] = _REL_FLOOR_LABELS.get(c, c) + " (기준 대비)"
        else:
            labels[c] = f"층 {c.replace('floor_', '')} (기준 대비)"
    return dummies, labels, dummy_cols


def _floor_row_for_predict(
    floor: float | None,
    mode: str,
    max_floor: float,
    dummy_cols: list[str],
) -> dict[str, float]:
    out = {c: 0.0 for c in dummy_cols}
    if floor is None or pd.isna(floor):
        return out
    f = float(floor)
    if mode == "linear":
        if "floor" in out:
            out["floor"] = f
        return out
    if mode == "relative":
        code = relative_floor_group(f, max_floor)
        if code in out:
            out[code] = 1.0
        return out
    if mode == "grouped":
        grp = _floor_group_label(f)
        if grp in out:
            out[grp] = 1.0
        return out
    key = str(int(f)) if f == int(f) else f"{f:g}"
    col = f"floor_{key}"
    if col in out:
        out[col] = 1.0
    return out


def _prepare_work(df: pd.DataFrame, req: CollectiveRegressionRequest) -> pd.DataFrame:
    work = df.copy()
    work = work.dropna(subset=["price"])
    if req.exclude_outliers_iqr and len(work) >= 4:
        up = work["unit_price"].astype(float)
        q1, q3 = up.quantile(0.25), up.quantile(0.75)
        iqr = q3 - q1
        mult = req.outlier_iqr_multiplier
        lo, hi = q1 - mult * iqr, q3 + mult * iqr
        work = work[(up >= lo) & (up <= hi)]
    return work


def _continuous_range(work: pd.DataFrame, col: str) -> ContinuousRange | None:
    if col not in work.columns or not work[col].notna().any():
        return None
    s = work[col].astype(float)
    return ContinuousRange(name=col, min=float(s.min()), max=float(s.max()))


def _build_design_matrix(
    work: pd.DataFrame,
    req: CollectiveRegressionRequest,
    *,
    cohort_mode: bool = False,
    building_display_names: dict[str, str] | None = None,
) -> tuple[pd.Series, pd.DataFrame, dict[str, str], RegressionDesignMeta, list[str]]:
    warnings: list[str] = []
    meta = RegressionDesignMeta(floor_mode=req.variables.floor_mode)
    labels: dict[str, str] = {"const": "절편"}
    parts: list[pd.DataFrame] = []

    display_names = building_display_names or {}
    if "building_key" in work.columns:
        for bk, cnt in work.groupby("building_key").size().items():
            meta.building_counts[str(bk)] = int(cnt)
            meta.building_labels[str(bk)] = display_names.get(str(bk), str(bk))

    if cohort_mode and "building_key" in work.columns and work["building_key"].nunique() > 1:
        keys = work["building_key"].astype(str)
        ref = str(work.groupby("building_key").size().idxmax())
        meta.building_reference_key = ref
        ref_name = meta.building_labels.get(ref, ref[:12])
        warnings.append(f"단지 FE 기준: {ref_name} (거래 최다)")
        for bk in sorted(keys.unique()):
            if bk == ref:
                continue
            cnt = meta.building_counts.get(bk, 0)
            bk_name = meta.building_labels.get(bk, bk[:12])
            if cnt < MIN_BUILDING_FE_GROUP:
                warnings.append(f"단지 FE 제외 — {bk_name} n={cnt} (최소 {MIN_BUILDING_FE_GROUP}건)")
                continue
            col = _sanitize_key(bk, "bld")
            work[col] = (keys == bk).astype(float)
            parts.append(work[[col]])
            labels[col] = f"단지 {bk_name}"
            meta.building_fe_map[bk] = col

    if req.variables.exclusive_area:
        parts.append(work[["exclusive_area"]].astype(float))
        labels["exclusive_area"] = "전용면적"
        rng = _continuous_range(work, "exclusive_area")
        if rng:
            meta.continuous_ranges["exclusive_area"] = (rng.min, rng.max)

    if req.variables.building_age:
        parts.append(work[["building_age"]].astype(float))
        labels["building_age"] = "연식"
        rng = _continuous_range(work, "building_age")
        if rng:
            meta.continuous_ranges["building_age"] = (rng.min, rng.max)

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
            meta.continuous_ranges["floor"] = (rng.min, rng.max)

    if req.variables.dong and "dong" in work.columns and work["dong"].notna().any():
        series = work["dong"].astype(str).str.strip()
        cats = sorted(c for c in series.dropna().unique() if c and c not in ("nan", "None"))
        if len(cats) >= 2:
            meta.dong_categories = cats
            meta.dong_reference = cats[0]
            dummies = pd.get_dummies(series, prefix="dong", drop_first=True)
            if not dummies.empty:
                parts.append(dummies)
                for c in dummies.columns:
                    labels[c] = f"동 {c.replace('dong_', '')}"

    if (
        req.variables.housing_subtype
        and "housing_subtype" in work.columns
        and work["housing_subtype"].notna().any()
    ):
        series = work["housing_subtype"].astype(str).str.strip()
        cats = sorted(c for c in series.dropna().unique() if c and c not in ("nan", "None"))
        if len(cats) >= 2:
            meta.housing_subtype_categories = cats
            meta.housing_subtype_reference = cats[0]
            dummies = pd.get_dummies(series, prefix="rights", drop_first=True)
            if not dummies.empty:
                parts.append(dummies)
                for c in dummies.columns:
                    labels[c] = f"권리 {c.replace('rights_', '')}"

    meta.column_labels = labels
    meta.floor_dummy_cols = floor_dummy_cols

    if not parts:
        empty_x = pd.DataFrame(index=work.index)
        return work["price"].astype(float), empty_x, labels, meta, warnings

    X = pd.concat(parts, axis=1).astype(float)
    y = work["price"].astype(float)
    return y, X, labels, meta, warnings


def _meta_to_predict_options(meta: RegressionDesignMeta, req: CollectiveRegressionRequest) -> CollectivePredictOptions:
    opts = CollectivePredictOptions(floor_mode=req.variables.floor_mode, max_floor=meta.max_floor)

    if req.variables.exclusive_area and "exclusive_area" in meta.continuous_ranges:
        lo, hi = meta.continuous_ranges["exclusive_area"]
        opts.exclusive_area = ContinuousRange(name="exclusive_area", min=lo, max=hi)
    if req.variables.building_age and "building_age" in meta.continuous_ranges:
        lo, hi = meta.continuous_ranges["building_age"]
        opts.building_age = ContinuousRange(name="building_age", min=lo, max=hi)
    if req.variables.floor and "floor" in meta.continuous_ranges:
        lo, hi = meta.continuous_ranges["floor"]
        opts.floor = ContinuousRange(name="floor", min=lo, max=hi)

    if req.variables.dong and meta.dong_categories:
        opts.dongs = meta.dong_categories
        opts.dong_reference = meta.dong_reference

    if req.variables.housing_subtype and meta.housing_subtype_categories:
        opts.housing_subtypes = meta.housing_subtype_categories
        opts.housing_subtype_reference = meta.housing_subtype_reference

    if meta.building_reference_key:
        for bk, cnt in sorted(meta.building_counts.items(), key=lambda x: -x[1]):
            opts.buildings.append(
                BuildingFeOption(
                    building_key=bk,
                    display_name=meta.building_labels.get(bk, bk),
                    count=cnt,
                    is_reference=(bk == meta.building_reference_key),
                    has_fe=(bk in meta.building_fe_map),
                )
            )
    return opts


def _fit_regression(
    y: pd.Series,
    X: pd.DataFrame,
    labels: dict[str, str],
    meta: RegressionDesignMeta,
    req: CollectiveRegressionRequest,
    base_warnings: list[str],
) -> tuple[sm.regression.linear_model.RegressionResultsWrapper | None, CollectiveRegressionResponse]:
    if X.empty:
        return None, CollectiveRegressionResponse(
            building_key="",
            display_name="",
            n=len(y),
            warnings=base_warnings + ["선택 변수 없음"],
        )

    X_const = sm.add_constant(X, has_constant="add")
    try:
        model = sm.OLS(y, X_const, missing="drop").fit()
    except Exception as exc:
        return None, CollectiveRegressionResponse(
            building_key="",
            display_name="",
            n=len(y),
            warnings=base_warnings + [f"회귀 실패: {exc}"],
        )

    warnings = list(base_warnings)
    if int(model.nobs) < 30:
        warnings.append(f"n={int(model.nobs)} — 참고용 (권장 n≥30)")

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
    return model, CollectiveRegressionResponse(
        building_key="",
        display_name="",
        n=int(model.nobs),
        r_squared=float(model.rsquared) if model.rsquared is not None else None,
        adj_r_squared=float(model.rsquared_adj) if model.rsquared_adj is not None else None,
        coefficients=coefs,
        warnings=warnings,
        predict_options=predict_options,
    )


def _extrapolation_warnings(meta: RegressionDesignMeta, inputs: CollectiveRegressionPredictInputs) -> list[str]:
    warns: list[str] = []
    for key, val in [
        ("exclusive_area", inputs.exclusive_area),
        ("building_age", inputs.building_age),
        ("floor", inputs.floor),
    ]:
        if val is None or key not in meta.continuous_ranges:
            continue
        lo, hi = meta.continuous_ranges[key]
        if lo is not None and val < lo:
            warns.append(f"{key}={val} — 표본 하한({lo}) 미만 (외삽)")
        if hi is not None and val > hi:
            warns.append(f"{key}={val} — 표본 상한({hi}) 초과 (외삽)")
    return warns


def _inputs_to_x_row(
    X: pd.DataFrame,
    meta: RegressionDesignMeta,
    req: CollectiveRegressionRequest,
    inputs: CollectiveRegressionPredictInputs,
) -> pd.Series:
    row = {c: 0.0 for c in X.columns}
    if req.variables.exclusive_area and inputs.exclusive_area is not None:
        row["exclusive_area"] = float(inputs.exclusive_area)
    if req.variables.building_age and inputs.building_age is not None:
        row["building_age"] = float(inputs.building_age)

    floor_dummy_cols = meta.floor_dummy_cols
    if req.variables.floor and floor_dummy_cols:
        mx = float(meta.max_floor or inputs.floor or 1)
        floor_vals = _floor_row_for_predict(inputs.floor, req.variables.floor_mode, mx, floor_dummy_cols)
        for c, v in floor_vals.items():
            if c in row:
                row[c] = v

    if req.variables.dong and inputs.dong is not None:
        dong = str(inputs.dong).strip()
        if meta.dong_reference and dong != meta.dong_reference:
            col = f"dong_{dong}"
            if col in row:
                row[col] = 1.0

    if req.variables.housing_subtype and inputs.housing_subtype is not None:
        hs = str(inputs.housing_subtype).strip()
        if meta.housing_subtype_reference and hs != meta.housing_subtype_reference:
            col = f"rights_{hs}"
            if col in row:
                row[col] = 1.0

    if inputs.building_key and meta.building_reference_key:
        bk = str(inputs.building_key)
        if bk != meta.building_reference_key and bk in meta.building_fe_map:
            col = meta.building_fe_map[bk]
            if col in row:
                row[col] = 1.0

    return pd.Series(row, index=X.columns)


def _run_regression_core(
    df: pd.DataFrame,
    req: CollectiveRegressionRequest,
    *,
    cohort_mode: bool = False,
    building_display_names: dict[str, str] | None = None,
) -> tuple[sm.regression.linear_model.RegressionResultsWrapper | None, pd.DataFrame, RegressionDesignMeta, CollectiveRegressionResponse]:
    if df.empty:
        resp = CollectiveRegressionResponse(
            building_key="",
            display_name="",
            n=0,
            warnings=["거래 표본 없음"],
        )
        return None, pd.DataFrame(), RegressionDesignMeta(), resp

    work = _prepare_work(df, req)
    n = len(work)
    if n < 5:
        resp = CollectiveRegressionResponse(
            building_key="",
            display_name="",
            n=n,
            warnings=[f"n={n} — 회귀 최소 표본 부족"],
        )
        return None, pd.DataFrame(), RegressionDesignMeta(), resp

    y, X, labels, meta, fe_warnings = _build_design_matrix(
        work,
        req,
        cohort_mode=cohort_mode,
        building_display_names=building_display_names,
    )
    model, resp = _fit_regression(y, X, labels, meta, req, fe_warnings)
    return model, X, meta, resp


def run_building_regression(
    df: pd.DataFrame,
    building_key: str,
    display_name: str,
    req: CollectiveRegressionRequest,
) -> CollectiveRegressionResponse:
    _, _, _, resp = _run_regression_core(df, req, cohort_mode=False)
    resp.building_key = building_key
    resp.display_name = display_name
    return resp


def run_cohort_regression(
    df: pd.DataFrame,
    building_keys: list[str],
    display_label: str,
    req: CollectiveRegressionRequest,
    *,
    building_display_names: dict[str, str] | None = None,
) -> CollectiveRegressionResponse:
    names = building_display_names or {}
    if not names and "display_name" in df.columns and "building_key" in df.columns:
        for _, row in df.drop_duplicates("building_key").iterrows():
            names[str(row["building_key"])] = str(row.get("display_name") or row["building_key"])

    _, _, _, resp = _run_regression_core(
        df,
        req,
        cohort_mode=True,
        building_display_names=names,
    )
    if len(building_keys) > 1 and resp.n > 0 and not any("단지 FE" in w for w in resp.warnings):
        resp.warnings.insert(0, f"코호트 {len(building_keys)}개 단지 — 단지 고정효과 적용")
    resp.building_key = building_keys[0] if building_keys else ""
    resp.display_name = display_label
    return resp


def predict_regression(
    df: pd.DataFrame,
    req: CollectiveRegressionRequest,
    inputs: CollectiveRegressionPredictInputs,
    *,
    cohort_mode: bool = False,
    building_display_names: dict[str, str] | None = None,
) -> dict:
    model, X, meta, fit_resp = _run_regression_core(
        df,
        req,
        cohort_mode=cohort_mode,
        building_display_names=building_display_names,
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

    y_hat = float(row["mean"])
    exclusive = inputs.exclusive_area
    unit_hat = round(y_hat / float(exclusive), 2) if exclusive and float(exclusive) > 0 else None

    return {
        "n": fit_resp.n,
        "y_hat": round(y_hat, 1),
        "pi_lower": round(float(row["obs_ci_lower"]), 1),
        "pi_upper": round(float(row["obs_ci_upper"]), 1),
        "ci_lower": round(float(row["mean_ci_lower"]), 1),
        "ci_upper": round(float(row["mean_ci_upper"]), 1),
        "unit_price_hat": unit_hat,
        "warnings": warnings,
    }
