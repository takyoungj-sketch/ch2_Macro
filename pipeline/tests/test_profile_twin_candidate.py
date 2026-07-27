"""Tests for Profile-native Twin candidate filtering."""

from __future__ import annotations

import sys
from pathlib import Path

PIPE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PIPE))

from profile_twin.candidate import effective_scope, twin_candidate_allowed  # noqa: E402
from profile_twin.weight import load_twin_weights  # noqa: E402
from profile_twin.candidate import twin_population_allowed  # noqa: E402


def _meta(*, sido: str, sigungu: str = "43111") -> dict:
    return {"sido_code": sido, "sigungu_code": sigungu}


def test_beop_same_sigungu_only():
    a = _meta(sido="43", sigungu="43111")
    b_ok = _meta(sido="43", sigungu="43111")
    b_no = _meta(sido="43", sigungu="43112")
    assert twin_candidate_allowed(
        region_level="beopjungri", anchor_meta=a, twin_meta=b_ok, scope="same_sigungu"
    )
    assert not twin_candidate_allowed(
        region_level="beopjungri", anchor_meta=a, twin_meta=b_no, scope="same_sigungu"
    )


def test_sigungu_national_scope():
    a = _meta(sido="11", sigungu="11110")
    b = _meta(sido="26", sigungu="26110")
    assert twin_candidate_allowed(
        region_level="sigungu", anchor_meta=a, twin_meta=b, scope="national"
    )


def test_eup_region_scope_chungcheong():
    a = _meta(sido="43", sigungu="43111")
    b_ok = _meta(sido="44", sigungu="44131")
    b_no = _meta(sido="11", sigungu="11110")
    assert twin_candidate_allowed(
        region_level="eupmyeondong", anchor_meta=a, twin_meta=b_ok, scope="region"
    )
    assert not twin_candidate_allowed(
        region_level="eupmyeondong", anchor_meta=a, twin_meta=b_no, scope="region"
    )


def test_effective_scope_by_level():
    assert effective_scope("beopjungri", "region") == "same_sigungu"
    assert effective_scope("sigungu", "region") == "national"
    assert effective_scope("eupmyeondong", None) == "region"


def test_population_gate():
    w = load_twin_weights()
    assert twin_population_allowed(10000, 12000, weights=w)
    assert not twin_population_allowed(10000, 30000, weights=w)
    assert twin_population_allowed(None, 5000, weights=w)
