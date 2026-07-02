"""cycle_utils — collection_yyyymm_range 테스트."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from cycle_utils import (  # noqa: E402
    collection_yyyymm_range_from_cycle_id,
    stats_as_of_iso_from_cycle_id,
)


def test_collection_range_202607() -> None:
    y_from, y_to = collection_yyyymm_range_from_cycle_id("202607")
    assert y_from == "202507"
    assert y_to == "202606"


def test_stats_as_of_202607() -> None:
    assert stats_as_of_iso_from_cycle_id("202607") == "2026-06-01"
