"""D·F 복수 K-apt 합산 — 세대수 합 · 첫 시공사 + 외. DB 없음."""

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
    multi_kapt_row_to_attrs,
    norm_name,
    norm_name_core,
)
from collective.apply_danji_dictionary import _derive  # noqa: E402
from parcel_master.apply_multi_kapt import classify_multi_fills  # noqa: E402

from app.collective.danji_attributes import TIER_META, list_builder_label
from app.collective.regional_regression.engine import USABLE_TIERS, _is_usable_tier


BJ = "4311311800"


def _kapt_frame(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    df["name_key"] = df["단지명"].map(norm_name)
    df["name_core"] = df["단지명"].map(norm_name_core)
    if "lot_key" not in df.columns:
        df["lot_key"] = ""
    return df


def _bunpyeong3_kapt() -> pd.DataFrame:
    return _kapt_frame(
        [
            {
                "단지코드": "A43180302",
                "단지명": "분평주공3-2단지아파트",
                "beopjungri_code": BJ,
                "lot_key": "1200",
                "사용승인일": "19940101",
                "세대수": "850",
                "시공사": "한양공영, 삼익건설",
                "시행사": None,
                "건물구조": "철근콘크리트구조",
                "총주차대수": "500",
                "분양세대수": "850",
                "임대세대수": "0",
                "동수": "8",
                "최고층수": "15",
                "단지분류": "아파트",
                "분양형태": "분양",
            },
            {
                "단지코드": "A43180301",
                "단지명": "분평주공3-1단지아파트",
                "beopjungri_code": BJ,
                "lot_key": "1200",
                "사용승인일": "19930101",
                "세대수": "480",
                "시공사": "한양건설",
                "시행사": None,
                "건물구조": "철근콘크리트구조",
                "총주차대수": "200",
                "분양세대수": "480",
                "임대세대수": "0",
                "동수": "5",
                "최고층수": "12",
                "단지분류": "아파트",
                "분양형태": "분양",
            },
        ]
    )


def test_match_one_lot_multi_returns_all_idxs():
    kapt = _bunpyeong3_kapt()
    by_lot, by_name, by_core, names_in_bj, by_road = build_kapt_indexes(kapt)
    row = SimpleNamespace(beopjungri_code=BJ, display_name="분평주공3", lot_number="1200")
    tier_key, idxs = match_one(
        row,
        by_lot=by_lot,
        by_name=by_name,
        by_core=by_core,
        names_in_bj=names_in_bj,
        by_road=by_road,
    )
    assert tier_key == "D_lot_multi"
    assert sorted(idxs) == [0, 1]


def test_aggregate_does_not_take_first_row_households():
    kapt = _bunpyeong3_kapt()
    attrs = multi_kapt_row_to_attrs(kapt, [0, 1])
    assert attrs["households"] == 1330
    assert attrs["households_sale"] == 1330
    assert attrs["dong_count"] == 13
    assert attrs["max_floor"] == 15
    assert attrs["parking_total"] == 700
    assert attrs["approved_year"] == 1993
    assert attrs["danji_code"] == "A43180301"
    assert attrs["match_danji_codes"] == "A43180301,A43180302"
    assert attrs["builder_raw"] == "한양건설, 한양공영, 삼익건설"


def test_attributes_rows_fills_d_sum():
    kapt = _bunpyeong3_kapt()
    buildings = pd.DataFrame(
        [
            {
                "building_key": "d" * 64,
                "asset_type": "apartment",
                "display_name": "분평주공3",
                "beopjungri_code": BJ,
                "lot_number": "1200",
                "n_tx": 80,
                "building_year": 1993,
            }
        ]
    )
    out = attributes_rows(buildings, kapt, snapshot_ym="202607", asset_type="apartment")
    row = out.iloc[0]
    assert row["match_tier"] == "D"
    assert row["households"] == 1330
    assert row["danji_code"] == "A43180301"
    assert row["match_danji_codes"] == "A43180301,A43180302"
    assert row["builder_raw"] == "한양건설, 한양공영, 삼익건설"


def test_dictionary_df_uses_first_builder_plus_oe():
    df = pd.DataFrame(
        {
            "building_key": ["k"],
            "snapshot_ym": ["202607"],
            "asset_type": ["apartment"],
            "match_tier": ["D"],
            "builder_raw": ["한양건설, 한양공영, 삼익건설"],
            "kapt_name": ["분평주공3-1단지아파트"],
            "households": [1330],
            "dong_count": [13],
            "max_floor": [15],
            "parking_per_household": [0.526],
            "n_tx": [80],
        }
    )
    out = _derive(df, {"k": "분평주공3"})
    assert out.iloc[0]["builder_norm"] == "한양건설 외"
    assert out.iloc[0]["builder_group"] == "한양건설 외"
    assert bool(out.iloc[0]["builder_is_joint"]) is True
    assert list_builder_label(out.iloc[0]["builder_norm"], out.iloc[0]["builder_raw"], True) == "한양건설 외"


def test_dictionary_same_builder_omits_oe():
    df = pd.DataFrame(
        {
            "building_key": ["k2"],
            "snapshot_ym": ["202607"],
            "asset_type": ["apartment"],
            "match_tier": ["D"],
            "builder_raw": ["롯데건설"],
            "kapt_name": ["롯데캐슬"],
            "households": [1870],
            "dong_count": [10],
            "max_floor": [20],
            "parking_per_household": [1.0],
            "n_tx": [20],
        }
    )
    out = _derive(df, {"k2": "롯데캐슬"})
    assert out.iloc[0]["builder_norm"] == "롯데건설"
    assert bool(out.iloc[0]["builder_is_joint"]) is False


def test_df_and_f_are_regression_usable():
    assert TIER_META["D"]["usable"] is True
    assert TIER_META["F"]["usable"] is True
    assert "D" in USABLE_TIERS and "F" in USABLE_TIERS
    assert _is_usable_tier("apartment", "D") is True
    assert _is_usable_tier("apartment", "F") is True
    assert TIER_META["E"]["usable"] is False
    assert TIER_META["P"]["usable"] is False


def test_short_name_f_does_not_fill():
    kapt = _kapt_frame(
        [
            {
                "단지코드": "X1",
                "단지명": "부평주공1단지",
                "beopjungri_code": BJ,
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
                "beopjungri_code": BJ,
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
                "beopjungri_code": BJ,
                "lot_number": "99",
                "n_tx": 10,
                "building_year": 1990,
            }
        ]
    )
    out = attributes_rows(buildings, kapt, snapshot_ym="202607", asset_type="apartment")
    row = out.iloc[0]
    assert row["match_tier"] == "Z"
    assert row["households"] is None or pd.isna(row["households"])
    assert row["danji_code"] is None or pd.isna(row["danji_code"])
    kapt = _bunpyeong3_kapt()
    cands = pd.DataFrame(
        [
            {
                "building_key": "bk",
                "display_name": "분평주공3",
                "beopjungri_code": BJ,
                "lot_number": "1200",
                "n_tx": 80,
                "building_year": 1993,
                "match_tier": "D",
                "match_rule": "lot_multi",
            }
        ]
    )
    classified = classify_multi_fills(cands, kapt)
    assert len(classified["fill"]) == 1
    rec = classified["fill"][0]
    assert rec["households"] == 1330
    assert rec["danji_code"] == "A43180301"
    assert rec["builder_raw"] == "한양건설, 한양공영, 삼익건설"
