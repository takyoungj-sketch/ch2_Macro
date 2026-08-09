"""flat sido addr2 목록 — 오염 원장(세종 상가) 보정."""

from __future__ import annotations

from app.flat_sido_region import (
    FLAT_SIDO_ADDR2_TOKEN,
    _addr2_values_look_like_misplaced_flat_leaves,
)


def test_misplaced_flat_leaf_detection():
    assert _addr2_values_look_like_misplaced_flat_leaves(["조치원읍", "고운동"])
    assert not _addr2_values_look_like_misplaced_flat_leaves(["청주시", "흥덕구"])
    assert not _addr2_values_look_like_misplaced_flat_leaves(["수원시"])


def test_list_addr2_sejong_commercial_flat_token():
    from app.collective.db import get_collective_engine
    from app.flat_sido_region import list_addr2_for_sido

    eng = get_collective_engine()
    with eng.connect() as conn:
        opts = list_addr2_for_sido(
            conn,
            table="collective_commercial_transactions",
            addr1="세종특별자치시",
            asset_type="collective_shop",
            valid_sql="is_valid = true",
        )
    assert opts == [FLAT_SIDO_ADDR2_TOKEN]
