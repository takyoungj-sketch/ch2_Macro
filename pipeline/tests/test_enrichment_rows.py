"""복원 확정 행 → enrichment 미리보기 레코드."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from built.enrichment_rows import structure_group, to_enrichment_records


def test_structure_group_src_before_rc():
    assert structure_group("철골철근콘크리트구조") == "SRC"
    assert structure_group("철근콘크리트구조") == "RC"
    assert structure_group("경량철골구조") == "철골"
    assert structure_group("벽돌구조") == "벽돌"
    assert structure_group("일반목구조") == "목"
    assert structure_group("") is None


def test_to_enrichment_records_skips_unknown_and_needs_hash():
    res = pd.DataFrame(
        [
            {
                "id": 1,
                "transaction_hash": "a" * 64,
                "tier": "A1",
                "parcel": "1111010100|146-6",
                "struct": "철근콘크리트구조",
                "floors": 2,
                "approve": 1994,
                "land_src": "title",
                "n_range": 3,
                "n_exact": 1,
                "tx_road": "중대로",
                "reg_road": "중대로154",
                "snapshot_used": "2024-09",
                "snapshot_via": "time",
            },
            {
                "id": 2,
                "transaction_hash": "b" * 64,
                "tier": None,
                "parcel": None,
                "struct": None,
                "floors": None,
                "approve": None,
                "land_src": None,
                "n_range": 0,
                "n_exact": 0,
                "tx_road": "",
                "reg_road": None,
                "snapshot_used": "2024-09",
                "snapshot_via": "time",
            },
            {
                "id": 3,
                "transaction_hash": None,
                "tier": "A2",
                "parcel": "1111010100|1-1",
                "struct": "벽돌구조",
                "floors": 1,
                "approve": 1980,
                "land_src": "land_ledger",
                "n_range": 5,
                "n_exact": 2,
                "tx_road": "가",
                "reg_road": "가",
                "snapshot_used": "2025-07",
                "snapshot_via": "fallback",
            },
        ]
    )
    recs = to_enrichment_records(
        res,
        [["제2종일반주거지역"], [], []],
        coverage_scope="full",
        matched_cycle="202608",
    )
    assert len(recs) == 1
    r = recs[0]
    assert r["match_tier"] == "A1"
    assert r["match_rule"] == "gross_exact"
    assert r["structure_group"] == "RC"
    assert r["zone_labels"] == ["제2종일반주거지역"]
    assert r["zone_source"] == "al_d155"
    assert r["snapshots_matched"] == ["2024-09"]
    assert r["evidence"]["road_contains"] is True
    assert r["land_area_source"] is None
