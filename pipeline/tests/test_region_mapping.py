"""region_mapping 단위 테스트 — D-015 정규화."""

from __future__ import annotations

import pandas as pd

from region_mapping import normalize_addr_fields


def test_gu_city_keeps_addr4_as_dong():
    gu_row = pd.DataFrame(
        [
            {
                "addr1": "경기도",
                "addr2": "수원시",
                "addr3": "영통구",
                "addr4": "망포동",
                "addr5": "",
            }
        ]
    )
    out = normalize_addr_fields(gu_row)
    assert out.loc[0, "addr4"] == "망포동"
    assert out.loc[0, "addr5"] == ""


def test_d015_ri_promotion_from_addr4_to_addr5():
    flat = pd.DataFrame(
        [
            {
                "addr1": "충청북도",
                "addr2": "제천시",
                "addr3": "신백읍",
                "addr4": "화산리",
                "addr5": "",
            }
        ]
    )
    out = normalize_addr_fields(flat)
    assert out.loc[0, "addr4"] == ""
    assert out.loc[0, "addr5"] == "화산리"


def test_addr5_unchanged_when_already_set():
    with_ri = pd.DataFrame(
        [
            {
                "addr1": "충청북도",
                "addr2": "제천시",
                "addr3": "신백읍",
                "addr4": "",
                "addr5": "화산리",
            }
        ]
    )
    out = normalize_addr_fields(with_ri)
    assert out.loc[0, "addr5"] == "화산리"
