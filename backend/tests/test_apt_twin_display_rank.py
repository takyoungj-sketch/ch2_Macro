"""쌍둥이지역 탭 순위. 구조 20곳 다음 가격분포로 자른다. DB 없음."""

from __future__ import annotations

import pandas as pd

from app.collective.regional_regression.apt_twin_lab import (
    PRICE_DIST_COLS,
    STRUCT_COLS,
    rank_display_twins,
)


def _row(**overrides: float) -> dict[str, float]:
    base = {col: 0.0 for col in STRUCT_COLS + PRICE_DIST_COLS}
    base["n_complexes"] = 25
    base.update(overrides)
    return base


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


def test_anchor_is_not_listed():
    frame = pd.DataFrame(
        [_row(age_median=0, price_p50=0), _row(age_median=1, price_p50=1)],
        index=["A", "B"],
    )
    assert rank_display_twins(frame, "A", keep=5) == ["B"]
