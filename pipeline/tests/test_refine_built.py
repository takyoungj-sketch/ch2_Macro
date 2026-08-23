"""refine_built 단위 테스트."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from built.refine_built import format_display_address, parse_partial_ownership, refine_molit_dataframe, refine_molit_file

REPO = Path(__file__).resolve().parents[2]
COMMERCIAL = (
    REPO
    / "raw"
    / "raw base"
    / "상업업무_2021_2026"
    / "서울특별시_상업업무_매매_2021.csv"
)


def test_commercial_general_filter_and_road_label():
    if not COMMERCIAL.is_file():
        return
    df = refine_molit_file(COMMERCIAL, "commercial")
    assert not df.empty
    assert df["road_code"].isna().all()
    assert df["road_width_label"].notna().any()
    assert (df["price"] > 0).all()
    assert df["contract_date"].notna().all()


def test_display_address_includes_lot_and_road():
    row = pd.Series(
        {
            "addr3": "강남동",
            "addr4": "",
            "addr5": "역삼리",
            "lot_number": "8**",
            "road_name": "테헤란로",
        }
    )
    assert format_display_address(row) == "강남동 역삼리 8** (테헤란로)"


def test_parse_partial_ownership():
    assert parse_partial_ownership("지분") == (True, "지분")
    assert parse_partial_ownership("") == (False, None)
    assert parse_partial_ownership("-") == (False, None)


def test_commercial_share_flag_from_col_16():
    row = [""] * 21
    row[1] = "충청북도 진천군 덕산읍"
    row[2] = "일반"
    row[3] = "5**"
    row[4] = "용몽길"
    row[5] = "일반상업지역"
    row[6] = "제2종근린생활시설"
    row[7] = "8m미만"
    row[8] = "233.4"
    row[9] = "129"
    row[10] = "15000"
    row[14] = "202408"
    row[15] = "5"
    row[16] = "지분"
    row[17] = "2010"
    row[19] = "중개거래"
    df = pd.DataFrame([row])
    out = refine_molit_dataframe(df, "commercial")
    assert len(out) == 1
    assert bool(out.loc[0, "is_partial_ownership"]) is True
    assert out.loc[0, "partial_ownership_label"] == "지분"


def test_detached_never_partial():
    row = [""] * 16
    row[1] = "충청북도 청주시 흥덕구"
    row[2] = "1**"
    row[3] = "단독주택"
    row[4] = "8m미만"
    row[5] = "80.0"
    row[6] = "120"
    row[7] = "202201"
    row[8] = "10"
    row[9] = "20000"
    row[12] = "1990"
    row[13] = "테헤란로"
    row[15] = "중개거래"
    df = pd.DataFrame([row])
    out = refine_molit_dataframe(df, "detached")
    assert len(out) == 1
    assert bool(out.loc[0, "is_partial_ownership"]) is False
    assert out.loc[0, "partial_ownership_label"] in (None, "")

