"""region_neighbors canonicalize helpers."""

from app.map.neighbors import (
    canonicalize_code_for_level,
    normalize_neighbor_level,
    selection_graph_usable,
)


def test_canon_emd_from_beop00():
    assert canonicalize_code_for_level("eupmyeondong", "4311314100") == "43113141"


def test_normalize_level():
    assert normalize_neighbor_level("eupmyeondong") == "eupmyeondong"
    assert normalize_neighbor_level("beopjungri") == "beopjungri"


def test_selection_graph_usable_requires_same_sigungu_neighbor():
    # 세종 연동면: 충북 링만 있으면 불완전 → turf 폴백
    assert not selection_graph_usable({"36110320": ["43113250", "43113310"]})
    assert not selection_graph_usable({"36110360": []})
    assert not selection_graph_usable({})
    # 강동 천호동: 광진 구의동만 있으면 같은 시도라도 불완전
    assert not selection_graph_usable({"11740109": ["11215104"]})
    assert selection_graph_usable({"36110320": ["36110360", "43113250"]})
    assert selection_graph_usable({"43113141": ["43113142"]})
    assert selection_graph_usable({"11740109": ["11740105", "11215104"]})
