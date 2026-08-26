"""표제부 동 합산: 첫째 동 금지 · 부대시설 제외 · 재건축 건너뜀."""

from __future__ import annotations

import sys
from pathlib import Path

_PIPELINE = Path(__file__).resolve().parents[2] / "pipeline"
sys.path.insert(0, str(_PIPELINE))

from parcel_master.title_fill import (  # noqa: E402
    aggregate_title_dongs,
    is_housing_dong,
    is_officetel_dong,
    is_rowhouse_dong,
    title_fill_skip_reason,
)


def test_skip_ancillary_keep_apartment():
    assert is_housing_dong("공동주택", "아파트")
    assert is_housing_dong("공동주택", "공동주택(아파트)")
    assert is_housing_dong("공동주택", "공동주택")
    assert not is_housing_dong("공동주택", "경비실")
    assert not is_housing_dong("공동주택", "지하주차장")
    assert not is_housing_dong("제1종근린생활시설", "점포")
    assert is_housing_dong("공동주택", "아파트-관리사무소")


def test_sum_households_not_first_dong():
    agg = aggregate_title_dongs(
        [
            {"main_purpose": "공동주택", "purpose_detail": "아파트", "households": 30, "floors_above": 10, "approve_date": "20130101", "structure_name": "철근콘크리트구조"},
            {"main_purpose": "공동주택", "purpose_detail": "아파트", "households": 38, "floors_above": 12, "approve_date": "20130101", "structure_name": "철근콘크리트구조"},
            {"main_purpose": "공동주택", "purpose_detail": "경비실", "households": 1, "floors_above": 1, "approve_date": "20130101", "structure_name": "철근콘크리트구조"},
        ]
    )
    assert agg is not None
    assert agg["households"] == 68
    assert agg["dong_count"] == 2
    assert agg["max_floor"] == 12
    assert agg["approved_year"] == 2013


def test_title_tier_usable_in_regional_regression():
    from app.collective.danji_attributes import TIER_META
    from app.collective.regional_regression.engine import USABLE_TIERS, _is_usable_tier

    # 단지정보 탭의 usable 은 매칭 품질. 지역회귀 표본은 값이 있으면 T·P도 넣는다.
    assert TIER_META["T"]["usable"] is False
    assert "T" in USABLE_TIERS
    assert _is_usable_tier("apartment", "T") is True
    assert _is_usable_tier("rowhouse", "T") is True
    assert _is_usable_tier("apartment", "P") is True
    assert _is_usable_tier("apartment", "E") is False


def test_skip_rebuild_and_empty():
    agg = aggregate_title_dongs(
        [
            {
                "main_purpose": "공동주택",
                "purpose_detail": "아파트",
                "households": 40,
                "floors_above": 15,
                "approve_date": "20230101",
                "structure_name": "철근콘크리트구조",
            }
        ]
    )
    assert title_fill_skip_reason(agg=agg, building_year=1985) == "rebuild"
    assert title_fill_skip_reason(agg=agg, building_year=2023) is None
    assert title_fill_skip_reason(agg=None, building_year=2000) == "no_housing"
    empty = aggregate_title_dongs(
        [
            {
                "main_purpose": "공동주택",
                "purpose_detail": "아파트",
                "households": 0,
                "floors_above": 5,
                "approve_date": "20000101",
                "structure_name": "RC",
            }
        ]
    )
    assert title_fill_skip_reason(agg=empty, building_year=2000) == "no_households"


def test_rowhouse_dong_excludes_apartment():
    assert is_rowhouse_dong("공동주택", "다세대주택")
    assert is_rowhouse_dong("공동주택", "연립주택")
    assert is_rowhouse_dong("공동주택", "도시형생활주택(단지형다세대)")
    assert not is_rowhouse_dong("공동주택", "아파트")
    assert not is_rowhouse_dong("공동주택", "공동주택(아파트)")
    assert not is_rowhouse_dong("공동주택", "경비실")
    assert not is_officetel_dong("공동주택", "다세대주택")
    assert is_officetel_dong("업무시설", "업무시설(오피스텔)")
    assert is_officetel_dong("업무시설", "오피스텔")
    assert not is_officetel_dong("업무시설", "업무시설")
    assert not is_housing_dong("업무시설", "오피스텔")


def test_rowhouse_sum_ignores_apartment_dongs():
    rows = [
        {"main_purpose": "공동주택", "purpose_detail": "아파트", "households": 200, "floors_above": 15, "approve_date": "20100101", "structure_name": "철근콘크리트구조"},
        {"main_purpose": "공동주택", "purpose_detail": "다세대주택", "households": 8, "floors_above": 4, "approve_date": "19980101", "structure_name": "벽돌구조"},
        {"main_purpose": "공동주택", "purpose_detail": "다세대주택", "households": 10, "floors_above": 5, "approve_date": "19980101", "structure_name": "벽돌구조"},
        {"main_purpose": "업무시설", "purpose_detail": "오피스텔", "households": 40, "floors_above": 12, "approve_date": "20050101", "structure_name": "철근콘크리트구조"},
    ]
    rh = aggregate_title_dongs(rows, kind="rowhouse")
    assert rh is not None
    assert rh["households"] == 18
    assert rh["dong_count"] == 2
    assert rh["max_floor"] == 5
    ot = aggregate_title_dongs(rows, kind="officetel")
    assert ot is not None
    assert ot["households"] == 40
    assert ot["dong_count"] == 1
    apt = aggregate_title_dongs(rows, kind="apartment")
    assert apt is not None
    assert apt["households"] == 218
    assert apt["dong_count"] == 3


def test_officetel_allows_missing_households():
    agg = aggregate_title_dongs(
        [
            {
                "main_purpose": "업무시설",
                "purpose_detail": "업무시설(오피스텔)",
                "households": 0,
                "floors_above": 18,
                "approve_date": "20150101",
                "structure_name": "철근콘크리트구조",
            }
        ],
        kind="officetel",
    )
    assert agg is not None
    assert agg["households"] is None
    assert agg["dong_count"] == 1
    assert agg["max_floor"] == 18
    assert title_fill_skip_reason(agg=agg, building_year=2015, require_households=True) == "no_households"
    assert title_fill_skip_reason(agg=agg, building_year=2015, require_households=False) is None


def test_classify_blocks_abc_and_refresh_t_fills():
    import pandas as pd
    from parcel_master.apply_title_fill import classify
    from parcel_master.pnu import pnu_from_tx

    pnu = pnu_from_tx("4313012500", "123")
    assert pnu
    title = {
        pnu: [
            {
                "main_purpose": "공동주택",
                "purpose_detail": "아파트",
                "households": 40,
                "floors_above": 10,
                "approve_date": "20130101",
                "structure_name": "철근콘크리트구조",
            }
        ]
    }
    cols = dict(
        beopjungri_code="4313012500",
        lot_number="123",
        display_name="테스트",
        building_year=2013,
        n_tx=10,
        has_attr_row=True,
    )
    blocked = classify(
        pd.DataFrame([{**cols, "building_key": "a", "match_tier": "A"}]),
        title,
        set(),
        kind="apartment",
        skip_kapt=False,
    )
    assert blocked["blocked"][0]["building_key"] == "a"
    assert blocked["fill"] == []

    for tier in ("B", "C"):
        got = classify(
            pd.DataFrame([{**cols, "building_key": tier.lower(), "match_tier": tier}]),
            title,
            set(),
            kind="apartment",
            skip_kapt=False,
        )
        assert got["blocked"][0]["building_key"] == tier.lower()
        assert got["fill"] == []

    keep = classify(
        pd.DataFrame([{**cols, "building_key": "t", "match_tier": "T"}]),
        title,
        set(),
        kind="apartment",
        skip_kapt=False,
        refresh_t=False,
    )
    assert keep["keep_t"][0]["building_key"] == "t"
    assert keep["fill"] == []

    refresh = classify(
        pd.DataFrame([{**cols, "building_key": "t", "match_tier": "T"}]),
        title,
        set(),
        kind="apartment",
        skip_kapt=False,
        refresh_t=True,
    )
    assert refresh["keep_t"] == []
    assert refresh["fill"][0]["building_key"] == "t"

