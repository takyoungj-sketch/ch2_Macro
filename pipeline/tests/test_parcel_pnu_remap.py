"""PNU 구코드 맵핑 · 표제부 캐시 이름."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from parcel_master.load_title_pilot import cache_path
from parcel_master.paths import ALL_SIDO, PILOT_SIDO
from parcel_master.pnu import pick_incheon_old_bjd, remap_pnu_bjd, remap_pnu_old_sido


def test_remap_skips_seoul():
    pnu = "1150010800100140162"
    assert remap_pnu_old_sido(pnu, {"2911010100": "1211010100"}) == pnu


def test_remap_gwangju_jeonnam_uses_bjd_map():
    old = "2917010100100010001"
    mapping = {"2917010100": "1217010100"}
    assert remap_pnu_old_sido(old, mapping) == "1217010100100010001"


def test_remap_incheon_current_to_old():
    current = "2829010300101230001"
    mapping = {"2829010300": "2826011300"}
    assert remap_pnu_bjd(current, mapping) == "2826011300101230001"


def test_pick_incheon_geomdan_geumgok_uses_seogu():
    # 동구 금곡동과 이름이 같아도 검단은 서구만
    got = pick_incheon_old_bjd("2829010700", ["2826011800", "2814010600"])
    assert got == "2826011800"


def test_pick_incheon_jemulpo_geumgok_uses_donggu():
    got = pick_incheon_old_bjd("2812510600", ["2826011800", "2814010600"])
    assert got == "2814010600"


def test_pick_incheon_yeongjong_uses_junggu():
    got = pick_incheon_old_bjd("2815510100", ["2811014500"])
    assert got == "2811014500"


def test_cache_path_separates_kinds():
    snap = "2026-07"
    a = cache_path(PILOT_SIDO, snap, "집합")
    b = cache_path(PILOT_SIDO, snap, "일반")
    assert "집합" in a.name
    assert "일반" in b.name
    assert a != b
    nat = cache_path(ALL_SIDO, snap, "일반")
    assert "national" in nat.name
