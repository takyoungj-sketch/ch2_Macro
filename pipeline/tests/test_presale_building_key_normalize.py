# -*- coding: utf-8 -*-
from __future__ import annotations

from collective.building_keys import (
    derive_building_key,
    normalize_building_name_for_key,
    normalize_name,
)


def test_normalize_name_light_keeps_spaces():
    assert normalize_name("청주  가경 IPARK 4단지") == "청주 가경 IPARK 4단지"


def test_presale_key_name_joins_ipark_variants():
    a = normalize_building_name_for_key("청주 가경 IPARK 4단지", asset_type="presale")
    b = normalize_building_name_for_key("청주가경아이파크4단지", asset_type="presale")
    c = normalize_building_name_for_key("청주가경I-Park4단지", asset_type="presale")
    assert a == b == c
    assert a == "청주가경아이파크4단지"
    assert normalize_building_name_for_key("가경 제4단지", asset_type="presale") == "가경4단지"


def test_apartment_key_name_unchanged_rules():
    """아파트는 기존처럼 공백만 정리 — 영문 alias 미적용(키 호환)."""
    a = normalize_building_name_for_key("청주 가경 IPARK 4단지", asset_type="apartment")
    assert a == "청주 가경 IPARK 4단지"


def test_ipark4_presale_keys_merge():
    common = dict(
        asset_type="presale",
        addr1="충청북도",
        addr2="청주시",
        addr3="흥덕구",
        addr4="가경동",
        lot_number="320",
        road_name=None,
    )
    k1 = derive_building_key(building_name="청주 가경 IPARK 4단지", **common)
    k2 = derive_building_key(
        building_name="청주가경아이파크4단지",
        **{**common, "lot_number": "2251"},
    )
    assert k1 == k2

    apt = derive_building_key(
        building_name="청주가경아이파크4단지",
        **{**common, "asset_type": "apartment", "lot_number": "2251"},
    )
    assert apt != k1
