"""region_neighbors canonicalize helpers."""

from app.map.neighbors import canonicalize_code_for_level, normalize_neighbor_level


def test_canon_emd_from_beop00():
    assert canonicalize_code_for_level("eupmyeondong", "4311314100") == "43113141"


def test_normalize_level():
    assert normalize_neighbor_level("eupmyeondong") == "eupmyeondong"
    assert normalize_neighbor_level("beopjungri") == "beopjungri"
