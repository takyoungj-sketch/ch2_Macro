"""PNU 구코드 맵핑 · 표제부 캐시 이름."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from parcel_master.load_title_pilot import cache_path
from parcel_master.paths import ALL_SIDO, PILOT_SIDO
from parcel_master.pnu import remap_pnu_old_sido


def test_remap_skips_seoul():
    pnu = "1150010800100140162"
    assert remap_pnu_old_sido(pnu, {"2911010100": "1211010100"}) == pnu


def test_remap_gwangju_jeonnam_uses_bjd_map():
    old = "2917010100100010001"
    mapping = {"2917010100": "1217010100"}
    assert remap_pnu_old_sido(old, mapping) == "1217010100100010001"


def test_remap_missing_keeps_old_bjd():
    old = "4611010100100010001"
    assert remap_pnu_old_sido(old, {}) == old


def test_cache_path_separates_kinds():
    snap = "2026-07"
    a = cache_path(PILOT_SIDO, snap, "집합")
    b = cache_path(PILOT_SIDO, snap, "일반")
    assert "집합" in a.name
    assert "일반" in b.name
    assert a != b
    nat = cache_path(ALL_SIDO, snap, "일반")
    assert "national" in nat.name
