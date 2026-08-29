"""표제부 단지명 클러스터 → K-apt 별칭. DB 없음."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

_PIPELINE = Path(__file__).resolve().parents[2] / "pipeline"
sys.path.insert(0, str(_PIPELINE))

from parcel_master.apply_pnu_unique import classify_candidates  # noqa: E402
from parcel_master.title_cluster import (  # noqa: E402
    clusters_from_title_rows,
    expand_kapt_pnu_map,
    stems_align,
)

BJ = "4311332025"
P981 = "4311332025109810000"
P265 = "4311332025102650000"
MOK = "3014010300"
P372 = "3014010300103720000"
P195 = "3014010300100010095"


def _kapt(
    *,
    code: str,
    name: str,
    pnu: str,
    bj: str,
    sido: str,
    sigungu: str,
    households: int = 2529,
    builder: str = "GS 건설",
    parking: int = 3289,
    dong_count: int = 18,
) -> SimpleNamespace:
    return SimpleNamespace(
        danji_code=code,
        danji_name=name,
        pnu=pnu,
        beopjungri_code=bj,
        sido_name=sido,
        sigungu_name=sigungu,
        approved_date="20200101",
        builder_raw=builder,
        developer_raw=None,
        structure_raw="철근콘크리트구조",
        households=households,
        households_sale=households,
        households_rent=0,
        dong_count=dong_count,
        max_floor=29,
        parking_total=parking,
        danji_class="아파트",
        supply_type="분양",
    )


def test_stems_align_cheongju_prefix_and_apt_tail():
    assert stems_align(
        "청주리버파크자이",
        "리버파크자이 아파트",
        sido="충청북도",
        sigungu="청주시 흥덕구",
    )
    assert stems_align(
        "목동더샵리슈빌",
        "대전목동더샵리슈빌",
        sido="대전광역시",
        sigungu="중구",
    )


def test_stems_align_rejects_phase_and_unrelated_prefix():
    assert not stems_align("경남아너스빌", "경남아너스빌2", sido="경상남도", sigungu="창원시")
    assert not stems_align("한화꿈에그린", "중계한화꿈에그린", sido="서울특별시", sigungu="노원구")


def test_cluster_is_title_pnus_not_kapt_lot():
    rows = [
        {
            "beopjungri_code": BJ,
            "building_name": "청주리버파크자이",
            "pnu": P981,
            "main_purpose": "공동주택",
            "purpose_detail": "아파트",
        }
    ]
    clusters = clusters_from_title_rows(rows)
    assert clusters[(BJ, "청주리버파크자이")] == {P981}


def test_expand_binds_unique_kapt_onto_title_pnus():
    kapt = _kapt(
        code="A10025357",
        name="리버파크자이 아파트",
        pnu=P265,
        bj=BJ,
        sido="충청북도",
        sigungu="청주시 흥덕구",
    )
    clusters = {(BJ, "청주리버파크자이"): {P981}}
    by_pnu, rules = expand_kapt_pnu_map({P265: kapt}, clusters)
    assert by_pnu[P981] is kapt
    assert rules[P981] == "title_cluster"
    assert rules[P265] == "pnu_unique"


def test_expand_skips_when_two_kapts_share_cluster():
    a = _kapt(code="A1", name="리버파크자이 아파트", pnu=P265, bj=BJ, sido="충청북도", sigungu="청주시 흥덕구")
    b = _kapt(
        code="A2",
        name="청주리버파크자이",
        pnu="4311332025109990000",
        bj=BJ,
        sido="충청북도",
        sigungu="청주시 흥덕구",
    )
    clusters = {(BJ, "청주리버파크자이"): {P981}}
    by_pnu, rules = expand_kapt_pnu_map({a.pnu: a, b.pnu: b}, clusters)
    assert P981 not in by_pnu
    assert "title_cluster" not in rules.values()


def test_mokdong_cluster_aliases_kapt_lot():
    kapt = _kapt(
        code="A10023786",
        name="대전목동더샵리슈빌",
        pnu=P195,
        bj=MOK,
        sido="대전광역시",
        sigungu="중구",
        households=993,
        builder="포스코건설, 계룡건설",
        parking=1213,
        dong_count=9,
    )
    clusters = {(MOK, "목동더샵리슈빌"): {P372}}
    by_pnu, rules = expand_kapt_pnu_map({P195: kapt}, clusters)
    assert rules[P372] == "title_cluster"
    assert by_pnu[P372].danji_code == "A10023786"


def test_classify_upgrades_t_via_title_cluster():
    kapt = _kapt(
        code="A10025357",
        name="리버파크자이 아파트",
        pnu=P265,
        bj=BJ,
        sido="충청북도",
        sigungu="청주시 흥덕구",
    )
    clusters = {(BJ, "청주리버파크자이"): {P981}}
    by_pnu, rules = expand_kapt_pnu_map({P265: kapt}, clusters)
    cands = pd.DataFrame(
        [
            {
                "building_key": "a" * 64,
                "match_tier": "T",
                "danji_code": None,
                "beopjungri_code": BJ,
                "lot_number": "981",
                "display_name": "청주리버파크자이",
                "building_year": 2020,
                "n_tx": 12,
                "has_attr_row": True,
            }
        ]
    )
    out = classify_candidates(cands, by_pnu, rules)
    assert len(out["fill"]) == 1
    rec = out["fill"][0]
    assert rec["match_tier"] == "P"
    assert rec["match_rule"] == "title_cluster"
    assert rec["danji_code"] == "A10025357"
    assert rec["households"] == 2529
    assert rec["builder_raw"] == "GS 건설"
    assert rec["parking_total"] == 3289
    assert rec["dong_count"] == 18


def test_classify_keep_p_does_not_rewrite():
    kapt = _kapt(
        code="A10025357",
        name="리버파크자이 아파트",
        pnu=P265,
        bj=BJ,
        sido="충청북도",
        sigungu="청주시 흥덕구",
    )
    cands = pd.DataFrame(
        [
            {
                "building_key": "b" * 64,
                "match_tier": "P",
                "danji_code": "A10025357",
                "beopjungri_code": BJ,
                "lot_number": "265",
                "display_name": "리버파크자이",
                "building_year": 2020,
                "n_tx": 3,
                "has_attr_row": True,
            }
        ]
    )
    out = classify_candidates(cands, {P265: kapt}, {P265: "pnu_unique"})
    assert out["fill"] == []
    assert len(out["keep_p"]) == 1
