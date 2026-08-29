"""세종형 K-apt 법정동 키 · 이름 재매칭. DB 없음."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

_PIPELINE = Path(__file__).resolve().parents[2] / "pipeline"
sys.path.insert(0, str(_PIPELINE))

from build_collective_building_attributes import (  # noqa: E402
    build_kapt_indexes,
    lookup_beopjungri_code,
    match_one,
    norm_name,
    norm_name_core,
    region_map_from_rows,
)
from parcel_master.apply_name_rematch import classify_name_fills  # noqa: E402


def _sejong_map():
    rows = [
        SimpleNamespace(
            sido_name="세종특별자치시",
            sigungu_name="종촌동",
            beopjungri_name="",
            beopjungri_code="3611011100",
        ),
        SimpleNamespace(
            sido_name="세종특별자치시",
            sigungu_name="소담동",
            beopjungri_name="",
            beopjungri_code="3611010200",
        ),
        SimpleNamespace(
            sido_name="충청북도",
            sigungu_name="청주시 흥덕구",
            beopjungri_name="가경동",
            beopjungri_code="4311312500",
        ),
    ]
    return region_map_from_rows(rows)


def test_sejong_dong_in_sigungu_looks_up_kapt_dongri():
    m = _sejong_map()
    assert (
        lookup_beopjungri_code(
            m, sido="세종특별자치시", sigungu="", dongri="종촌동"
        )
        == "3611011100"
    )


def test_chungbuk_normal_keys_still_work():
    m = _sejong_map()
    assert (
        lookup_beopjungri_code(
            m, sido="충청북도", sigungu="청주시흥덕구", dongri="가경동"
        )
        == "4311312500"
    )


def test_gajae5_name_matches_despite_lot_mismatch():
    kapt = pd.DataFrame(
        [
            {
                "danji_code": "A33980013",
                "danji_name": "가재마을5단지",
                "beopjungri_code": "3611011100",
                "lot_key": "110",
                "approved_date": "20140811",
                "builder_raw": "현대엔지니어링(주)",
                "developer_raw": None,
                "structure_raw": "철근콘크리트구조",
                "households": 1940,
                "households_sale": 1940,
                "households_rent": 0,
                "dong_count": 29,
                "max_floor": 29,
                "parking_total": 2000,
                "danji_class": "아파트",
                "supply_type": "분양",
            }
        ]
    )
    kapt["name_key"] = kapt["danji_name"].map(norm_name)
    kapt["name_core"] = kapt["danji_name"].map(norm_name_core)
    by_lot, by_name, by_core, names_in_bj, by_road = build_kapt_indexes(kapt)
    row = SimpleNamespace(
        beopjungri_code="3611011100",
        display_name="가재마을5단지",
        lot_number="690",
    )
    tier_key, idx = match_one(
        row,
        by_lot=by_lot,
        by_name=by_name,
        by_core=by_core,
        names_in_bj=names_in_bj,
        by_road=by_road,
    )
    assert tier_key == "A_name_exact"
    assert idx == [0]

    cands = pd.DataFrame(
        [
            {
                "building_key": "bk5",
                "display_name": "가재마을5단지",
                "beopjungri_code": "3611011100",
                "lot_number": "690",
                "n_tx": 428,
                "building_year": 2014,
                "match_tier": "T",
                "match_rule": "title_pnu",
                "danji_code": None,
                "has_attr_row": True,
            }
        ]
    )
    classified = classify_name_fills(cands, kapt)
    assert len(classified["fill"]) == 1
    rec = classified["fill"][0]
    assert rec["match_tier"] == "A"
    assert rec["builder_raw"] == "현대엔지니어링(주)"
    assert rec["danji_code"] == "A33980013"
