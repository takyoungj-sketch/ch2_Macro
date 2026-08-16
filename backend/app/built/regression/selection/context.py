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


def resolve_selection_context(conn, req: RegressionRunRequest) -> SelectionContext:
    wide_df, req, addr4_city, mode = _prepare_regression_scope(conn, req)
    level = _focus_admin_level(req, addr4_city)
    df = _scope_for_level(wide_df, req, level, addr4_city, mode)
    label = _label_for_level(req, wide_df, level, addr4_city)
    return SelectionContext(
        df=df,
        scope_label=label,
        admin_level=level,
        addr4_city=addr4_city,
        mode=mode,
        unified=is_unified(req.asset_type),
    )


_BLOCK_SOURCE_COLUMNS: dict[str, tuple[str, ...]] = {
    "gross_area": ("gross_area",),
    "land_area": ("land_area",),
    "building_age": ("building_age",),
    "road_width": ("road_width_label",),
    "zone_type": ("zone_type",),
    "building_use": ("building_use",),
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
    """모든 후보가 공유할 complete-case 표본을 고정한다.

    후보별로 필요한 컬럼만 결측 제거하면 모델마다 n이 달라져
    AIC/BIC/MAPE 비교가 공정하지 않다. 후보 풀의 원천 컬럼 합집합과
    종속변수(price)를 한 번에 고정하고 이후 적합은 이 표본만 사용한다.
    """
    columns: list[str] = ["price"]
    for block in blocks:
        for column in _BLOCK_SOURCE_COLUMNS.get(block, ()):
            if column not in columns:
                columns.append(column)
    if "region_leaf" in blocks and region_col and region_col not in columns:
        columns.append(region_col)

    available = [column for column in columns if column in ctx.df.columns]
    sample = ctx.df.loc[:, available].copy()
    for column in available:
        if sample[column].dtype == object:
            sample[column] = sample[column].replace(r"^\s*$", pd.NA, regex=True)
    sample = sample.dropna(subset=available)
    # log 후보가 함께 존재할 수 있으므로 모든 후보의 공통 표본에서 양수 가격만 허용한다.
    if "price" in sample.columns:
        sample = sample[pd.to_numeric(sample["price"], errors="coerce") > 0]
    return replace(
        ctx,
        df=ctx.df.loc[sample.index].copy(),
        sample_columns=tuple(available),
        selection_n=len(sample),
    )


def region_col_for_context(ctx: SelectionContext, spec) -> str | None:
    return _region_col_for_scatter(spec, ctx.admin_level, ctx.addr4_city)
