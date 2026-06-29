"""법정리(addr5) 목록 — has_ri 메타와 무관하게 leaf 하위 조회."""

from __future__ import annotations

from app.built.region_structure import sigungu_has_addr5
from app.built.regression.engine import _compare_mode, _filter_ri_picks
from app.built.schemas import RegressionRunRequest, RiPick
import pandas as pd


def test_compare_mode_three_way_when_ri_selected():
    req = RegressionRunRequest(
        addr1="충청북도",
        addr2="청주시",
        addr3_list=["청원구"],
        addr4_list=["내수읍"],
        ri_list=[RiPick(eup="내수읍", ri="내송리")],
        exclude_outliers_iqr=False,
    )
    assert _compare_mode(req, True) == "three_way"


def test_filter_ri_picks_addr4_eup():
    df = pd.DataFrame(
        {
            "price": [100, 200, 300],
            "addr3": ["청원구", "청원구", "청원구"],
            "addr4": ["내수읍", "내수읍", "오창읍"],
            "addr5": ["내송리", "신봉리", "가좌리"],
        }
    )
    out = _filter_ri_picks(df, [RiPick(eup="내수읍", ri="내송리")])
    assert len(out) == 1
    assert out.iloc[0]["addr5"] == "내송리"
