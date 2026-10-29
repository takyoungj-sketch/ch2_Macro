"""R1 — recommend stage1 (pool·termination, DB 없음)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from app.built.regression.selection.context import SelectionContext
from app.built.schemas import ModelCandidate, ModelMetrics, RegressionVariableSpec
from app.recommendation.built_pool import (
    DEFAULT_BUILT_CANDIDATE_BLOCKS,
    count_scope_leaves,
    filter_pool_by_coverage,
    fit_is_offerable,
    resolve_recommendation_pool,
)
from app.recommendation.cv_fitness import AxisReading, macro_summary_ko
from app.recommendation.termination import build_termination_v0


def _ctx(df: pd.DataFrame, *, unified: bool = False) -> SelectionContext:
    return SelectionContext(
        df=df,
        scope_label="테스트",
        admin_level="eupmyeondong",
        addr4_city=False,
        mode="two_way",
        unified=unified,
    )


def test_default_pool_excludes_asset_type_when_not_unified():
    df = pd.DataFrame({"addr3": ["A", "B"], "price": [1, 2]})
    pool = resolve_recommendation_pool(_ctx(df), unified=False)
    assert "structure" not in pool
    assert "asset_type" not in pool
    assert "zone_type" in pool
    assert "region_leaf" in pool


def test_structure_enters_pool_only_when_requested():
    df = pd.DataFrame({"addr3": ["A"], "price": [1]})
    pool = resolve_recommendation_pool(_ctx(df), unified=False, include_structure=True)
    assert "structure" in pool


def test_default_pool_includes_asset_type_when_unified():
    df = pd.DataFrame({"addr3": ["A"], "price": [1]})
    pool = resolve_recommendation_pool(_ctx(df, unified=True), unified=True)
    assert "asset_type" in pool


def test_region_leaf_when_two_leaves():
    df = pd.DataFrame({"addr3": ["봉명동", "운천동", "봉명동"], "price": [1, 2, 3]})
    assert count_scope_leaves(_ctx(df)) == 2
    pool = resolve_recommendation_pool(_ctx(df), unified=False)
    assert "region_leaf" in pool


def test_region_leaf_excluded_for_single_leaf():
    df = pd.DataFrame({"addr3": ["봉명동", "봉명동"], "price": [1, 2]})
    pool = resolve_recommendation_pool(_ctx(df), unified=False)
    assert "region_leaf" not in pool


def test_filter_pool_excludes_blocks_without_coverage():
    n = 20
    df = pd.DataFrame(
        {
            "addr3": ["A"] * n,
            "price": list(range(1, n + 1)),
            "gross_area": list(range(1, n + 1)),
            "land_area": list(range(1, n + 1)),
            "building_age": list(range(1, n + 1)),
            "road_width_label": list(range(1, n + 1)),
            "zone_type": [pd.NA] * n,
            "building_use": ["주거"] * n,
        }
    )
    pool, excluded = filter_pool_by_coverage(_ctx(df), list(DEFAULT_BUILT_CANDIDATE_BLOCKS))
    assert "zone_type" not in pool
    assert "gross_area" in pool
    assert any("zone_type" in item for item in excluded)


def test_termination_proceed_twin_when_n_small():
    primary = ModelCandidate(
        rank=1,
        blocks=["land_area"],
        variables=RegressionVariableSpec(land_area=True),
        response_scale="log",
        metrics=ModelMetrics(model_type="log", cv_mape=35.0),
    )
    term = build_termination_v0(
        selection_n=9,
        primary=primary,
        alternate=None,
        truncated=False,
    )
    assert term.action == "proceed_twin"
    assert term.grade == "pending"
    assert any("selection_n=9" in r for r in term.reasons)


def test_fit_below_floor_or_blocked_is_not_offerable():
    class _Inner:
        exog = np.ones((12, 2))

    class _Mid:
        model = _Inner()

    class _Small:
        n = 9
        model = _Mid()

    assert fit_is_offerable(_Small()) is False

    class _BlockedInner:
        exog = np.array([[1.0, 0.0]])

    class _BlockedMid:
        model = _BlockedInner()

    class _Blocked:
        n = 40
        model = _BlockedMid()

    assert fit_is_offerable(_Blocked()) is False


def test_usable_summary_skips_sample_limit_sentence():
    text = macro_summary_ko(
        composite=AxisReading(tier="usable", label_ko="활용 가능"),
        sample=AxisReading(tier="caution", label_ko="표본 주의"),
        fit_n=69,
        scope_n_tx=70,
    )
    assert "제한되어" not in text
    assert "구조적 관계" in text
