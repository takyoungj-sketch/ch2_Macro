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


def fit_is_offerable(fit) -> bool:
    """복합 최소 건수 통과 뒤, 계산 불가(잔차 자유도 없음)는 순위에서 뺀다."""
    if int(getattr(fit, "n", 0)) < built_min_fit_n():
        return False
    model = getattr(fit, "model", None)
    exog = getattr(getattr(model, "model", None), "exog", None)
    if exog is None:
        return False
    try:
        from app.regression_sample_judge import judge_exog

        return judge_exog(exog).tier != "blocked"
    except (AttributeError, TypeError, ValueError):
        return False


def resolve_recommendation_pool(
    ctx: SelectionContext,
    *,
    unified: bool,
    min_leaves_for_region: int = 2,
    include_structure: bool = False,
) -> list[BlockId]:
    """구조는 대장보강과 구조 체크가 있을 때만. 호출부가 그 조건을 넘긴다."""
    pool: list[BlockId] = [
        block
        for block in DEFAULT_BUILT_CANDIDATE_BLOCKS
        if block != "structure" or include_structure
    ]
    if unified:
        pool.append("asset_type")
    if count_scope_leaves(ctx) >= min_leaves_for_region:
        pool.append("region_leaf")
    return pool
