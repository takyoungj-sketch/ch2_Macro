"""refine_built 단위 테스트."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from built.refine_built import format_display_address, refine_molit_file

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
