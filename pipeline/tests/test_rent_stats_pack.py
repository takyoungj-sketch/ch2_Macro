"""임대 건물 마트 — 전세/반전세/순수월세 단가 분리."""

from __future__ import annotations

import sys
from pathlib import Path

PIPE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PIPE))

from rent.stats_pack import has_any_lease, pack_building_lease_stats, pack_metric


def test_pack_metric_empty():
    st = pack_metric([])
    assert st["n"] == 0
    assert st["median"] is None


def test_pack_metric_median_before_mean_shape():
    st = pack_metric([100, 120, 500])
    assert st["n"] == 3
    assert st["median"] == 120
    assert st["mean"] is not None


def test_pack_three_structures_not_merged():
    row = {
        "jeonse_deposit": [350.0, 360.0],
        "mixed_deposit": [80.0, 90.0],
        "mixed_monthly": [1.1, 1.3],
        "monthly_rent": [2.3],
    }
    st = pack_building_lease_stats(row)
    assert st["jeonse_n"] == 2
    assert st["jeonse_median"] == 355.0
    assert st["mixed_n"] == 2
    assert st["mixed_deposit_median"] == 85.0
    assert st["mixed_monthly_median"] == 1.2
    assert st["monthly_n"] == 1
    assert st["monthly_median"] == 2.3
    assert has_any_lease(st)


def test_pure_monthly_has_no_deposit_stats():
    st = pack_building_lease_stats(
        {
            "jeonse_deposit": None,
            "mixed_deposit": None,
            "mixed_monthly": None,
            "monthly_rent": [2.1, 2.5],
        }
    )
    assert st["jeonse_n"] == 0
    assert st["mixed_n"] == 0
    assert st["monthly_n"] == 2
    assert st["monthly_median"] == 2.3
