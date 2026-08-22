"""용도지역 대분류는 코드가 아니라 라벨 이름 (D-047)."""

from __future__ import annotations

import sys
from pathlib import Path

_PIPELINE = Path(__file__).resolve().parents[2] / "pipeline"
sys.path.insert(0, str(_PIPELINE))

from parcel_master.zone import is_coarse_label, is_zone_code, zone_family  # noqa: E402


def test_coarse_is_label_not_code():
    assert is_coarse_label("도시지역")
    assert is_coarse_label("관리지역")
    assert not is_coarse_label("제1종일반주거지역")
    assert not is_coarse_label("농림지역")
    assert not is_coarse_label("자연환경보전지역")
    assert not is_coarse_label("계획관리지역")


def test_zone_family():
    assert zone_family("제2종일반주거지역") == "주거"
    assert zone_family("계획관리지역") == "관리"
    assert zone_family("농림지역") == "농림"
    assert zone_family("자연환경보전지역") == "자연환경"
    assert zone_family("도시지역") is None


def test_zone_code_keeps_abcd_drops_district():
    assert is_zone_code("UQA001")
    assert is_zone_code("UQB002")
    assert not is_zone_code("UQQ001")
    assert not is_zone_code("UDV001")
