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
        structure_dummy=False,
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
        structure_dummy=False,
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
        structure_dummy=False,
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


def test_enumerate_block_subsets_ascending_size():
    """블록 수 오름차순 — 상한에 걸려도 특정 블록이 통째로 빠지지 않는다."""
    cands = ["gross_area", "land_area", "building_age", "zone_type"]
    subs = enumerate_block_subsets(cands)
    sizes = [len(s) for s in subs]
    assert sizes == sorted(sizes)
    assert [s for s in subs if len(s) == 1] == [[c] for c in cands]


def test_enumerate_block_subsets_cap_keeps_every_block():
    cands = [f"b{i}" for i in range(9)]
    subs = enumerate_block_subsets(cands, max_count=20)
    assert len(subs) == 20
    covered = {b for s in subs for b in s}
    assert covered == set(cands)


def test_estimable_columns_drops_constant_dummy():
    """학습 fold에 없는 범주의 더미는 계수를 추정할 수 없어 빠진다."""
    import pandas as pd

    from app.built.regression.selection.fit import _estimable_columns

    frame = pd.DataFrame(
        {
            "const": [1.0, 1.0, 1.0, 1.0],
            "gross_area": [30.0, 45.0, 52.0, 61.0],
            "zone_Z9": [0.0, 0.0, 0.0, 0.0],
        }
    )
    assert _estimable_columns(frame) == ["const", "gross_area"]


def test_estimable_columns_skips_collinear_fold():
    import pandas as pd

    from app.built.regression.selection.fit import _estimable_columns

    frame = pd.DataFrame(
        {
            "const": [1.0, 1.0, 1.0],
            "use_a": [1.0, 0.0, 1.0],
            "use_b": [0.0, 1.0, 0.0],
        }
    )
    assert _estimable_columns(frame) == []
