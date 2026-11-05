"""쌍둥이지역 탭 순위. 구조 20곳 다음 가격분포로 자른다. DB 없음."""

from __future__ import annotations

import pandas as pd

from app.collective.regional_regression.apt_twin_lab import (
    PRICE_DIST_COLS,
    STRUCT_COLS,
    _match_product_anchor,
    _profile_public_row,
    _scope_anchor_rows,
    rank_display_twins,
)
from app.flat_sido_region import FLAT_SIDO_ADDR2_TOKEN


def _row(**overrides: float) -> dict[str, float]:
    base = {col: 0.0 for col in STRUCT_COLS + PRICE_DIST_COLS}
    base["n_complexes"] = 25
    base.update(overrides)
    return base


def test_struct_cols_can_omit_parking():
    frame = pd.DataFrame(
        [
            _row(age_median=0, park_median=0, price_p50=0),
            _row(age_median=1, park_median=50, price_p50=10),
            _row(age_median=2, park_median=40, price_p50=20),
            _row(age_median=3, park_median=30, price_p50=30),
            _row(age_median=4, park_median=20, price_p50=40),
            _row(age_median=5, park_median=10, price_p50=50),
            _row(age_median=6, park_median=0, price_p50=60),
        ],
        index=list("ABCDEFG"),
    )
    no_park = tuple(col for col in STRUCT_COLS if not str(col).startswith("park_"))
    ranked = rank_display_twins(frame, "A", keep=5, struct_cols=no_park)
    assert ranked[0] == "B"
    assert "park_median" not in no_park


def test_price_order_inside_structural_shortlist_and_keep_five():
    frame = pd.DataFrame(
        [
            _row(age_median=0, price_p50=0),
            _row(age_median=1, price_p50=60),
            _row(age_median=2, price_p50=50),
            _row(age_median=3, price_p50=40),
            _row(age_median=4, price_p50=30),
            _row(age_median=5, price_p50=20),
            _row(age_median=6, price_p50=10),
        ],
        index=["A", "B", "C", "D", "E", "F", "G"],
    )
    assert rank_display_twins(frame, "A", keep=5) == ["G", "F", "E", "D", "C"]


def test_flat_sido_public_addr_uses_lookup_token():
    profiles = pd.DataFrame(
        [{
            "addr1": "세종특별자치시",
            "addr2": "",
            "addr4": "조치원읍",
            "label": "",
            "n_complexes": 30,
        }],
        index=["36110101"],
    )
    row = _profile_public_row(profiles, "36110101", rank=None)
    assert row["addr2"] == FLAT_SIDO_ADDR2_TOKEN
    assert row["region_addr"] == f"세종특별자치시|{FLAT_SIDO_ADDR2_TOKEN}|조치원읍"
    assert FLAT_SIDO_ADDR2_TOKEN not in row["label"]
    assert "조치원읍" in row["label"]
    assert _match_product_anchor(
        profiles, addr1="세종특별자치시", addr2=row["addr2"], addr4="조치원읍", region_code="",
    ) == "36110101"
    assert _match_product_anchor(
        profiles, addr1="세종특별자치시", addr2="세종특별자치시", addr4="조치원읍", region_code="",
    ) == "36110101"


def test_named_sigungu_public_addr_stays_literal():
    profiles = pd.DataFrame(
        [{
            "addr1": "서울특별시",
            "addr2": "강남구",
            "addr4": "삼성동",
            "label": "서울특별시 강남구 삼성동",
            "n_complexes": 40,
        }],
        index=["11680101"],
    )
    row = _profile_public_row(profiles, "11680101", rank=1)
    assert row["addr2"] == "강남구"
    assert row["region_addr"] == "서울특별시|강남구|삼성동"


def test_ri_code_uses_parent_eup_for_ranking():
    profiles = pd.DataFrame(
        [{
            "addr1": "충청북도",
            "addr2": "청주시",
            "addr4": "가경동",
            "label": "가경동",
            "n_complexes": 20,
        }],
        index=["43111103"],
    )
    assert _match_product_anchor(
        profiles, addr1="충청북도", addr2="청주시", addr4="가경리", region_code="4311110300",
    ) == "43111103"


def test_scope_anchors_stay_inside_the_selected_gu():
    profiles = pd.DataFrame(
        [
            {
                "label": "충청북도 청주시 강서동",
                "addr1": "충청북도",
                "addr2": "청주시",
                "addr3": "흥덕구",
                "addr4": "강서동",
                "n_complexes": 20,
            },
            {
                "label": "충청북도 청주시 용암동",
                "addr1": "충청북도",
                "addr2": "청주시",
                "addr3": "상당구",
                "addr4": "용암동",
                "n_complexes": 21,
            },
        ],
        index=["43113103", "43111107"],
    )
    inside = _scope_anchor_rows(profiles, "충청북도", "청주시", ["흥덕구"])
    assert [row["addr4"] for row in inside] == ["강서동"]
    whole = _scope_anchor_rows(profiles, "충청북도", "청주시", [])
    assert {row["addr4"] for row in whole} == {"강서동", "용암동"}


def test_anchor_is_not_listed():
    frame = pd.DataFrame(
        [_row(age_median=0, price_p50=0), _row(age_median=1, price_p50=1)],
        index=["A", "B"],
    )
    assert rank_display_twins(frame, "A", keep=5) == ["B"]
