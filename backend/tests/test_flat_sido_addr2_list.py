"""flat sido addr2 목록 — 오염 원장(세종 상가) 보정."""

from __future__ import annotations

from types import SimpleNamespace

from app.collective.meta_cache import clear_meta_cache
from app.flat_sido_region import (
    FLAT_SIDO_ADDR2_TOKEN,
    _addr2_values_look_like_misplaced_flat_leaves,
    list_addr2_for_sido,
)


def test_misplaced_flat_leaf_detection():
    assert _addr2_values_look_like_misplaced_flat_leaves(["조치원읍", "고운동"])
    assert not _addr2_values_look_like_misplaced_flat_leaves(["청주시", "흥덕구"])
    assert not _addr2_values_look_like_misplaced_flat_leaves(["수원시"])


def test_list_addr2_ttl_cache_skips_second_scan():
    clear_meta_cache()
    n = {"q": 0}

    class Row:
        def __init__(self, v: str):
            self.v = v

    class Conn:
        def execute(self, *args, **kwargs):
            n["q"] += 1
            return SimpleNamespace(fetchall=lambda: [Row("청주시")])

    conn = Conn()
    kwargs = dict(
        table="collective_transactions",
        addr1="충청북도",
        asset_type="apartment",
        valid_sql="is_valid = true",
    )
    first = list_addr2_for_sido(conn, **kwargs)
    second = list_addr2_for_sido(conn, **kwargs)
    assert first == second == ["청주시"]
    assert n["q"] == 1
    list_addr2_for_sido(conn, table="collective_transactions", addr1="경기도", asset_type="apartment", valid_sql="is_valid = true")
    assert n["q"] == 2


def test_list_addr2_sejong_commercial_flat_token():
    from app.collective.db import get_collective_engine

    eng = get_collective_engine()
    clear_meta_cache()
    with eng.connect() as conn:
        opts = list_addr2_for_sido(
            conn,
            table="collective_commercial_transactions",
            addr1="세종특별자치시",
            asset_type="collective_shop",
            valid_sql="is_valid = true",
        )
    assert opts == [FLAT_SIDO_ADDR2_TOKEN]
