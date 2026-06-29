"""MOLIT raw base 집합상가·집합공장 refine 단위 테스트."""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "pipeline" / "collective_commercial"))
sys.path.insert(0, str(REPO / "pipeline"))

from molit_raw import refine_collective_molit_file  # noqa: E402

COMMERCIAL = (
    REPO
    / "raw"
    / "raw base"
    / "상업업무_2021_2026"
    / "서울특별시_상업업무_매매_2021.csv"
)


def test_collective_shop_filter_and_contract_date():
    if not COMMERCIAL.is_file():
        return
    df = refine_collective_molit_file(COMMERCIAL, asset_type="collective_shop")
    assert not df.empty
    assert (df["asset_type"] == "collective_shop").all()
    assert df["road_name"].notna().all()
    assert df["contract_date"].notna().all()
    assert df["contract_year"].notna().all()
    assert df["contract_month"].notna().all()
    assert (df["unit_price"] > 0).all()
