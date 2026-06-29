"""변수 블록 — Group Model Selection (D-028)."""

from __future__ import annotations

from app.built.regression.selection.blocks import (
    candidate_blocks_from_spec,
    enumerate_block_subsets,
    spec_from_blocks,
)
from app.built.schemas import RegressionVariableSpec


def test_candidate_blocks_from_spec():
    spec = RegressionVariableSpec(
        gross_area=True,
        land_area=True,
        building_age=False,
        road_width_dummy=True,
        zone_type_dummy=False,
        building_use_dummy=True,
        asset_type_dummy=False,
        region_leaf_dummy=False,
    )
    blocks = candidate_blocks_from_spec(spec, unified=False)
    assert blocks == ["gross_area", "land_area", "road_width", "building_use"]


def test_candidate_blocks_unified_includes_asset_type():
    spec = RegressionVariableSpec(
        gross_area=True,
        land_area=False,
        building_age=False,
        road_width_dummy=False,
        zone_type_dummy=False,
        building_use_dummy=False,
        asset_type_dummy=True,
        region_leaf_dummy=False,
    )
    blocks = candidate_blocks_from_spec(spec, unified=True)
    assert "asset_type" in blocks


def test_spec_from_blocks_roundtrip():
    spec = RegressionVariableSpec(
        gross_area=True,
        land_area=True,
        building_age=True,
        road_width_dummy=False,
        zone_type_dummy=True,
        building_use_dummy=False,
        asset_type_dummy=False,
        region_leaf_dummy=False,
    )
    blocks = candidate_blocks_from_spec(spec)
    rebuilt = spec_from_blocks(blocks)
    assert rebuilt.gross_area is True
    assert rebuilt.land_area is True
    assert rebuilt.building_age is True
    assert rebuilt.zone_type_dummy is True
    assert rebuilt.road_width_dummy is False
    assert rebuilt.building_use_dummy is False


def test_enumerate_block_subsets():
    cands = ["gross_area", "land_area", "building_age"]
    subs = enumerate_block_subsets(cands)
    assert len(subs) == 7  # 2^3 - 1
    assert ["gross_area"] in subs
    assert cands in subs
