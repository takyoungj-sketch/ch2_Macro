"""변수 블록 SSOT — Group Model Selection (D-028).

탐색 단위 = 사용자 토글 1개 = 연속 1컬럼 또는 더미 묶음 전체.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.built.schemas import RegressionVariableSpec

BlockId = Literal[
    "gross_area",
    "land_area",
    "building_age",
    "road_width",
    "zone_type",
    "building_use",
    "structure",
    "asset_type",
    "region_leaf",
    "region_population",
    "region_land_p50",
    "region_apt_p50",
    "region_apt_n",
    "region_comm_p50",
    "region_comm_n",
]


@dataclass(frozen=True)
class VariableBlock:
    block_id: BlockId
    label: str
    spec_field: str  # RegressionVariableSpec bool field


BLOCKS: tuple[VariableBlock, ...] = (
    VariableBlock("gross_area", "연면적", "gross_area"),
    VariableBlock("land_area", "대지면적", "land_area"),
    VariableBlock("building_age", "연식", "building_age"),
    VariableBlock("road_width", "도로조건", "road_width_dummy"),
    VariableBlock("zone_type", "용도지역", "zone_type_dummy"),
    VariableBlock("building_use", "건축물용도", "building_use_dummy"),
    VariableBlock("structure", "구조", "structure_dummy"),
    VariableBlock("asset_type", "유형", "asset_type_dummy"),
    VariableBlock("region_leaf", "지역(읍·면·동)", "region_leaf_dummy"),
    VariableBlock("region_population", "지역인구", "region_population"),
    VariableBlock("region_land_p50", "지역토지가격", "region_land_p50"),
    VariableBlock("region_apt_p50", "지역아파트가격", "region_apt_p50"),
    VariableBlock("region_apt_n", "지역아파트거래량", "region_apt_n"),
    VariableBlock("region_comm_p50", "지역상가가격", "region_comm_p50"),
    VariableBlock("region_comm_n", "지역상가거래량", "region_comm_n"),
)

_BLOCK_BY_ID: dict[str, VariableBlock] = {b.block_id: b for b in BLOCKS}


def block_label(block_id: str) -> str:
    b = _BLOCK_BY_ID.get(block_id)
    return b.label if b else block_id


def candidate_blocks_from_spec(
    spec: RegressionVariableSpec,
    *,
    unified: bool = False,
) -> list[BlockId]:
    """variables=True 인 블록만 후보 풀 (순서 SSOT)."""
    out: list[BlockId] = []
    for b in BLOCKS:
        if b.block_id == "asset_type" and not unified:
            continue
        if getattr(spec, b.spec_field, False):
            out.append(b.block_id)
    return out


def spec_from_blocks(
    blocks: list[BlockId] | list[str],
    *,
    base: RegressionVariableSpec | None = None,
) -> RegressionVariableSpec:
    """블록 집합 → RegressionVariableSpec (미포함 블록 False)."""
    chosen = set(blocks)
    data = (base or RegressionVariableSpec()).model_dump()
    for b in BLOCKS:
        data[b.spec_field] = b.block_id in chosen
    return RegressionVariableSpec(**data)


def subset_to_mask(blocks: list[BlockId], candidates: list[BlockId]) -> int:
    """후보 블록 순서에 대한 bitmask (best subset enumeration)."""
    mask = 0
    for i, cid in enumerate(candidates):
        if cid in blocks:
            mask |= 1 << i
    return mask


def mask_to_blocks(mask: int, candidates: list[BlockId]) -> list[BlockId]:
    return [candidates[i] for i in range(len(candidates)) if mask & (1 << i)]


def subset_count(candidates: list[BlockId]) -> int:
    n = len(candidates)
    return (1 << n) - 1 if n else 0


def enumerate_block_subsets(
    candidates: list[BlockId],
    *,
    max_count: int | None = None,
) -> list[list[BlockId]]:
    """공집합 제외, 전체 포함 — 2^k - 1 subsets (max_count로 상한)."""
    n = len(candidates)
    if n == 0:
        return []
    total = (1 << n) - 1
    limit = total if max_count is None else min(total, max_count)
    out: list[list[BlockId]] = []
    for mask in range(1, 1 << n):
        if len(out) >= limit:
            break
        out.append(mask_to_blocks(mask, candidates))
    return out
