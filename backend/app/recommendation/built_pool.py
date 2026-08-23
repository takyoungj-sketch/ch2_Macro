"""Built SSOT 추천 변수 풀 (R1)."""

from __future__ import annotations

import pandas as pd

from app.built.regression.engine import _region_dummy_column
from app.built.regression.region_features import is_region_block
from app.built.regression.selection.blocks import BlockId, block_label, spec_from_blocks
from app.built.regression.selection.context import SelectionContext, _BLOCK_SOURCE_COLUMNS
from app.recommendation.satisfaction import built_min_fit_n

DEFAULT_BUILT_CANDIDATE_BLOCKS: tuple[BlockId, ...] = (
    "gross_area",
    "land_area",
    "building_age",
    "road_width",
    "zone_type",
    "building_use",
    "structure",
)


def count_scope_leaves(ctx: SelectionContext) -> int:
    spec = spec_from_blocks(["region_leaf"])
    col = _region_dummy_column(spec, ctx.admin_level, addr4_city=ctx.addr4_city)
    if not col or col not in ctx.df.columns:
        return 0
    series = ctx.df[col].dropna().astype(str).str.strip()
    return int(series[series != ""].nunique())


def _usable_rows_for_block(ctx: SelectionContext, block: BlockId) -> int:
    """price>0 및 블록 원천 컬럼 complete-case 건수."""
    if block == "region_leaf":
        return count_scope_leaves(ctx)

    columns = list(_BLOCK_SOURCE_COLUMNS.get(block, ()))
    if not columns or "price" not in ctx.df.columns:
        return 0

    available = [column for column in columns if column in ctx.df.columns]
    if not available:
        return 0

    sample = ctx.df.loc[:, ["price", *available]].copy()
    for column in available:
        if sample[column].dtype == object:
            sample[column] = sample[column].replace(r"^\s*$", pd.NA, regex=True)
    sample = sample.dropna(subset=["price", *available])
    sample = sample[pd.to_numeric(sample["price"], errors="coerce") > 0]
    return len(sample)


def filter_pool_by_coverage(
    ctx: SelectionContext,
    pool: list[BlockId],
    *,
    min_rows: int | None = None,
) -> tuple[list[BlockId], list[str]]:
    """표본에 유효 값이 거의 없는 블록은 SSOT 풀에서 제외한다."""
    threshold = built_min_fit_n() if min_rows is None else min_rows
    kept: list[BlockId] = []
    excluded: list[str] = []
    for block in pool:
        usable = _usable_rows_for_block(ctx, block)
        if usable < threshold:
            label = block_label(block)
            excluded.append(f"{label}({block}): 유효 {usable}건 (< {threshold})")
            continue
        # 단일 읍면동 Local이면 region 공변량은 상수 → 식별 불가
        if is_region_block(block):
            cols = _BLOCK_SOURCE_COLUMNS.get(block, ())
            col = cols[0] if cols else None
            if col and col in ctx.df.columns:
                nuniq = int(pd.to_numeric(ctx.df[col], errors="coerce").nunique(dropna=True))
                if nuniq < 2:
                    label = block_label(block)
                    excluded.append(f"{label}({block}): 상수(지역값 종류 {nuniq})")
                    continue
        kept.append(block)
    return kept, excluded


def resolve_recommendation_pool(
    ctx: SelectionContext,
    *,
    unified: bool,
    min_leaves_for_region: int = 2,
) -> list[BlockId]:
    pool: list[BlockId] = list(DEFAULT_BUILT_CANDIDATE_BLOCKS)
    if unified:
        pool.append("asset_type")
    if count_scope_leaves(ctx) >= min_leaves_for_region:
        pool.append("region_leaf")
    return pool
