"""집합 신규 키 조인 — A·B·C 미덮기."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from build_collective_building_attributes import filter_new_attribute_rows
from parcel_master.apply_title_fill import BLOCKED_TIERS, filter_fills_new_keys


def test_filter_new_attribute_rows_keeps_missing_keys():
    attrs = pd.DataFrame(
        {
            "building_key": ["aaa", "bbb", "ccc"],
            "match_tier": ["A", "Z", "B"],
        }
    )
    got = filter_new_attribute_rows(attrs, {"aaa", "ccc"})
    assert list(got["building_key"]) == ["bbb"]


def test_filter_fills_new_keys_drops_existing_rows():
    fills = [
        {"building_key": "n", "has_attr_row": False},
        {"building_key": "t", "has_attr_row": True},
    ]
    got = filter_fills_new_keys(fills)
    assert [r["building_key"] for r in got] == ["n"]


def test_abc_are_blocked_tiers():
    assert {"A", "B", "C"}.issubset(BLOCKED_TIERS)
    assert "T" not in BLOCKED_TIERS


def test_empty_f_is_not_title_blocked():
    from parcel_master.apply_title_fill import title_fill_blocked

    assert title_fill_blocked("F", None) is False
    assert title_fill_blocked("F", "A10023786") is True
    assert title_fill_blocked("A", None) is True
    assert title_fill_blocked("Z", None) is False
