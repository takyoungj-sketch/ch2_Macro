"""PNU 유일 승격: 채움 / 재건축 / 묶음. DB·xlsx 없음."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

_PIPELINE = Path(__file__).resolve().parents[2] / "pipeline"
sys.path.insert(0, str(_PIPELINE))

from build_collective_building_attributes import (  # noqa: E402
    ATTR_TIERS,
    attributes_rows,
    norm_name,
    norm_name_core,
)
from parcel_master.pnu_unique import pnu_unique_skip_reason  # noqa: E402


def test_fill_abbreviation_and_year_ok():
    assert (
        pnu_unique_skip_reason(
            tx_name="삼익목화",
            kapt_name="삼익목화1차",
            approved_year=1988,
            building_year=1988,
        )
        is None
    )
    assert (
        pnu_unique_skip_reason(
            tx_name="서우1단지",
            kapt_name="내동서우아파트",
            approved_year=1992,
            building_year=1992,
        )
        is None
    )
    assert (
        pnu_unique_skip_reason(
            tx_name="호암리버빌(2단지)",
            kapt_name="호암리버빌아파트",
            approved_year=2005,
            building_year=2005,
        )
        is None
    )
    assert (
        pnu_unique_skip_reason(
            tx_name="스마트시티2단지",
            kapt_name="스마트시티주상복합아파트",
            approved_year=2011,
            building_year=2011,
        )
        is None
    )


def test_skip_rebuild_year_gap():
    assert (
        pnu_unique_skip_reason(
            tx_name="경성맨션2",
            kapt_name="홍도갤러리휴리움아파트",
            approved_year=2023,
            building_year=1985,
        )
        == "rebuild"
    )
    assert (
        pnu_unique_skip_reason(
            tx_name="계룡맨션",
            kapt_name="글로리아아파트",
            approved_year=2024,
            building_year=1978,
        )
        == "rebuild"
    )


def test_skip_bundle_kapt_name():
    assert (
        pnu_unique_skip_reason(
            tx_name="남산주공3",
            kapt_name="남산주공2.3차 아파트",
            approved_year=1992,
            building_year=1992,
        )
        == "bundle"
    )
    assert (
        pnu_unique_skip_reason(
            tx_name="남광하우스토리A단지",
            kapt_name="사천남광하우스토리 A, B단지",
            approved_year=2008,
            building_year=2008,
        )
        == "bundle"
    )
    assert (
        pnu_unique_skip_reason(
            tx_name="분평계룡리슈빌2단지",
            kapt_name="분평계룡리슈빌1,2단지",
            approved_year=2006,
            building_year=2006,
        )
        == "bundle"
    )
    assert (
        pnu_unique_skip_reason(
            tx_name="대전역대라수어썸브릿지1단지",
            kapt_name="대라수어썸브릿지 1,2단지아파트",
            approved_year=2018,
            building_year=2018,
        )
        == "bundle"
    )


def test_skip_comma_series_in_kapt_name():
    assert (
        pnu_unique_skip_reason(
            tx_name="신반포27",
            kapt_name="신반포 한신 25,26,27차 아파트",
            approved_year=1976,
            building_year=1976,
        )
        == "bundle"
    )
    assert (
        pnu_unique_skip_reason(
            tx_name="푸르지오캐슬(301~302)",
            kapt_name="청주푸르지오.캐슬아파트",
            approved_year=2009,
            building_year=2009,
        )
        == "bundle"
    )
    assert (
        pnu_unique_skip_reason(
            tx_name="문화마을2단지",
            kapt_name="문화마을금호어울림",
            approved_year=2004,
            building_year=2004,
        )
        == "bundle"
    )


def test_p_not_in_regression_usable():
    from app.collective.danji_attributes import TIER_META
    from app.collective.regional_regression.engine import USABLE_TIERS

    assert TIER_META["P"]["usable"] is False
    assert "P" not in USABLE_TIERS
    assert "P" in ATTR_TIERS


def _kapt_frame(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    df["name_key"] = df["단지명"].map(norm_name)
    df["name_core"] = df["단지명"].map(norm_name_core)
    if "lot_key" not in df.columns:
        df["lot_key"] = ""
    return df


def test_attributes_rows_promotes_z_to_p():
    kapt = _kapt_frame(
        [
            {
                "단지코드": "A1",
                "단지명": "삼익목화1차",
                "beopjungri_code": "3017010100",
                "법정동주소": "대전 서구 복수동",
                "pnu": "3017010100102740001",
                "사용승인일": "19880101",
                "세대수": "420",
                "시공사": "삼익주택",
                "시행사": None,
                "건물구조": "철근콘크리트구조",
                "총주차대수": "200",
                "분양세대수": "420",
                "임대세대수": "0",
                "동수": "5",
                "최고층수": "15",
                "단지분류": "아파트",
                "분양형태": "분양",
            },
            {
                "단지코드": "A2",
                "단지명": "삼익목화2차",
                "beopjungri_code": "3017010100",
                "법정동주소": "대전 서구 복수동",
                "pnu": "3017010100103000000",
                "사용승인일": "19900101",
                "세대수": "300",
                "시공사": "삼익주택",
                "시행사": None,
                "건물구조": "철근콘크리트구조",
                "총주차대수": "150",
                "분양세대수": "300",
                "임대세대수": "0",
                "동수": "3",
                "최고층수": "12",
                "단지분류": "아파트",
                "분양형태": "분양",
            },
        ]
    )
    buildings = pd.DataFrame(
        [
            {
                "building_key": "a" * 64,
                "asset_type": "apartment",
                "display_name": "삼익목화",
                "beopjungri_code": "3017010100",
                "lot_number": "274-1",
                "n_tx": 10,
                "building_year": 1988,
            }
        ]
    )
    out = attributes_rows(buildings, kapt, snapshot_ym="202607", asset_type="apartment")
    assert out.iloc[0]["match_tier"] == "P"
    assert out.iloc[0]["match_rule"] == "pnu_unique"
    assert out.iloc[0]["danji_code"] == "A1"
    assert out.iloc[0]["households"] == 420


def test_attributes_rows_keeps_rebuild_as_z():
    kapt = _kapt_frame(
        [
            {
                "단지코드": "B1",
                "단지명": "홍도갤러리휴리움아파트",
                "beopjungri_code": "3011011700",
                "법정동주소": "대전 동구 홍도동",
                "pnu": "3011011700100230003",
                "사용승인일": "20230228",
                "세대수": "200",
                "시공사": "휴림",
                "시행사": None,
                "건물구조": "철근콘크리트구조",
                "총주차대수": "200",
                "분양세대수": "200",
                "임대세대수": "0",
                "동수": "2",
                "최고층수": "20",
                "단지분류": "아파트",
                "분양형태": "분양",
            }
        ]
    )
    buildings = pd.DataFrame(
        [
            {
                "building_key": "b" * 64,
                "asset_type": "apartment",
                "display_name": "경성맨션2",
                "beopjungri_code": "3011011700",
                "lot_number": "23-3",
                "n_tx": 5,
                "building_year": 1985,
            }
        ]
    )
    out = attributes_rows(buildings, kapt, snapshot_ym="202607", asset_type="apartment")
    assert out.iloc[0]["match_tier"] == "Z"
    assert out.iloc[0]["danji_code"] is None
    assert pd.isna(out.iloc[0]["households"]) or out.iloc[0]["households"] is None


def test_attributes_rows_keeps_bundle_as_z():
    kapt = _kapt_frame(
        [
            {
                "단지코드": "C1",
                "단지명": "남산주공2.3차 아파트",
                "beopjungri_code": "4313010500",
                "법정동주소": "충주 교현동",
                "pnu": "4313010500110600000",
                "사용승인일": "19920101",
                "세대수": "720",
                "시공사": "대한주택공사",
                "시행사": None,
                "건물구조": "철근콘크리트구조",
                "총주차대수": "400",
                "분양세대수": "720",
                "임대세대수": "0",
                "동수": "8",
                "최고층수": "15",
                "단지분류": "아파트",
                "분양형태": "분양",
            }
        ]
    )
    buildings = pd.DataFrame(
        [
            {
                "building_key": "c" * 64,
                "asset_type": "apartment",
                "display_name": "남산주공3",
                "beopjungri_code": "4313010500",
                "lot_number": "1060",
                "n_tx": 8,
                "building_year": 1992,
            }
        ]
    )
    out = attributes_rows(buildings, kapt, snapshot_ym="202607", asset_type="apartment")
    assert out.iloc[0]["match_tier"] == "Z"
    assert out.iloc[0]["households"] is None or pd.isna(out.iloc[0]["households"])
