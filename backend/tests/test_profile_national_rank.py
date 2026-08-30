"""D-053 전국 순위 RANK 산식."""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "pipeline"))

from build_regional_profile_rank import (  # noqa: E402
    MIX_TYPES,
    competition_ranks_desc,
    name_short,
    pearson,
    ranks_per_capita,
    type_share_corr,
)


def test_competition_rank_ties():
    assert competition_ranks_desc([10, 8, 8, 1]) == [1, 2, 2, 4]


def test_competition_rank_all_equal():
    assert competition_ranks_desc([0, 0, 0]) == [1, 1, 1]


def test_per_capita_excludes_missing_pop():
    amounts = [100.0, 50.0, 999.0]
    pops = [10, None, 5]
    ranks = ranks_per_capita(amounts, pops)
    assert ranks[1] is None
    # 999/5 = 199.8 > 100/10 = 10 → index 2 is rank 1, index 0 is rank 2
    assert ranks[2] == 1
    assert ranks[0] == 2


def test_name_short_sigungu_seoul():
    names = {
        "sigungu": {"11680": {"sido_code": "11", "sigungu_name": "강남구", "eupmyeondong_name": "", "beopjungri_name": "", "sido_name": "서울특별시"}},
        "city": {},
        "eupmyeondong": {},
        "beopjungri": {},
    }
    assert name_short("sigungu", "11680", names) == "서울 강남구"


def test_name_short_eup_dong_not_duplicated():
    names = {
        "sigungu": {
            "11680": {
                "sido_code": "11",
                "sigungu_name": "강남구",
                "eupmyeondong_name": "역삼동",
                "beopjungri_name": "역삼동",
                "sido_name": "서울특별시",
            }
        },
        "eupmyeondong": {
            "11680105": {
                "sido_code": "11",
                "sigungu_name": "역삼동",
                "eupmyeondong_name": "역삼동",
                "beopjungri_name": "역삼동",
                "sido_name": "서울특별시",
            }
        },
        "city": {},
        "beopjungri": {},
    }
    assert name_short("eupmyeondong", "11680105", names) == "서울 강남구 역삼동"


def test_name_short_beop_dong_not_duplicated():
    names = {
        "sigungu": {
            "11680": {
                "sido_code": "11",
                "sigungu_name": "강남구",
                "eupmyeondong_name": "",
                "beopjungri_name": "",
                "sido_name": "서울특별시",
            }
        },
        "beopjungri": {
            "1168010500": {
                "sido_code": "11",
                "sigungu_name": "강남구",
                "eupmyeondong_name": "역삼동",
                "beopjungri_name": "역삼동",
                "sido_name": "서울특별시",
            }
        },
        "city": {},
        "eupmyeondong": {},
    }
    assert name_short("beopjungri", "1168010500", names) == "서울 강남구 역삼동"


def test_pearson_perfect_and_none():
    r = pearson([1, 2, 3, 4], [2, 4, 6, 8])
    assert r is not None and abs(r - 1.0) < 1e-9
    assert pearson([1, 1, 1], [1, 2, 3]) is None
    assert pearson([1, 2], [1, 2]) is None


def test_type_share_corr_compositional_negative():
    items = [
        {"type_amounts": {t: (100.0 if t == "아파트" else 0.0) for t in MIX_TYPES}},
        {"type_amounts": {t: (100.0 if t == "토지" else 0.0) for t in MIX_TYPES}},
        {"type_amounts": {t: (50.0 if t in ("아파트", "토지") else 0.0) for t in MIX_TYPES}},
    ]
    block = type_share_corr(items, "type_amounts")
    assert block["n"] == 3
    i_apt = MIX_TYPES.index("아파트")
    i_land = MIX_TYPES.index("토지")
    r = block["matrix"][i_apt][i_land]
    assert r is not None and r < 0


def test_mix_types_eight():
    assert len(MIX_TYPES) == 8
    assert "아파트" in MIX_TYPES
