"""대표지번 불일치: 시도 접두·도로명 유일·부분일치 최장 유일. DB 없음."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

_PIPELINE = Path(__file__).resolve().parents[2] / "pipeline"
sys.path.insert(0, str(_PIPELINE))

from build_collective_building_attributes import (  # noqa: E402
    attributes_rows,
    build_kapt_indexes,
    match_one,
    name_keys_with_region_aliases,
    norm_name,
    norm_name_core,
    norm_road,
    region_name_prefixes,
)
from parcel_master.apply_name_rematch import classify_name_fills  # noqa: E402
from parcel_master.apply_title_fill import title_fill_blocked  # noqa: E402

MOK = "3014010300"


def _kapt_frame(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    df["name_key"] = df["단지명"].map(norm_name)
    df["name_core"] = df["단지명"].map(norm_name_core)
    if "lot_key" not in df.columns:
        df["lot_key"] = ""
    return df


def _mokdong_kapt() -> pd.DataFrame:
    return _kapt_frame(
        [
            {
                "단지코드": "A10023786",
                "단지명": "대전목동더샵리슈빌",
                "시도": "대전광역시",
                "시군구": "중구",
                "beopjungri_code": MOK,
                "lot_key": "1-95",
                "도로명주소": "대전광역시 중구 선화서로 115",
                "사용승인일": "20220530",
                "세대수": "993",
                "시공사": "포스코건설, 계룡건설",
                "시행사": None,
                "건물구조": "철근콘크리트구조",
                "총주차대수": "1213",
                "분양세대수": "993",
                "임대세대수": "0",
                "동수": "9",
                "최고층수": "35",
                "단지분류": "아파트",
                "분양형태": "분양",
            },
            {
                "단지코드": "A10000001",
                "단지명": "대전목동더샵",
                "시도": "대전광역시",
                "시군구": "중구",
                "beopjungri_code": MOK,
                "lot_key": "360",
                "도로명주소": "대전광역시 중구 목동로22번길 16",
                "사용승인일": "20080101",
                "세대수": "400",
                "시공사": "포스코건설",
                "시행사": None,
                "건물구조": "철근콘크리트구조",
                "총주차대수": "400",
                "분양세대수": "400",
                "임대세대수": "0",
                "동수": "4",
                "최고층수": "20",
                "단지분류": "아파트",
                "분양형태": "분양",
            },
        ]
    )


def test_norm_road_strips_sido():
    assert norm_road("대전광역시 중구 선화서로 115") == "선화서로115"
    assert norm_road("선화서로 115") == "선화서로115"
    assert norm_road("목동로22번길 16") == "목동로22번길16"


def test_daejeon_prefix_alias():
    assert "대전" in region_name_prefixes("대전광역시", "중구")
    keys = name_keys_with_region_aliases(
        "대전목동더샵리슈빌", sido="대전광역시", sigungu="중구"
    )
    assert "목동더샵리슈빌" in keys
    assert "대전목동더샵리슈빌" in keys


def test_mokdong_lishuvil_name_alias_is_a():
    kapt = _mokdong_kapt()
    by_lot, by_name, by_core, names_in_bj, by_road = build_kapt_indexes(kapt)
    row = SimpleNamespace(
        beopjungri_code=MOK,
        display_name="목동더샵리슈빌",
        lot_number="372",
        road_name="선화서로 115",
    )
    tier_key, idxs = match_one(
        row,
        by_lot=by_lot,
        by_name=by_name,
        by_core=by_core,
        names_in_bj=names_in_bj,
        by_road=by_road,
    )
    assert tier_key == "A_name_exact"
    assert idxs == [0]


def test_mokdong_lishuvil_road_when_alias_absent():
    kapt = _mokdong_kapt().drop(columns=["시도", "시군구"])
    by_lot, by_name, by_core, names_in_bj, by_road = build_kapt_indexes(kapt)
    row = SimpleNamespace(
        beopjungri_code=MOK,
        display_name="목동더샵리슈빌",
        lot_number="372",
        road_name="선화서로 115",
    )
    tier_key, idxs = match_one(
        row,
        by_lot=by_lot,
        by_name=by_name,
        by_core=by_core,
        names_in_bj=names_in_bj,
        by_road=by_road,
    )
    assert tier_key == "C_road_exact"
    assert idxs == [0]


def test_unique_road_rejects_unrelated_name():
    kapt = _mokdong_kapt()
    kapt.loc[0, "단지명"] = "다른이름단지"
    kapt["name_key"] = kapt["단지명"].map(norm_name)
    kapt["name_core"] = kapt["단지명"].map(norm_name_core)
    by_lot, by_name, by_core, names_in_bj, by_road = build_kapt_indexes(kapt)
    row = SimpleNamespace(
        beopjungri_code=MOK,
        display_name="목동더샵리슈빌",
        lot_number="372",
        road_name="선화서로 115",
    )
    tier_key, idxs = match_one(
        row,
        by_lot=by_lot,
        by_name=by_name,
        by_core=by_core,
        names_in_bj=names_in_bj,
        by_road=by_road,
    )
    assert tier_key != "C_road_exact"


def test_mokdong_attributes_fill_households():
    kapt = _mokdong_kapt()
    buildings = pd.DataFrame(
        [
            {
                "building_key": "a" * 64,
                "asset_type": "apartment",
                "display_name": "목동더샵리슈빌",
                "beopjungri_code": MOK,
                "lot_number": "372",
                "road_name": "선화서로 115",
                "n_tx": 253,
                "building_year": 2022,
            }
        ]
    )
    out = attributes_rows(buildings, kapt, snapshot_ym="202607", asset_type="apartment")
    row = out.iloc[0]
    assert row["match_tier"] == "A"
    assert int(row["households"]) == 993
    assert row["danji_code"] == "A10023786"
    assert "포스코건설" in str(row["builder_raw"])


def test_name_rematch_opens_empty_f():
    kapt = _mokdong_kapt()
    kapt = kapt.rename(
        columns={
            "단지코드": "danji_code",
            "단지명": "danji_name",
            "시도": "sido_name",
            "시군구": "sigungu_name",
            "도로명주소": "road_address",
            "사용승인일": "approved_date",
            "세대수": "households",
            "시공사": "builder_raw",
            "시행사": "developer_raw",
            "건물구조": "structure_raw",
            "총주차대수": "parking_total",
            "분양세대수": "households_sale",
            "임대세대수": "households_rent",
            "동수": "dong_count",
            "최고층수": "max_floor",
            "단지분류": "danji_class",
            "분양형태": "supply_type",
        }
    )
    cands = pd.DataFrame(
        [
            {
                "building_key": "bk",
                "display_name": "목동더샵리슈빌",
                "beopjungri_code": MOK,
                "lot_number": "372",
                "road_name": "선화서로 115",
                "n_tx": 253,
                "building_year": 2022,
                "match_tier": "F",
                "match_rule": "contains_multi",
                "danji_code": None,
                "has_attr_row": True,
            }
        ]
    )
    classified = classify_name_fills(cands, kapt)
    assert len(classified["fill"]) == 1
    rec = classified["fill"][0]
    assert rec["match_tier"] in {"A", "C"}
    assert rec["danji_code"] == "A10023786"
    assert rec["households"] == 993


def test_bupyeong_short_name_stays_unfilled():
    kapt = _kapt_frame(
        [
            {
                "단지코드": "X1",
                "단지명": "부평주공1단지",
                "beopjungri_code": "2820010100",
                "lot_key": "1",
                "사용승인일": "19900101",
                "세대수": "500",
                "시공사": "대한주택공사",
                "시행사": None,
                "건물구조": "철근콘크리트구조",
                "총주차대수": "200",
                "분양세대수": "500",
                "임대세대수": "0",
                "동수": "5",
                "최고층수": "15",
                "단지분류": "아파트",
                "분양형태": "분양",
            },
            {
                "단지코드": "X2",
                "단지명": "부평푸르지오",
                "beopjungri_code": "2820010100",
                "lot_key": "2",
                "사용승인일": "20050101",
                "세대수": "800",
                "시공사": "대우건설",
                "시행사": None,
                "건물구조": "철근콘크리트구조",
                "총주차대수": "400",
                "분양세대수": "800",
                "임대세대수": "0",
                "동수": "8",
                "최고층수": "20",
                "단지분류": "아파트",
                "분양형태": "분양",
            },
        ]
    )
    buildings = pd.DataFrame(
        [
            {
                "building_key": "f" * 64,
                "asset_type": "apartment",
                "display_name": "부평",
                "beopjungri_code": "2820010100",
                "lot_number": "99",
                "n_tx": 10,
                "building_year": 1990,
            }
        ]
    )
    out = attributes_rows(buildings, kapt, snapshot_ym="202607", asset_type="apartment")
    row = out.iloc[0]
    assert row["match_tier"] == "Z"
    assert not title_fill_blocked("Z", None)
