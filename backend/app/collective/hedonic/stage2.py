"""2단계 특성회귀 + 블록 L 시군구 매크로."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.stats.outliers_influence import variance_inflation_factor

from app.collective.hedonic.constants import (
    BOOTSTRAP_REPS,
    BRAND_OTHER,
    BRAND_OTHER_LABEL,
    BRAND_REFERENCE,
    BRAND_REFERENCE_LABEL,
    BUILDER_OTHER,
    BUILDER_OTHER_LABEL,
    DEFAULT_DANJI_CLASSES,
    DEFAULT_MATCH_TIERS,
    DEFAULT_SUPPLY_TYPES,
    LOCATION_TERMS,
    MACRO_TERMS,
    MIN_BUILDINGS_PER_TERM,
    SPEC_LABELS,
    STRUCTURE_LABELS,
    STRUCTURE_REFERENCE,
    VINTAGE_BINS,
    VINTAGE_REFERENCE,
    QUALITY_FLAG_FLOOR,
    QUALITY_FLAG_HH_ZERO,
    QUALITY_FLAG_PARKING,
    QUALITY_FLAG_SCALE,
)


@dataclass
class AttributeEffectsResult:
    spec: str
    scope_level: str
    scope_code: str | None
    include_location: bool
    weighting: str
    coefficients: list[dict[str, Any]]
    equation: str
    warnings: list[str]
    sample_breakdown: dict[str, Any]
    reference_categories: dict[str, str]
    n_buildings: int
    adj_r_squared: float | None
    model_candidates: list[dict[str, Any]] = field(default_factory=list)
    controls_note: str = (
        "동일 시군구·면적·층·계약연도를 1단계에서 통제한 뒤의 단지특성 효과입니다."
    )


def vintage_bin(year: int | None) -> str | None:
    if year is None or (isinstance(year, float) and np.isnan(year)):
        return None
    y = int(year)
    for label, lo, hi in VINTAGE_BINS:
        if lo is not None and y < lo:
            continue
        if hi is not None and y > hi:
            continue
        if lo is None and hi is not None and y <= hi:
            return label
        if hi is None and lo is not None and y >= lo:
            return label
        if lo is not None and hi is not None and lo <= y <= hi:
            return label
    return None


def _has_flag(flags: object, code: str) -> bool:
    if flags is None or (isinstance(flags, float) and np.isnan(flags)):
        return False
    parts = {p.strip() for p in str(flags).split(",") if p.strip()}
    return code in parts


def _collapse_terms(series: pd.Series, min_n: int, *, other: str = BRAND_OTHER) -> pd.Series:
    counts = series.value_counts()
    keep = set(counts[counts >= min_n].index.astype(str))
    return series.astype(str).where(series.astype(str).isin(keep), other=other)


def _prepare_stage2_frame(
    df: pd.DataFrame,
    *,
    match_tiers: set[str],
    danji_classes: set[str],
    supply_types: set[str],
    include_terms: set[str],
    min_buildings_per_term: int,
    spec: str,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    breakdown: dict[str, Any] = {"initial": len(df)}
    work = df.copy()

    work = work[work["match_tier"].isin(match_tiers)]
    breakdown["after_tier"] = len(work)

    if "danji_class" in work.columns:
        work = work[work["danji_class"].isin(danji_classes)]
    breakdown["after_danji_class"] = len(work)

    if "supply_type" in work.columns and supply_types:
        work = work[work["supply_type"].isin(supply_types)]
    breakdown["after_supply_type"] = len(work)

    work = work[work["quality_index"].notna()]
    breakdown["after_quality_index"] = len(work)

    # 대표 building_key — danji_code 중복 시 거래 최대 키만
    if "danji_code" in work.columns:
        dup_codes = work["danji_code"].dropna().value_counts()
        dup_codes = dup_codes[dup_codes > 1].index.tolist()
        if dup_codes:
            keep_keys: set[str] = set()
            for dc in dup_codes:
                sub = work[work["danji_code"] == dc]
                best = sub.sort_values("n_tx", ascending=False).iloc[0]["building_key"]
                keep_keys.add(str(best))
            single = work[~work["danji_code"].isin(dup_codes)]
            multi = work[work["danji_code"].isin(dup_codes) & work["building_key"].astype(str).isin(keep_keys)]
            work = pd.concat([single, multi], ignore_index=True)
            breakdown["danji_duplicate_collapsed"] = len(dup_codes)

    breakdown["final"] = len(work)
    if work.empty:
        return work, breakdown

    work["brand_term"] = work["brand"].fillna(BRAND_REFERENCE).astype(str)
    work["builder_term"] = work["builder_group"].fillna(BUILDER_OTHER).astype(str)
    work["structure_term"] = work["structure_group"].fillna(STRUCTURE_REFERENCE).astype(str)
    work["vintage_term"] = work.apply(
        lambda r: vintage_bin(r.get("approved_year") or r.get("building_year")),
        axis=1,
    )
    work["vintage_term"] = work["vintage_term"].fillna(VINTAGE_REFERENCE)

    if "brand" in include_terms and spec in ("A", "C"):
        work["brand_term"] = _collapse_terms(work["brand_term"], min_buildings_per_term)
    if "builder" in include_terms and spec in ("B", "C"):
        work["builder_term"] = _collapse_terms(
            work["builder_term"], min_buildings_per_term, other=BUILDER_OTHER
        )

    # 품질 플래그 → 해당 변수 결측
    for idx, row in work.iterrows():
        flags = row.get("attr_quality_flags")
        if _has_flag(flags, QUALITY_FLAG_SCALE) or _has_flag(flags, QUALITY_FLAG_HH_ZERO):
            work.at[idx, "households"] = np.nan
        if _has_flag(flags, QUALITY_FLAG_FLOOR):
            work.at[idx, "max_floor"] = np.nan
        if _has_flag(flags, QUALITY_FLAG_PARKING):
            work.at[idx, "parking_per_household"] = np.nan

    if "scale" in include_terms:
        work["ln_households"] = np.log(work["households"].astype(float).clip(lower=1))

    work["is_jusang"] = (work.get("danji_class") == "주상복합").astype(float)

    return work, breakdown


def _build_design(
    work: pd.DataFrame,
    *,
    spec: str,
    include_terms: set[str],
    include_location: bool,
) -> tuple[pd.DataFrame, pd.Series, pd.Series | None, dict[str, str], list[str]]:
    labels: dict[str, str] = {"const": "절편"}
    parts: list[pd.DataFrame] = []
    warnings: list[str] = []

    if spec in ("A", "C") and "brand" in include_terms:
        brand = work["brand_term"].astype(str)
        dummies = pd.get_dummies(brand, prefix="brand", drop_first=False)
        if f"brand_{BRAND_REFERENCE}" in dummies.columns:
            dummies = dummies.drop(columns=[f"brand_{BRAND_REFERENCE}"])
        parts.append(dummies.astype(float))
        for col in dummies.columns:
            key = col.replace("brand_", "")
            if key == BRAND_OTHER:
                labels[col] = BRAND_OTHER_LABEL
            elif key == BRAND_REFERENCE:
                labels[col] = BRAND_REFERENCE_LABEL
            else:
                labels[col] = key

    if spec in ("B", "C") and "builder" in include_terms:
        builder = work["builder_term"].astype(str)
        dummies = pd.get_dummies(builder, prefix="builder", drop_first=False)
        ref_col = f"builder_{BUILDER_OTHER}"
        if ref_col in dummies.columns:
            dummies = dummies.drop(columns=[ref_col])
        parts.append(dummies.astype(float))
        for col in dummies.columns:
            key = col.replace("builder_", "")
            labels[col] = BUILDER_OTHER_LABEL if key == BUILDER_OTHER else key

    if "scale" in include_terms and "ln_households" in work.columns:
        parts.append(work[["ln_households"]].astype(float))
        labels["ln_households"] = "ln(세대수)"

    if "structure" in include_terms:
        st = work["structure_term"].astype(str)
        dummies = pd.get_dummies(st, prefix="struct", drop_first=False)
        ref = f"struct_{STRUCTURE_REFERENCE}"
        if ref in dummies.columns:
            dummies = dummies.drop(columns=[ref])
        parts.append(dummies.astype(float))
        for col in dummies.columns:
            key = col.replace("struct_", "")
            labels[col] = STRUCTURE_LABELS.get(key, key)

    if "vintage" in include_terms:
        vt = work["vintage_term"].astype(str)
        dummies = pd.get_dummies(vt, prefix="vintage", drop_first=False)
        ref = f"vintage_{VINTAGE_REFERENCE}"
        if ref in dummies.columns:
            dummies = dummies.drop(columns=[ref])
        parts.append(dummies.astype(float))
        for col in dummies.columns:
            labels[col] = col.replace("vintage_", "")

    if "parking" in include_terms and "parking_per_household" in work.columns:
        parts.append(work[["parking_per_household"]].astype(float))
        labels["parking_per_household"] = "세대당 주차"

    if "danji_class" in include_terms:
        parts.append(work[["is_jusang"]].astype(float))
        labels["is_jusang"] = "주상복합(기준: 아파트)"

    if "max_floor" in include_terms and "max_floor" in work.columns:
        parts.append(work[["max_floor"]].astype(float))
        labels["max_floor"] = "최고층수"

    if include_location:
        for col, label in (
            ("eup_population", "읍면동 인구"),
            ("rent_jeonse_p50", "단지 전세 P50(만원/㎡)"),
            ("land_p50_zone", "용도지역 토지 P50"),
        ):
            if col in include_terms and col in work.columns:
                parts.append(work[[col]].astype(float))
                labels[col] = label

    x = pd.concat(parts, axis=1) if parts else pd.DataFrame(index=work.index)
    x = sm.add_constant(x, has_constant="add")
    y = work["quality_index"].astype(float)

    weights = None
    if "quality_se" in work.columns:
        se = work["quality_se"].astype(float).fillna(work["quality_se"].astype(float).median())
        med = float(se.median()) if se.notna().any() else 1.0
        w = 1.0 / (se**2 + med**2)
        weights = w

    return x, y, weights, labels, warnings


def _term_kind(name: str) -> str:
    if name.startswith("brand_"):
        return "brand"
    if name.startswith("builder_"):
        return "builder"
    if name in ("ln_households",):
        return "scale"
    if name.startswith("struct_"):
        return "structure"
    if name.startswith("vintage_"):
        return "vintage"
    if name in LOCATION_TERMS:
        return "location"
    if name in MACRO_TERMS:
        return "macro"
    return "other"


def _format_equation(labels: dict[str, str], coefs: dict[str, float]) -> str:
    parts = ["quality_index ="]
    for name, label in labels.items():
        if name == "const":
            continue
        c = coefs.get(name, 0.0)
        if abs(c) < 1e-12:
            continue
        sign = "+" if c >= 0 else "−"
        parts.append(f" {sign} {abs(c):.4f}·[{label}]")
    intercept = coefs.get("const", 0.0)
    parts.insert(1, f" {intercept:.4f}")
    return "".join(parts)


def _compute_vif(x: pd.DataFrame) -> dict[str, float]:
    cols = [c for c in x.columns if c != "const"]
    if len(cols) < 2:
        return {}
    out: dict[str, float] = {}
    arr = x[cols].astype(float).values
    for i, col in enumerate(cols):
        try:
            out[col] = float(variance_inflation_factor(arr, i))
        except Exception:  # noqa: BLE001
            out[col] = float("nan")
    return out


def _bootstrap_ci(
    work: pd.DataFrame,
    x: pd.DataFrame,
    y: pd.Series,
    weights: pd.Series | None,
    *,
    reps: int = BOOTSTRAP_REPS,
) -> dict[str, tuple[float, float]]:
    if reps <= 0 or len(work) < 30:
        return {}
    rng = np.random.default_rng(42)
    names = [c for c in x.columns if c != "const"]
    store: dict[str, list[float]] = {n: [] for n in names}
    idx = np.arange(len(work))
    for _ in range(reps):
        pick = rng.choice(idx, size=len(idx), replace=True)
        xb = x.iloc[pick]
        yb = y.iloc[pick]
        wb = weights.iloc[pick] if weights is not None else None
        try:
            if wb is not None:
                model = sm.WLS(yb, xb, weights=wb).fit()
            else:
                model = sm.OLS(yb, xb).fit()
        except Exception:  # noqa: BLE001
            continue
        for n in names:
            if n in model.params.index:
                store[n].append(float(model.params[n]))
    out: dict[str, tuple[float, float]] = {}
    for n, vals in store.items():
        if len(vals) >= 20:
            out[n] = (float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5)))
    return out


def run_attribute_effects(
    df: pd.DataFrame,
    *,
    spec: str = "A",
    scope_level: str = "national",
    scope_code: str | None = None,
    include_terms: set[str] | None = None,
    include_location: bool = False,
    match_tiers: set[str] | None = None,
    danji_classes: set[str] | None = None,
    supply_types: set[str] | None = None,
    min_buildings_per_term: int = MIN_BUILDINGS_PER_TERM,
    weighting: str = "wls",
    bootstrap_reps: int = BOOTSTRAP_REPS,
) -> AttributeEffectsResult:
    include_terms = include_terms or {
        "brand",
        "builder",
        "scale",
        "structure",
        "vintage",
        "parking",
        "danji_class",
        "max_floor",
    }
    match_tiers = match_tiers or set(DEFAULT_MATCH_TIERS)
    danji_classes = danji_classes or set(DEFAULT_DANJI_CLASSES)
    supply_types = supply_types or set(DEFAULT_SUPPLY_TYPES)

    work0 = df.copy()
    if scope_level == "sido" and scope_code:
        work0 = work0[work0["sido_code"].astype(str) == str(scope_code)]
    elif scope_level == "sigungu" and scope_code:
        work0 = work0[work0["sigungu_code"].astype(str) == str(scope_code)]

    work, breakdown = _prepare_stage2_frame(
        work0,
        match_tiers=match_tiers,
        danji_classes=danji_classes,
        supply_types=supply_types,
        include_terms=include_terms,
        min_buildings_per_term=min_buildings_per_term,
        spec=spec,
    )

    warnings: list[str] = []
    if spec == "C":
        warnings.append("스펙 C는 브랜드·시공사 공선 진단용 — UI 기본 노출 금지")
    if breakdown.get("final", 0) < 50:
        warnings.append(f"표본 부족 — 단지 {breakdown.get('final', 0)}개")

    if work.empty or breakdown.get("final", 0) < 10:
        return AttributeEffectsResult(
            spec=spec,
            scope_level=scope_level,
            scope_code=scope_code,
            include_location=include_location,
            weighting=weighting,
            coefficients=[],
            equation="",
            warnings=warnings + ["회귀 표본 없음"],
            sample_breakdown=breakdown,
            reference_categories={
                "brand": BRAND_REFERENCE_LABEL,
                "structure": STRUCTURE_REFERENCE,
                "vintage": VINTAGE_REFERENCE,
            },
            n_buildings=0,
            adj_r_squared=None,
        )

    loc_terms = set(LOCATION_TERMS) if include_location else set()
    active_terms = include_terms | loc_terms

    x, y, weights, labels, _ = _build_design(
        work,
        spec=spec,
        include_terms=active_terms,
        include_location=include_location,
    )
    if x.shape[1] <= 1:
        warnings.append("설명변수 없음")
        return AttributeEffectsResult(
            spec=spec,
            scope_level=scope_level,
            scope_code=scope_code,
            include_location=include_location,
            weighting=weighting,
            coefficients=[],
            equation="",
            warnings=warnings,
            sample_breakdown=breakdown,
            reference_categories={
                "brand": BRAND_REFERENCE_LABEL,
                "structure": STRUCTURE_REFERENCE,
                "vintage": VINTAGE_REFERENCE,
            },
            n_buildings=len(work),
            adj_r_squared=None,
        )

    use_w = weighting == "wls" and weights is not None
    if use_w:
        model = sm.WLS(y, x, weights=weights).fit(cov_type="HC3")
    else:
        model = sm.OLS(y, x).fit(cov_type="HC3")

    vif_map = _compute_vif(x) if spec == "C" else {}
    boot = _bootstrap_ci(work, x, y, weights if use_w else None, reps=bootstrap_reps)

    coef_rows: list[dict[str, Any]] = []
    coef_dict = {k: float(v) for k, v in model.params.items()}
    for name in model.params.index:
        if name == "const":
            continue
        c = float(model.params[name])
        se = float(model.bse[name]) if name in model.bse.index else None
        p = float(model.pvalues[name]) if name in model.pvalues.index else None
        ci_lo = c - 1.96 * se if se is not None else None
        ci_hi = c + 1.96 * se if se is not None else None
        boot_lo, boot_hi = boot.get(name, (None, None))
        n_bld = None
        if name.startswith("brand_"):
            key = name.replace("brand_", "")
            n_bld = int((work["brand_term"] == key).sum())
        elif name.startswith("builder_"):
            key = name.replace("builder_", "")
            n_bld = int((work["builder_term"] == key).sum())
        coef_rows.append(
            {
                "term": name,
                "term_label": labels.get(name, name),
                "term_kind": _term_kind(name),
                "coef": round(c, 6),
                "pct_effect": round((np.exp(c) - 1) * 100, 4),
                "se": round(se, 6) if se is not None else None,
                "p_value": round(p, 6) if p is not None else None,
                "ci_low": round(ci_lo, 6) if ci_lo is not None else None,
                "ci_high": round(ci_hi, 6) if ci_hi is not None else None,
                "boot_ci_low": round(boot_lo, 6) if boot_lo is not None else None,
                "boot_ci_high": round(boot_hi, 6) if boot_hi is not None else None,
                "n_buildings": n_bld,
                "vif": round(vif_map[name], 4) if name in vif_map else None,
            }
        )

    equation = _format_equation(labels, coef_dict)
    ref_cats = {
        "brand": BRAND_REFERENCE_LABEL,
        "builder": BUILDER_OTHER_LABEL,
        "structure": STRUCTURE_REFERENCE,
        "vintage": VINTAGE_REFERENCE,
        "spec": SPEC_LABELS.get(spec, spec),
    }

    return AttributeEffectsResult(
        spec=spec,
        scope_level=scope_level,
        scope_code=scope_code,
        include_location=include_location,
        weighting=weighting,
        coefficients=coef_rows,
        equation=equation,
        warnings=warnings,
        sample_breakdown=breakdown,
        reference_categories=ref_cats,
        n_buildings=len(work),
        adj_r_squared=round(float(model.rsquared_adj), 5) if model.rsquared_adj is not None else None,
    )


def run_block_l_macro(
    base_df: pd.DataFrame,
    macro_df: pd.DataFrame,
    *,
    as_of_month,
    window_years: int,
    asset_type: str = "apartment",
) -> AttributeEffectsResult:
    """블록 L: sigungu_base_ln_price ~ 시군구 인구·토지P50·임대P50."""
    work = base_df.merge(macro_df, on="sigungu_code", how="inner")
    breakdown = {"initial_sigungu": len(base_df), "after_macro_join": len(work)}
    warnings: list[str] = []
    if len(work) < 10:
        warnings.append("블록 L 표본 부족(시군구 10 미만)")
        return AttributeEffectsResult(
            spec="L",
            scope_level="national",
            scope_code=None,
            include_location=False,
            weighting="ols",
            coefficients=[],
            equation="",
            warnings=warnings,
            sample_breakdown=breakdown,
            reference_categories={},
            n_buildings=len(work),
            adj_r_squared=None,
            controls_note="1단계에서 분리한 시군구 기준 log(㎡당가)를 지역 거시변수로 설명합니다.",
        )

    y = work["base_ln_price"].astype(float)
    x = work[["sigungu_population", "sigungu_land_p50", "sigungu_rent_p50"]].astype(float)
    x = sm.add_constant(x)
    labels = {
        "const": "절편",
        "sigungu_population": "시군구 인구",
        "sigungu_land_p50": "시군구 주거×대 토지 P50",
        "sigungu_rent_p50": "시군구 아파트 전세 P50",
    }
    model = sm.OLS(y, x).fit(cov_type="HC3")
    coef_rows: list[dict[str, Any]] = []
    coef_dict = {k: float(v) for k, v in model.params.items()}
    for name in model.params.index:
        if name == "const":
            continue
        c = float(model.params[name])
        se = float(model.bse[name])
        p = float(model.pvalues[name])
        coef_rows.append(
            {
                "term": name,
                "term_label": labels[name],
                "term_kind": "macro",
                "coef": round(c, 6),
                "pct_effect": None,
                "se": round(se, 6),
                "p_value": round(p, 6),
                "ci_low": round(c - 1.96 * se, 6),
                "ci_high": round(c + 1.96 * se, 6),
                "boot_ci_low": None,
                "boot_ci_high": None,
                "n_buildings": len(work),
                "vif": None,
            }
        )

    return AttributeEffectsResult(
        spec="L",
        scope_level="national",
        scope_code=None,
        include_location=False,
        weighting="ols",
        coefficients=coef_rows,
        equation=_format_equation(labels, coef_dict),
        warnings=warnings,
        sample_breakdown=breakdown,
        reference_categories={"dependent": "base_ln_price(1단계 시군구 기준수준)"},
        n_buildings=len(work),
        adj_r_squared=round(float(model.rsquared_adj), 5),
        controls_note="단지 시공사·브랜드는 포함하지 않습니다.",
    )
