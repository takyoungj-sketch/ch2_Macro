"""임대 C-2 배정. 새 조각 번호를 만들지 않는다."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "pipeline"))

from collective.building_keys import apply_rent_c2_assignment, c2_key  # noqa: E402

BASE = "b" * 64
RAW = "apartment|서울|강남|역삼|name:한빛"
UNITS = {
    (BASE, "1111010100", "10"): (0, "split"),
    (BASE, "1111010100", "11"): (1, "split"),
}


def _frame(lots: list[str]) -> pd.DataFrame:
    return pd.DataFrame({
        "building_key": [BASE] * len(lots),
        "asset_type": ["apartment"] * len(lots),
        "beopjungri_code": ["1111010100"] * len(lots),
        "lot_number": lots,
    })


def test_empty_table_keeps_keys():
    df = _frame(["10"])
    out = apply_rent_c2_assignment(df, "apartment", units=None)
    assert out["building_key"].tolist() == [BASE]
    assert out.attrs["rent_c2_pending"] == []
    assert out.attrs["rent_c2_new_parts"] == []


def test_known_part_and_unknown_lot_then_same_input_is_unchanged():
    df = _frame(["11", "12"])
    first = apply_rent_c2_assignment(df, "apartment", units=UNITS, raw_of={BASE: RAW})
    assert first["building_key"].tolist() == [c2_key(RAW, "p1"), BASE]
    assert len(first.attrs["rent_c2_pending"]) == 1
    assert first.attrs["rent_c2_pending"][0]["part"] == 0
    assert first.attrs["rent_c2_pending"][0]["decision"] == "pending"
    assert first.attrs["rent_c2_new_parts"] == []
    merged = dict(UNITS)
    row = first.attrs["rent_c2_pending"][0]
    merged[(row["base_key"], row["beopjungri_code"], row["main_lot"])] = (0, "pending")
    second = apply_rent_c2_assignment(df, "apartment", units=merged, raw_of={BASE: RAW})
    assert second["building_key"].tolist() == first["building_key"].tolist()
    assert second.attrs["rent_c2_pending"] == []
    assert second.attrs["rent_c2_new_parts"] == []


def test_unique_collective_part_does_not_create_a_new_part():
    df = _frame(["13"])
    out = apply_rent_c2_assignment(
        df,
        "apartment",
        units=UNITS,
        collective_unique={(BASE, "1111010100", "13"): 2},
        raw_of={BASE: RAW},
    )
    assert out["building_key"].tolist() == [c2_key(RAW, "p2")]
    assert out.attrs["rent_c2_pending"] == []
    assert out.attrs["rent_c2_new_parts"] == []


def test_keep_group_and_unknown_base_do_not_pending():
    keep = {(BASE, "1111010100", "10"): (0, "keep")}
    kept = apply_rent_c2_assignment(_frame(["99"]), "apartment", units=keep, raw_of={BASE: RAW})
    assert kept["building_key"].tolist() == [BASE]
    assert kept.attrs["rent_c2_pending"] == []
    other = _frame(["12"])
    other["building_key"] = "c" * 64
    missed = apply_rent_c2_assignment(other, "apartment", units=UNITS, raw_of={BASE: RAW})
    assert missed["building_key"].tolist() == ["c" * 64]
    assert missed.attrs["rent_c2_pending"] == []
