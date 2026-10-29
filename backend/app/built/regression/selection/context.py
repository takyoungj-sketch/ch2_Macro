"""회귀 scope — 모형 선택용 primary level 표본."""

from __future__ import annotations

from dataclasses import dataclass, replace

import pandas as pd

from app.built.asset_scope import is_unified
from app.built.regression.engine import (
    CompareMode,
    _focus_admin_level,
    _label_for_level,
    _prepare_regression_scope,
    _region_col_for_scatter,
    _scope_for_level,
)
from app.built.regression.price_index import TimeAdjuster, last_complete_year
from app.built.schemas import AdminLevel, RegressionRunRequest, ResponseScale


@dataclass(frozen=True)
class SelectionContext:
    df: pd.DataFrame
    scope_label: str
    admin_level: AdminLevel
    addr4_city: bool
    mode: CompareMode
    unified: bool
    sample_columns: tuple[str, ...] = ()
    selection_n: int = 0
    numeric_drop_notes: tuple[str, ...] = ()
    # 시점 보정 지수원 (D-075) — **기본 None(보정 없음).** `time_adjust`를 켠 실험 경로에서만
    # 채워진다. 국소 표본은 연도별로 너무 얇아 지수를 못 세우므로 항상 시군구 표본에서 추정한다.
    time_adjuster: TimeAdjuster | None = None


def resolve_selection_context(conn, req: RegressionRunRequest) -> SelectionContext:
    wide_df, req, addr4_city, mode, _partial_tx_count = _prepare_regression_scope(conn, req)
    level = _focus_admin_level(req, addr4_city)
    df = _scope_for_level(wide_df, req, level, addr4_city, mode, conn=conn)
    label = _label_for_level(req, wide_df, level, addr4_city)
    return SelectionContext(
        df=df,
        scope_label=label,
        admin_level=level,
        addr4_city=addr4_city,
        mode=mode,
        unified=is_unified(req.asset_type),
        time_adjuster=(
            TimeAdjuster(wide_df, max_complete_year=last_complete_year(req.as_of_month))
            if getattr(req, "time_adjust", False)
            else None
        ),
    )


_NUMERIC_SOURCE_COLUMNS: dict[str, tuple[tuple[str, str], ...]] = {
    "gross_area": (("gross_area", "연면적 결측"),),
    "land_area": (("land_area", "대지면적 결측"),),
    "building_age": (("building_age", "연식 결측"),),
    "region_population": (("region_population", "지역인구 결측"),),
    "region_land_p50": (("region_land_p50", "지역토지가격 결측"),),
    "region_apt_p50": (("region_apt_p50", "지역아파트가격 결측"),),
    "region_apt_n": (("region_apt_n", "지역아파트거래량 결측"),),
    "region_comm_p50": (("region_comm_p50", "지역상가가격 결측"),),
    "region_comm_n": (("region_comm_n", "지역상가거래량 결측"),),
}

_BLOCK_SOURCE_COLUMNS: dict[str, tuple[str, ...]] = {
    "gross_area": ("gross_area",),
    "land_area": ("land_area",),
    "building_age": ("building_age",),
    "road_width": ("road_width_label",),
    "zone_type": ("zone_type",),
    "building_use": ("building_use",),
    "structure": ("structure_group",),
    "asset_type": ("asset_type",),
    "region_population": ("region_population",),
    "region_land_p50": ("region_land_p50",),
    "region_apt_p50": ("region_apt_p50",),
    "region_apt_n": ("region_apt_n",),
    "region_comm_p50": ("region_comm_p50",),
    "region_comm_n": ("region_comm_n",),
}


def with_complete_case(
    ctx: SelectionContext,
    blocks: list[str],
    *,
    region_col: str | None,
) -> SelectionContext:
    """후보가 공유할 표본을 고정한다.

    숫자 빈칸과 0 이하 금액·면적은 풀에 오른 숫자 열 기준으로 한 번만 뺀다.
    한 행은 한 사유만 센다. 범주 빈칸은 빼지 않고, 적합 때 미상으로 남긴다.
    """
    columns: list[str] = ["price"]
    numeric: list[tuple[str, str]] = []
    for block in blocks:
        for column in _BLOCK_SOURCE_COLUMNS.get(block, ()):
            if column not in columns:
                columns.append(column)
        for column, label in _NUMERIC_SOURCE_COLUMNS.get(block, ()):
            if column not in {name for name, _label in numeric}:
                numeric.append((column, label))
    if "region_leaf" in blocks and region_col and region_col not in columns:
        columns.append(region_col)

    available = [column for column in columns if column in ctx.df.columns]
    keep = pd.Series(True, index=ctx.df.index)
    notes: list[str] = []
    if "price" in ctx.df.columns:
        price = pd.to_numeric(ctx.df["price"], errors="coerce")
        bad_price = keep & (price.isna() | ~(price > 0))
        n_bad = int(bad_price.sum())
        if n_bad:
            notes.append(f"금액 없음·0 이하 {n_bad}건")
            keep = keep & ~bad_price
    for column, label in numeric:
        if column not in ctx.df.columns:
            continue
        values = pd.to_numeric(ctx.df[column], errors="coerce")
        missing = keep & values.isna()
        n_missing = int(missing.sum())
        if n_missing:
            notes.append(f"{label} {n_missing}건")
            keep = keep & ~missing
        if column in {"gross_area", "land_area"}:
            nonpositive = keep & values.notna() & ~(values > 0)
            n_nonpositive = int(nonpositive.sum())
            if n_nonpositive:
                notes.append(f"면적 0 이하 {n_nonpositive}건")
                keep = keep & ~nonpositive
    sample = ctx.df.loc[keep]
    return replace(
        ctx,
        df=sample.copy(),
        sample_columns=tuple(available),
        selection_n=len(sample),
        numeric_drop_notes=tuple(notes),
    )


def region_col_for_context(ctx: SelectionContext, spec) -> str | None:
    return _region_col_for_scatter(spec, ctx.admin_level, ctx.addr4_city)
