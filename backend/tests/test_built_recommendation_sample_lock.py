"""추천 추정 표본, Twin 필터, 부분 CV 순위."""

from __future__ import annotations

import numpy as np
import pandas as pd

from app.built.regression.engine import (
    _lock_recommendation_sample,
    _with_recommendation_missing_policy,
)
from app.built.regression.selection.best_subset import _rank_candidates
from app.built.regression.selection.fit import BlockFitResult, CvPhase
from app.built.schemas import RegressionRunRequest, RegressionVariableSpec


def _fit(mape: float, phase: CvPhase, blocks: list[str]) -> BlockFitResult:
    return BlockFitResult(
        blocks=blocks,  # type: ignore[arg-type]
        variables=RegressionVariableSpec(),
        response_scale="linear",
        n=40,
        n_params=2,
        aic=1.0,
        bic=1.0,
        adj_r_squared=None,
        mape=10.0,
        model=None,
        x_const=pd.DataFrame(),
        y_price=np.array([]),
        joint_f_tests={},
        cv_mape=mape,
        cv_folds=phase.folds,
        cv_search=phase,
    )


def test_partial_cv_does_not_outrank_a_complete_search():
    partial = _fit(
        5.0,
        CvPhase(
            mape=5.0,
            folds=2,
            years=(2022, 2024),
            held_years=(2022, 2023, 2024),
            failure_reasons=((2023, "학습 표본 부족"),),
        ),
        ["gross_area"],
    )
    complete = _fit(
        20.0,
        CvPhase(mape=20.0, folds=2, years=(2022, 2023), held_years=(2022, 2023)),
        ["land_area"],
    )
    ranked = _rank_candidates(
        [(partial.blocks, partial, None), (complete.blocks, complete, None)],
        "cv_mape",
    )
    assert [list(item.blocks) for item in ranked] == [["land_area"]]


def test_sample_lock_drops_rows_the_selected_model_would_keep():
    frame = pd.DataFrame(
        {
            "price": [100.0, 100.0, 100.0, 100.0],
            "gross_area": [10.0, 10.0, 10.0, 10.0],
            "land_area": [5.0, 5.0, None, None],
        }
    )
    req = RegressionRunRequest(
        asset_type="commercial",
        sample_lock_blocks=["gross_area", "land_area"],
        categorical_missing="drop",
    )
    locked = _lock_recommendation_sample(
        frame,
        req,
        admin_level="sigungu",
        addr4_city=False,
        mode="sigungu_only",
        unified=False,
    )
    assert len(locked) == 2
    kept = _with_recommendation_missing_policy(req)
    assert kept.categorical_missing == "keep_unknown"


def test_twin_fetch_keeps_the_analysis_filters():
    from app.built.regression.candidates.factory import fetch_candidate_rows

    captured: dict = {}

    class Result:
        def mappings(self):
            return self

        def all(self):
            return []

    class Conn:
        def execute(self, sql, params):
            captured["sql"] = str(sql)
            captured["params"] = params
            return Result()

    req = RegressionRunRequest(
        asset_type="commercial",
        road_width_labels=["narrow"],
        zone_types=["상업지역"],
        building_uses=["근린생활"],
        gross_area_min=10,
        building_age_max=30,
        exclude_outliers_iqr=True,
    )
    fetch_candidate_rows(
        Conn(),
        admin_level="eupmyeondong",
        region_codes=("1111010100",),
        asset_type="commercial",
        req=req,
    )
    sql = captured["sql"]
    assert "road_width_label = ANY(:road_width_labels)" in sql
    assert "zone_type = ANY(:zone_types)" in sql
    assert "building_use = ANY(:building_uses)" in sql
    assert "gross_area >= :gross_area_min" in sql
    assert "building_age <= :building_age_max" in sql
    assert captured["params"]["road_width_labels"] == ["narrow"]
