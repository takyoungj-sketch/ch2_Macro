"""Pareto archetype picks — 설명형 · 균형형 · 예측형."""

from __future__ import annotations

import pandas as pd

from app.built.regression.selection.archetypes import ARCHETYPE_LABELS, pick_archetypes
from app.built.regression.selection.blocks import BlockId
from app.built.regression.selection.fit import BlockFitResult, fit_best_scale


def _make_df(n: int = 40) -> pd.DataFrame:
    rows = []
    for i in range(n):
        gross = 50 + i * 2
        land = 30 + i
        age = 5 + (i % 6)
        zone = ["Z1", "Z2", "Z3"][i % 3]
        price = 3000 + gross * 8 + land * 4 - age * 20 + (500 if zone == "Z2" else 0)
        rows.append(
            {
                "price": price,
                "gross_area": gross,
                "land_area": land,
                "building_age": age,
                "road_width_label": "8m" if i % 2 == 0 else "12m",
                "zone_type": zone,
                "building_use": "근린",
                "asset_type": "commercial",
            }
        )
    return pd.DataFrame(rows)


def _score_all(df: pd.DataFrame, block_lists: list[list[BlockId]]):
    scored = []
    for blocks in block_lists:
        fit, cmp = fit_best_scale(
            df, blocks, unified=False, region_col=None, admin_level="sigungu"
        )
        if fit is not None:
            scored.append((blocks, fit, cmp))
    return scored


def test_pick_archetypes_returns_three_kinds():
    df = _make_df()
    blocks = [
        ["gross_area"],
        ["gross_area", "land_area"],
        ["gross_area", "building_age"],
        ["gross_area", "land_area", "building_age"],
        ["gross_area", "land_area", "building_age", "road_width"],
        ["gross_area", "land_area", "building_age", "zone_type"],
    ]
    scored = _score_all(df, blocks)
    baseline, _ = fit_best_scale(
        df,
        ["gross_area", "land_area", "building_age", "road_width", "zone_type"],
        unified=False,
        region_col=None,
        admin_level="sigungu",
    )
    picks = pick_archetypes(scored, baseline)
    assert len(picks) >= 2
    kinds = {p.kind for p in picks}
    assert "explanation" in kinds or "prediction" in kinds
    for p in picks:
        assert p.kind in ARCHETYPE_LABELS
        assert p.confidence_label in ("높음", "보통", "낮음")
        assert p.reasons


def test_archetype_explanation_has_highest_adj():
    df = _make_df()
    blocks = [
        ["gross_area"],
        ["gross_area", "zone_type"],
        ["gross_area", "land_area", "zone_type"],
    ]
    scored = _score_all(df, blocks)
    picks = pick_archetypes(scored, None)
    expl = next(p for p in picks if p.kind == "explanation")
    pool_adj = [f.adj_r_squared for _, f, _ in scored if f.adj_r_squared is not None]
    assert expl.fit.adj_r_squared == max(pool_adj)
