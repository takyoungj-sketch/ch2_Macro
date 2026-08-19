"""1단계 시군구 OLS — 단지 품질지수."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import numpy as np
import pandas as pd
import statsmodels.api as sm

from app.collective.hedonic.constants import (
    MIN_BUILDINGS_PER_SIGUNGU,
    MIN_TX_PER_BUILDING,
    MIN_TX_PER_SIGUNGU,
    OUTLIER_IQR_MULTIPLIER,
    REF_FLOOR_GROUP,
)
from app.collective.regression.engine import relative_floor_group


@dataclass
class SigunguStage1Result:
    sigungu_code: str
    building_rows: list[dict]
    base_row: dict
    warnings: list[str] = field(default_factory=list)


@dataclass
class Stage1BuildResult:
    building_rows: list[dict]
    base_rows: list[dict]
    warnings: list[str]
    excluded_sigungu: int
    included_sigungu: int


def apply_iqr_filter(df: pd.DataFrame, *, multiplier: float = OUTLIER_IQR_MULTIPLIER) -> pd.DataFrame:
    work = df.dropna(subset=["unit_price"]).copy()
    if len(work) < 4:
        return work
    up = work["unit_price"].astype(float)
    q1, q3 = up.quantile(0.25), up.quantile(0.75)
    iqr = float(q3 - q1)
    lo, hi = float(q1 - multiplier * iqr), float(q3 + multiplier * iqr)
    return work[(up >= lo) & (up <= hi)]


def _vintage_year(row: pd.Series) -> int | None:
    for col in ("approved_year", "building_year"):
        val = row.get(col)
        if val is not None and not (isinstance(val, float) and np.isnan(val)):
            try:
                return int(val)
            except (TypeError, ValueError):
                pass
    return None


def _prepare_sigungu_frame(df: pd.DataFrame, ref_year: int) -> pd.DataFrame:
    work = df.copy()
    work["ln_price"] = np.log(work["unit_price"].astype(float))
    work["ln_area"] = np.log(work["exclusive_area"].astype(float).clip(lower=1e-6))
    work["contract_year"] = work["contract_year"].astype("Int64")
    work = work[work["contract_year"].notna()]
    max_by_bk = work.groupby("building_key")["floor"].max().to_dict()
    work["floor_group"] = work.apply(
        lambda r: relative_floor_group(
            r.get("floor"),
            max_by_bk.get(r["building_key"], r.get("floor")),
        ),
        axis=1,
    )
    years = sorted(int(y) for y in work["contract_year"].dropna().unique())
    work["year_cat"] = work["contract_year"].astype(str)
    return work, years


def _design_matrix(work: pd.DataFrame, ref_year: int) -> tuple[pd.DataFrame, pd.Series, str, list[str]]:
    warnings: list[str] = []
    bld_dummies = pd.get_dummies(work["building_key"].astype(str), prefix="bld", drop_first=True)
    ref_building = str(work.groupby("building_key").size().idxmax())
    floor_cats = [c for c in work["floor_group"].dropna().unique() if c != REF_FLOOR_GROUP]
    floor_part = pd.get_dummies(work["floor_group"], prefix="", prefix_sep="", drop_first=False)
    if REF_FLOOR_GROUP in floor_part.columns:
        floor_part = floor_part.drop(columns=[REF_FLOOR_GROUP])
    for col in floor_cats:
        if col not in floor_part.columns:
            floor_part[col] = 0.0
    floor_part = floor_part[[c for c in floor_part.columns if c != REF_FLOOR_GROUP]]

    year_str = str(ref_year)
    year_part = pd.get_dummies(work["year_cat"], prefix="yr", drop_first=False)
    if f"yr_{year_str}" in year_part.columns:
        year_part = year_part.drop(columns=[f"yr_{year_str}"])

    x_parts = [
        work[["ln_area"]].astype(float),
        floor_part.astype(float),
        year_part.astype(float),
        bld_dummies.astype(float),
    ]
    x = pd.concat(x_parts, axis=1)
    x = sm.add_constant(x, has_constant="add")
    y = work["ln_price"].astype(float)
    return x, y, ref_building, warnings


def _extract_building_effects(
    model: sm.regression.linear_model.RegressionResultsWrapper,
    buildings: list[str],
    ref_building: str,
) -> dict[str, tuple[float, float | None]]:
    out: dict[str, tuple[float, float | None]] = {}
    ref_coef = 0.0
    ref_se = None
    for bk in buildings:
        col = f"bld_{bk}"
        if col in model.params.index:
            coef = float(model.params[col])
            se = float(model.bse[col]) if col in model.bse.index else None
        elif bk == ref_building:
            coef, se = 0.0, None
        else:
            coef, se = 0.0, None
        out[bk] = (coef, se)
    if ref_building not in out:
        out[ref_building] = (ref_coef, ref_se)
    return out


def _center_effects(raw: dict[str, tuple[float, float | None]]) -> dict[str, tuple[float, float | None]]:
    coefs = np.array([v[0] for v in raw.values()], dtype=float)
    mean = float(np.mean(coefs))
    centered: dict[str, tuple[float, float | None]] = {}
    for bk, (c, se) in raw.items():
        centered[bk] = (c - mean, se)
    return centered


def _base_ln_price(
    model: sm.regression.linear_model.RegressionResultsWrapper,
    *,
    ref_area: float,
    ref_year: int,
) -> tuple[float, float | None]:
    val = float(model.params.get("const", 0.0))
    area_beta = float(model.params.get("ln_area", 0.0))
    val += area_beta * np.log(max(ref_area, 1e-6))
    yr_col = f"yr_{ref_year}"
    if yr_col in model.params.index:
        val += float(model.params[yr_col])
    return val, area_beta


def fit_sigungu_stage1(
    df: pd.DataFrame,
    sigungu_code: str,
    *,
    as_of_month: date,
    window_years: int,
    asset_type: str,
    ref_year: int,
) -> SigunguStage1Result | None:
    warnings: list[str] = []
    work = apply_iqr_filter(df)
    if work.empty:
        return None

    bld_counts = work.groupby("building_key").size()
    eligible = bld_counts[bld_counts >= MIN_TX_PER_BUILDING].index.tolist()
    work = work[work["building_key"].isin(eligible)]
    if len(eligible) < MIN_BUILDINGS_PER_SIGUNGU or len(work) < MIN_TX_PER_SIGUNGU:
        return None

    ref_area = float(work["exclusive_area"].astype(float).median())
    work, _years = _prepare_sigungu_frame(work, ref_year)
    if work["building_key"].nunique() < MIN_BUILDINGS_PER_SIGUNGU:
        return None

    try:
        x, y, ref_building, _ = _design_matrix(work, ref_year)
        if x.shape[0] <= x.shape[1] + 2:
            warnings.append(f"시군구 {sigungu_code}: 설계행렬 rank 부족 — 제외")
            return None
        model = sm.OLS(y, x).fit()
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"시군구 {sigungu_code}: OLS 실패 ({exc})")
        return None

    buildings = sorted(work["building_key"].astype(str).unique())
    raw = _extract_building_effects(model, buildings, ref_building)
    centered = _center_effects(raw)
    base_ln, area_beta = _base_ln_price(model, ref_area=ref_area, ref_year=ref_year)

    building_rows: list[dict] = []
    for bk in buildings:
        grp = work[work["building_key"] == bk]
        qi, qse = centered[bk]
        building_rows.append(
            {
                "as_of_month": as_of_month,
                "window_years": window_years,
                "asset_type": asset_type,
                "sigungu_code": sigungu_code,
                "building_key": bk,
                "quality_index": round(float(qi), 6),
                "quality_se": round(float(qse), 6) if qse is not None else None,
                "n_tx": int(len(grp)),
                "first_year": int(grp["contract_year"].min()),
                "last_year": int(grp["contract_year"].max()),
            }
        )

    base_row = {
        "as_of_month": as_of_month,
        "window_years": window_years,
        "asset_type": asset_type,
        "sigungu_code": sigungu_code,
        "base_ln_price": round(float(base_ln), 6),
        "ref_area": round(ref_area, 3),
        "ref_floor_group": REF_FLOOR_GROUP,
        "ref_year": ref_year,
        "area_beta": round(float(area_beta), 6) if area_beta is not None else None,
        "r_squared": round(float(model.rsquared), 5),
        "n_buildings": len(buildings),
        "n_tx": int(len(work)),
    }
    return SigunguStage1Result(
        sigungu_code=sigungu_code,
        building_rows=building_rows,
        base_row=base_row,
        warnings=warnings,
    )


def build_stage1_from_transactions(
    tx: pd.DataFrame,
    *,
    as_of_month: date,
    window_years: int,
    asset_type: str = "apartment",
) -> Stage1BuildResult:
    ref_year = as_of_month.year
    all_building: list[dict] = []
    all_base: list[dict] = []
    warnings: list[str] = []
    excluded = 0
    included = 0

    if tx.empty:
        return Stage1BuildResult([], [], ["거래 표본 없음"], 0, 0)

    for sg, grp in tx.groupby("sigungu_code"):
        if sg is None or (isinstance(sg, float) and np.isnan(sg)):
            excluded += 1
            continue
        res = fit_sigungu_stage1(
            grp,
            str(sg),
            as_of_month=as_of_month,
            window_years=window_years,
            asset_type=asset_type,
            ref_year=ref_year,
        )
        if res is None:
            excluded += 1
            continue
        included += 1
        all_building.extend(res.building_rows)
        all_base.append(res.base_row)
        warnings.extend(res.warnings)

    return Stage1BuildResult(
        building_rows=all_building,
        base_rows=all_base,
        warnings=warnings,
        excluded_sigungu=excluded,
        included_sigungu=included,
    )
