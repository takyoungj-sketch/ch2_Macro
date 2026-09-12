"""Fingerprint Twin 거리 — 공통식, 절편 제거."""

from __future__ import annotations

import pandas as pd

from app.built.lab_fingerprint_twin import (
    Fingerprint,
    fit_common_spec,
    fingerprint_distance,
    parent_sigungu,
    rerank_neighbors,
)


def test_parent_sigungu_uses_five_digits():
    assert parent_sigungu("43113113") == "43113"
    assert parent_sigungu("43730") == "43730"


def _fp(sig: str, ln_g: float, ln_l: float, intercept: float = 5.0) -> Fingerprint:
    return Fingerprint(
        sigungu_code=sig,
        n=100,
        beta={
            "ln_gross": ln_g,
            "ln_land": ln_l,
            "r_12m미만": 0.0,
            "r_25m미만": 0.1,
            "r_25m이상": 0.8,
        },
        intercept=intercept,
    )


def test_distance_zero_when_slopes_match_even_if_intercept_differs():
    a = _fp("43113", 0.30, 0.60, intercept=5.0)
    b = _fp("43730", 0.30, 0.60, intercept=8.0)
    d = fingerprint_distance(a, b)
    assert d.distance < 1e-9
    assert d.curve_r > 0.999
    assert d.sign_mismatch == 0


def test_distance_grows_when_land_elasticity_diverges():
    a = _fp("43113", 0.30, 0.60)
    close = fingerprint_distance(a, _fp("43730", 0.32, 0.58))
    far = fingerprint_distance(a, _fp("11110", 0.90, 0.10))
    assert far.distance > close.distance


def test_sign_mismatch_on_area_elasticity():
    a = _fp("43113", 0.30, 0.60)
    b = _fp("11110", 0.30, -0.40)
    d = fingerprint_distance(a, b)
    assert d.sign_mismatch == 1


def test_fit_common_spec_rejects_thin_sample():
    df = pd.DataFrame(
        {
            "price": [10000.0, 12000.0],
            "gross_area": [100.0, 110.0],
            "land_area": [200.0, 210.0],
            "road_width_label": ["8m미만", "12m미만"],
        }
    )
    assert fit_common_spec(df, sigungu_code="43113", n_min=50) is None


def test_rerank_puts_closer_parent_first():
    fps = {
        "43113": _fp("43113", 0.30, 0.60),
        "43730": _fp("43730", 0.31, 0.59),
        "11110": _fp("11110", 1.10, 0.05),
    }
    neighbors = [
        {"region_code": "11110101", "similarity_score": 0.99, "label": "far"},
        {"region_code": "43730250", "similarity_score": 0.40, "label": "near"},
    ]
    ranked = rerank_neighbors(anchor_code="43113113", neighbors=neighbors, fingerprints=fps)
    assert ranked[0].region_code == "43730250"
    assert ranked[0].fingerprint_distance is not None
    assert ranked[1].region_code == "11110101"
