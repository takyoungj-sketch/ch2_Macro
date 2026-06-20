"""집합상가·공장 도로(cluster) 회귀 기반 층·면적 효용지수 — semi-log OLS (HC3)."""

from __future__ import annotations

import re
from collections import defaultdict

import numpy as np
import pandas as pd
import statsmodels.api as sm

from app.collective.analysis_gates import MIN_RELIABLE_BUILDING_STATS
from app.collective.area_buckets import (
    FACTORY_AREA_BUCKETS,
    label_for_gross_area,
    shop_fixed_bucket_label,
)
from app.collective.floor_index_regression import (
    _add_time_dummies,
    _cells_from_regression,
    _collinearity_diagnostics,
)
from app.stats_utils import _rnd_price

REFERENCE_CODE = "f1"
REFERENCE_LABEL = "1층"
MIN_FLOOR_GROUP_FOR_DUMMY = 5
MIN_CLUSTER_FE_GROUP = 5

# (label, code, sort_key)
SHOP_FLOOR_GROUPS: list[tuple[str, str, float]] = [
    ("지하심층", "b2_deep", -2),
    ("지하1층", "b1", -1),
    ("1층", "f1", 1),
    ("2층", "f2", 2),
    ("저층", "low", 3),
    ("중층", "mid", 5),
    ("고층", "high", 10),
    ("초고층", "ultra", 20),
]


def shop_floor_group(floor: float | int | None) -> tuple[str, str] | None:
    """원시 층수 → (표시 라벨, 내부 코드). 매핑 불가 시 None."""
    if floor is None or (isinstance(floor, float) and pd.isna(floor)):
        return None
    try:
        f = float(floor)
    except (TypeError, ValueError):
        return None
    if f <= -2:
        return ("지하심층", "b2_deep")
    if f == -1:
        return ("지하1층", "b1")
    if f == 1:
        return ("1층", "f1")
    if f == 2:
        return ("2층", "f2")
    if 3 <= f <= 4:
        return ("저층", "low")
    if 5 <= f <= 9:
        return ("중층", "mid")
    if 10 <= f <= 19:
        return ("고층", "high")
    if f >= 20:
        return ("초고층", "ultra")
    return None


def _add_cat_dummies(
    work: pd.DataFrame,
    col: str,
    prefix: str,
) -> tuple[pd.DataFrame, dict[str, str]]:
    if col not in work.columns or not work[col].notna().any():
        return pd.DataFrame(index=work.index), {}
    series = work[col].astype(str).str.strip()
    series = series.replace({"nan": pd.NA, "None": pd.NA, "": pd.NA})
    if series.dropna().nunique() < 2:
        return pd.DataFrame(index=work.index), {}
    dummies = pd.get_dummies(series, prefix=prefix, drop_first=True)
    labels = {c: f"건축물용도 {c.replace(prefix + '_', '')} (기준 대비)" for c in dummies.columns}
    return dummies, labels


def _add_cluster_fe(
    reg: pd.DataFrame,
    parts: list[pd.DataFrame],
    controls: list[str],
    *,
    reference_key: str,
) -> None:
    """코호트: 도로(cluster) 고정효과 — 표본 최다 cluster = 기준(omitted)."""
    if "cluster_key" not in reg.columns:
        return
    keys = reg["cluster_key"].astype(str)
    if keys.nunique() < 2:
        return
    added = False
    for ck in sorted(k for k in keys.unique() if k != reference_key):
        col = f"clst_{re.sub(r'[^a-zA-Z0-9]+', '_', ck)[:32]}"
        reg[col] = (keys == ck).astype(float)
        if reg[col].sum() >= MIN_CLUSTER_FE_GROUP:
            parts.append(reg[[col]])
            added = True
    if added:
        controls.append("cluster_fixed_effects")


def compute_shop_floor_index_regression(df: pd.DataFrame, *, cohort_mode: bool = False) -> dict:
    """ln(㎡당단가) ~ ln(연면적) + 연식 + 용도더미 + 층구간더미(1층 기준)."""
    warnings: list[str] = []
    controls: list[str] = []

    work = df.dropna(subset=["unit_price"]).copy()
    work = work[work["unit_price"].astype(float) > 0]

    mapped: list[tuple[int, str, str, float]] = []
    for idx, row in work.iterrows():
        grp = shop_floor_group(row.get("floor"))
        if grp is None:
            continue
        label, code = grp
        mapped.append((idx, label, code, float(row["unit_price"])))

    if not mapped:
        return {
            "method": "regression_semilog",
            "reference_floor": REFERENCE_LABEL,
            "controls": [],
            "n_total": 0,
            "n_regression": 0,
            "r_squared": None,
            "baseline_median": None,
            "dimension": "floor",
            "cells": [],
            "warnings": ["층 정보가 있는 거래가 없습니다."],
        }

    idxs, labels, codes, _ = zip(*mapped)
    work = work.loc[list(idxs)].copy()
    work["floor_group_label"] = list(labels)
    work["floor_group_code"] = list(codes)

    n_total = len(work)

    mask = work["building_age"].isna() & work["building_year"].notna() & work["contract_year"].notna()
    work.loc[mask, "building_age"] = (
        work.loc[mask, "contract_year"].astype(float) - work.loc[mask, "building_year"].astype(float)
    )

    group_prices: dict[str, list[float]] = defaultdict(list)
    group_counts: dict[str, int] = defaultdict(int)
    for _, row in work.iterrows():
        code = row["floor_group_code"]
        group_prices[code].append(float(row["unit_price"]))
        group_counts[code] += 1

    baseline = float(np.median(work["unit_price"].astype(float)))

    ref_count = group_counts.get(REFERENCE_CODE, 0)
    if ref_count < MIN_FLOOR_GROUP_FOR_DUMMY:
        warnings.append(
            f"기준층({REFERENCE_LABEL}) 거래 {ref_count}건 — "
            f"최소 {MIN_FLOOR_GROUP_FOR_DUMMY}건 필요, 회귀 지수 미산출"
        )
        cells = _cells_from_counts_only(group_counts, group_prices, baseline)
        return {
            "method": "regression_semilog",
            "reference_floor": REFERENCE_LABEL,
            "controls": [],
            "n_total": n_total,
            "n_regression": 0,
            "r_squared": None,
            "baseline_median": _rnd_price(baseline),
            "dimension": "floor",
            "cells": cells,
            "warnings": warnings,
        }

    reg = work.copy()
    reg = reg[reg["gross_area"].astype(float) > 0]
    reg["ln_unit_price"] = np.log(reg["unit_price"].astype(float))
    reg["ln_gross_area"] = np.log(reg["gross_area"].astype(float))

    parts: list[pd.DataFrame] = [reg[["ln_gross_area"]]]
    controls.append("ln_gross_area")

    if reg["building_age"].notna().any():
        parts.append(reg[["building_age"]].astype(float))
        controls.append("building_age")

    use_part, _ = _add_cat_dummies(reg, "building_use", "use")
    if not use_part.empty:
        parts.append(use_part)
        controls.append("building_use")

    dummy_codes = [
        code
        for _, code, _ in SHOP_FLOOR_GROUPS
        if code != REFERENCE_CODE and group_counts.get(code, 0) >= MIN_FLOOR_GROUP_FOR_DUMMY
    ]
    for code in dummy_codes:
        col = f"floor_{code}"
        reg[col] = (reg["floor_group_code"] == code).astype(float)
        parts.append(reg[[col]])

    _add_time_dummies(reg, parts, controls)

    if cohort_mode and "cluster_key" in reg.columns and reg["cluster_key"].nunique() > 1:
        ref_ck = str(reg["cluster_key"].value_counts().idxmax())
        _add_cluster_fe(reg, parts, controls, reference_key=ref_ck)
        warnings.append(
            f"코호트 {reg['cluster_key'].nunique()}개 도로 — cluster FE 적용 (기준: 거래 최다 도로)"
        )

    for label, code, _ in SHOP_FLOOR_GROUPS:
        if code != REFERENCE_CODE and 0 < group_counts.get(code, 0) < MIN_FLOOR_GROUP_FOR_DUMMY:
            warnings.append(f"{label} n={group_counts[code]} — 구간 표본 부족, 지수 미산출")

    if not dummy_codes:
        warnings.append("회귀에 포함할 층 구간(기준층 제외)이 없습니다.")
        cells = _cells_from_counts_only(group_counts, group_prices, baseline)
        return {
            "method": "regression_semilog",
            "reference_floor": REFERENCE_LABEL,
            "controls": controls,
            "n_total": n_total,
            "n_regression": 0,
            "r_squared": None,
            "baseline_median": _rnd_price(baseline),
            "dimension": "floor",
            "cells": cells,
            "warnings": warnings,
        }

    X = pd.concat(parts, axis=1).astype(float)
    y = reg["ln_unit_price"]
    valid = X.notna().all(axis=1) & y.notna()
    X = X.loc[valid]
    y = y.loc[valid]

    if len(y) < 30:
        warnings.append(f"회귀 표본 n={len(y)} — 참고용 (권장 n≥30)")

    X = sm.add_constant(X, has_constant="add")
    try:
        model = sm.OLS(y, X, missing="drop").fit(cov_type="HC3")
    except Exception as exc:
        warnings.append(f"회귀 실패: {exc}")
        cells = _cells_from_counts_only(group_counts, group_prices, baseline)
        return {
            "method": "regression_semilog",
            "reference_floor": REFERENCE_LABEL,
            "controls": controls,
            "n_total": n_total,
            "n_regression": 0,
            "r_squared": None,
            "baseline_median": _rnd_price(baseline),
            "dimension": "floor",
            "cells": cells,
            "warnings": warnings,
        }

    diagnostics, diag_warnings = _collinearity_diagnostics(X)
    warnings.extend(diag_warnings)

    coef_map: dict[str, dict] = {}
    for code in dummy_codes:
        col = f"floor_{code}"
        if col not in model.params.index:
            continue
        gamma = float(model.params[col])
        se = float(model.bse[col]) if col in model.bse.index else None
        p = float(model.pvalues[col]) if col in model.pvalues.index else None
        idx_pct = round(float(np.exp(gamma)) * 100, 1)
        idx_lo = round(float(np.exp(gamma - 1.96 * se)) * 100, 1) if se is not None else None
        idx_hi = round(float(np.exp(gamma + 1.96 * se)) * 100, 1) if se is not None else None
        coef_map[code] = {
            "gamma": round(gamma, 4),
            "p_value": round(p, 4) if p is not None else None,
            "index": idx_pct,
            "index_lo": idx_lo,
            "index_hi": idx_hi,
        }

    cells = []
    for label, code, sort_key in SHOP_FLOOR_GROUPS:
        count = group_counts.get(code, 0)
        prices = group_prices.get(code, [])
        mean_p = float(np.mean(prices)) if prices else None
        is_ref = code == REFERENCE_CODE
        coef = coef_map.get(code)
        if is_ref:
            index_val = 100.0
            gamma = None
            p_value = None
            index_lo = None
            index_hi = None
        elif coef:
            index_val = coef["index"]
            gamma = coef["gamma"]
            p_value = coef["p_value"]
            index_lo = coef["index_lo"]
            index_hi = coef["index_hi"]
        else:
            index_val = None
            gamma = None
            p_value = None
            index_lo = None
            index_hi = None

        cells.append(
            {
                "label": label,
                "floor": sort_key,
                "count": count,
                "mean_unit_price": _rnd_price(mean_p) if mean_p is not None else None,
                "index": index_val,
                "is_reliable": count >= MIN_RELIABLE_BUILDING_STATS,
                "is_reference": is_ref,
                "gamma": gamma,
                "p_value": p_value,
                "index_lo": index_lo,
                "index_hi": index_hi,
            }
        )

    return {
        "method": "regression_semilog",
        "reference_floor": REFERENCE_LABEL,
        "controls": controls,
        "n_total": n_total,
        "n_regression": int(model.nobs),
        "r_squared": round(float(model.rsquared), 4) if model.rsquared is not None else None,
        "baseline_median": _rnd_price(baseline),
        "dimension": "floor",
        "cells": cells,
        "warnings": warnings,
        "diagnostics": diagnostics,
    }


def _area_code_from_sort(sort_key: float) -> str:
    return f"area_{int(sort_key) if sort_key == int(sort_key) else sort_key:g}"


def _commercial_area_bucket(
    gross_area: float | None,
    asset_type: str,
) -> tuple[str, str, float | None]:
    if gross_area is None or (isinstance(gross_area, float) and pd.isna(gross_area)) or float(gross_area) <= 0:
        return "area_missing", "—", None
    fv = float(gross_area)
    if asset_type == "collective_shop":
        label, sort_v = shop_fixed_bucket_label(fv)
        return _area_code_from_sort(sort_v), label, sort_v
    label, sort_v = label_for_gross_area(asset_type, fv)
    if label == "—" or sort_v is None:
        return "area_missing", "—", None
    return _area_code_from_sort(sort_v), label, sort_v


def _factory_area_group_specs() -> list[tuple[str, str, float | None]]:
    return [(label, _area_code_from_sort(sort_key), sort_key) for _, _, label, sort_key in FACTORY_AREA_BUCKETS]


def _add_shop_floor_control(reg: pd.DataFrame, parts: list[pd.DataFrame], controls: list[str]) -> None:
    """면적형 탭: 층 구간 통제 (1층 기준 omitted)."""
    codes: list[str | None] = []
    for fl in reg.get("floor", pd.Series(dtype=float)):
        grp = shop_floor_group(fl)
        codes.append(grp[1] if grp else None)
    reg["floor_ctrl_code"] = codes
    added = False
    for _label, code, _ in SHOP_FLOOR_GROUPS:
        if code == REFERENCE_CODE:
            continue
        col = f"ctrl_{code}"
        reg[col] = (reg["floor_ctrl_code"] == code).astype(float)
        if reg[col].sum() >= MIN_FLOOR_GROUP_FOR_DUMMY:
            parts.append(reg[[col]])
            added = True
    if added:
        controls.append("relative_floor")


def _cells_area_fallback(
    group_specs: list[tuple[str, str, float | None]],
    group_counts: dict[str, int],
    group_prices: dict[str, list[float]],
    reference_code: str,
    baseline: float,
) -> list[dict]:
    cells = []
    for label, code, sort_key in group_specs:
        count = group_counts.get(code, 0)
        prices = group_prices.get(code, [])
        mean_p = float(np.mean(prices)) if prices else None
        is_ref = code == reference_code
        index_val = (
            100.0
            if is_ref
            else round(mean_p / baseline * 100, 1) if mean_p is not None and baseline > 0 else None
        )
        cells.append(
            {
                "label": label,
                "area": sort_key,
                "count": count,
                "mean_unit_price": _rnd_price(mean_p) if mean_p is not None else None,
                "index": index_val,
                "is_reliable": count >= MIN_RELIABLE_BUILDING_STATS,
                "is_reference": is_ref,
                "gamma": None,
                "p_value": None,
                "index_lo": None,
                "index_hi": None,
            }
        )
    return cells


def compute_commercial_area_index_regression(
    df: pd.DataFrame,
    *,
    asset_type: str,
    cohort_mode: bool = False,
) -> dict:
    """ln(㎡당단가) ~ 연식 + 층구간 + 시점 + 면적구간더미 (연면적 연속항 제외 — 주거 면적형과 동일)."""
    warnings: list[str] = []
    controls: list[str] = []

    work = df.dropna(subset=["unit_price"]).copy()
    work = work[work["unit_price"].astype(float) > 0]
    n_total = len(work)
    if n_total == 0:
        return {
            "method": "regression_semilog",
            "reference_floor": None,
            "controls": [],
            "n_total": 0,
            "n_regression": 0,
            "r_squared": None,
            "baseline_median": None,
            "dimension": "area",
            "cells": [],
            "warnings": ["유효 거래가 없습니다."],
        }

    mask = work["building_age"].isna() & work["building_year"].notna() & work["contract_year"].notna()
    work.loc[mask, "building_age"] = (
        work.loc[mask, "contract_year"].astype(float) - work.loc[mask, "building_year"].astype(float)
    )

    codes: list[str] = []
    labels: list[str] = []
    area_meta: dict[str, tuple[str, float | None]] = {}
    for _, row in work.iterrows():
        code, lbl, sort_v = _commercial_area_bucket(row.get("gross_area"), asset_type)
        area_meta[code] = (lbl, sort_v)
        codes.append(code)
        labels.append(lbl)
    work["index_group_code"] = codes
    work["index_group_label"] = labels

    valid = work[work["index_group_code"] != "area_missing"]
    if valid.empty:
        return {
            "method": "regression_semilog",
            "reference_floor": None,
            "controls": [],
            "n_total": n_total,
            "n_regression": 0,
            "r_squared": None,
            "baseline_median": None,
            "dimension": "area",
            "cells": [],
            "warnings": ["면적 정보가 있는 거래가 없습니다."],
        }

    if asset_type == "collective_factory":
        group_specs = _factory_area_group_specs()
    else:
        group_specs = []
        for code in sorted(
            area_meta.keys(),
            key=lambda c: (area_meta[c][1] is None, area_meta[c][1] or 0),
        ):
            if code == "area_missing":
                continue
            lbl, sort_v = area_meta[code]
            group_specs.append((lbl, code, sort_v))

    med = float(valid["gross_area"].astype(float).median())
    ref_code, reference_label, _ = _commercial_area_bucket(med, asset_type)
    if ref_code == "area_missing":
        ref_code = str(valid["index_group_code"].value_counts().idxmax())
        reference_label = area_meta.get(ref_code, (ref_code, None))[0]
    reference_code = ref_code

    baseline = float(np.median(work["unit_price"].astype(float)))
    group_counts: dict[str, int] = defaultdict(int)
    group_prices: dict[str, list[float]] = defaultdict(list)
    for _, row in work.iterrows():
        code = row["index_group_code"]
        if code == "area_missing":
            continue
        group_counts[code] += 1
        group_prices[code].append(float(row["unit_price"]))

    ref_count = group_counts.get(reference_code, 0)
    if ref_count < MIN_FLOOR_GROUP_FOR_DUMMY:
        warnings.append(
            f"기준({reference_label}) 거래 {ref_count}건 — "
            f"최소 {MIN_FLOOR_GROUP_FOR_DUMMY}건 필요, 회귀 지수 미산출"
        )
        return {
            "method": "regression_semilog",
            "reference_floor": reference_label,
            "controls": [],
            "n_total": n_total,
            "n_regression": 0,
            "r_squared": None,
            "baseline_median": _rnd_price(baseline),
            "dimension": "area",
            "cells": _cells_area_fallback(group_specs, group_counts, group_prices, reference_code, baseline),
            "warnings": warnings,
        }

    reg = work[work["index_group_code"] != "area_missing"].copy()
    reg = reg[reg["gross_area"].astype(float) > 0]
    if reg.empty:
        warnings.append("연면적 유효 거래 없음")
        return {
            "method": "regression_semilog",
            "reference_floor": reference_label,
            "controls": [],
            "n_total": n_total,
            "n_regression": 0,
            "r_squared": None,
            "baseline_median": _rnd_price(baseline),
            "dimension": "area",
            "cells": _cells_area_fallback(group_specs, group_counts, group_prices, reference_code, baseline),
            "warnings": warnings,
        }

    reg["ln_unit_price"] = np.log(reg["unit_price"].astype(float))
    parts: list[pd.DataFrame] = []

    if reg["building_age"].notna().any():
        parts.append(reg[["building_age"]].astype(float))
        controls.append("building_age")

    _add_shop_floor_control(reg, parts, controls)
    _add_time_dummies(reg, parts, controls)

    if cohort_mode and "cluster_key" in reg.columns and reg["cluster_key"].nunique() > 1:
        ref_ck = str(reg["cluster_key"].value_counts().idxmax())
        _add_cluster_fe(reg, parts, controls, reference_key=ref_ck)
        warnings.append(
            f"코호트 {reg['cluster_key'].nunique()}개 도로 — cluster FE 적용 (기준: 거래 최다 도로)"
        )

    dummy_codes = [
        code
        for _, code, _ in group_specs
        if code != reference_code and group_counts.get(code, 0) >= MIN_FLOOR_GROUP_FOR_DUMMY
    ]
    for label, code, _ in group_specs:
        if code != reference_code and 0 < group_counts.get(code, 0) < MIN_FLOOR_GROUP_FOR_DUMMY:
            warnings.append(f"{label} n={group_counts[code]} — 구간 표본 부족, 지수 미산출")

    for code in dummy_codes:
        col = f"idx_{code}"
        reg[col] = (reg["index_group_code"] == code).astype(float)
        parts.append(reg[[col]])

    if not dummy_codes:
        warnings.append("회귀에 포함할 면적 구간(기준 제외)이 없습니다.")
        return {
            "method": "regression_semilog",
            "reference_floor": reference_label,
            "controls": controls,
            "n_total": n_total,
            "n_regression": 0,
            "r_squared": None,
            "baseline_median": _rnd_price(baseline),
            "dimension": "area",
            "cells": _cells_area_fallback(group_specs, group_counts, group_prices, reference_code, baseline),
            "warnings": warnings,
        }

    X = pd.concat(parts, axis=1).astype(float)
    y = reg["ln_unit_price"]
    valid_mask = X.notna().all(axis=1) & y.notna()
    X = X.loc[valid_mask]
    y = y.loc[valid_mask]

    if len(y) < 30:
        warnings.append(f"회귀 표본 n={len(y)} — 참고용 (권장 n≥30)")

    X = sm.add_constant(X, has_constant="add")
    try:
        model = sm.OLS(y, X, missing="drop").fit(cov_type="HC3")
    except Exception as exc:
        warnings.append(f"회귀 실패: {exc}")
        return {
            "method": "regression_semilog",
            "reference_floor": reference_label,
            "controls": controls,
            "n_total": n_total,
            "n_regression": 0,
            "r_squared": None,
            "baseline_median": _rnd_price(baseline),
            "dimension": "area",
            "cells": _cells_area_fallback(group_specs, group_counts, group_prices, reference_code, baseline),
            "warnings": warnings,
        }

    diagnostics, diag_warnings = _collinearity_diagnostics(X)
    warnings.extend(diag_warnings)

    coef_map: dict[str, dict] = {}
    for code in dummy_codes:
        col = f"idx_{code}"
        if col not in model.params.index:
            continue
        gamma = float(model.params[col])
        se = float(model.bse[col]) if col in model.bse.index else None
        p = float(model.pvalues[col]) if col in model.pvalues.index else None
        idx_pct = round(float(np.exp(gamma)) * 100, 1)
        idx_lo = round(float(np.exp(gamma - 1.96 * se)) * 100, 1) if se is not None else None
        idx_hi = round(float(np.exp(gamma + 1.96 * se)) * 100, 1) if se is not None else None
        coef_map[code] = {
            "gamma": round(gamma, 4),
            "p_value": round(p, 4) if p is not None else None,
            "index": idx_pct,
            "index_lo": idx_lo,
            "index_hi": idx_hi,
        }

    cells = _cells_from_regression(
        group_specs,
        group_counts,
        group_prices,
        reference_code,
        coef_map,
        "area",
    )

    return {
        "method": "regression_semilog",
        "reference_floor": reference_label,
        "controls": controls,
        "n_total": n_total,
        "n_regression": int(model.nobs),
        "r_squared": round(float(model.rsquared), 4) if model.rsquared is not None else None,
        "baseline_median": _rnd_price(baseline),
        "dimension": "area",
        "cells": cells,
        "warnings": warnings,
        "diagnostics": diagnostics,
    }


def _cells_from_counts_only(
    group_counts: dict[str, int],
    group_prices: dict[str, list[float]],
    baseline: float,
) -> list[dict]:
    cells = []
    for label, code, sort_key in SHOP_FLOOR_GROUPS:
        count = group_counts.get(code, 0)
        prices = group_prices.get(code, [])
        mean_p = float(np.mean(prices)) if prices else None
        index_val = round(mean_p / baseline * 100, 1) if mean_p is not None and baseline > 0 else None
        cells.append(
            {
                "label": label,
                "floor": sort_key,
                "count": count,
                "mean_unit_price": _rnd_price(mean_p) if mean_p is not None else None,
                "index": index_val if code == REFERENCE_CODE else None,
                "is_reliable": count >= MIN_RELIABLE_BUILDING_STATS,
                "is_reference": code == REFERENCE_CODE,
                "gamma": None,
                "p_value": None,
                "index_lo": None,
                "index_hi": None,
            }
        )
    return cells
