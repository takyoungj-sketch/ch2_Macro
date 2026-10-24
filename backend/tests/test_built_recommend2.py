"""모형추천2. 현행 추천의 완전관측 삭제를 쓰지 않는지, 행이 다른 CV로 1위를 가리지 않는지."""

from __future__ import annotations

import numpy as np
import pandas as pd

from app.built.regression.engine import _fit_ols
from app.built.regression.selection.context import SelectionContext
from app.built.schemas import RegressionRunRequest, RegressionVariableSpec
from app.recommendation.recommend2 import (
    RowCandidate,
    recommend2_from_context,
    winning_row_key,
)


def test_larger_row_set_wins_even_when_its_cv_is_higher():
    wide = RowCandidate(row_key=("a",), n=40, cv=20.0, offerable=True)
    narrow = RowCandidate(row_key=("b",), n=10, cv=1.0, offerable=True)
    blocked = RowCandidate(row_key=("c",), n=80, cv=0.1, offerable=False)
    assert winning_row_key([narrow, wide, blocked]) == ("a",)


def test_keep_unknown_matches_run_and_assessed_stays_beside():
    rng = np.random.default_rng(7)
    n = 36
    gross = rng.uniform(80, 300, n)
    age = rng.uniform(2, 35, n)
    price = 2000 + 6 * gross - 4 * age + rng.normal(0, 40, n)
    structure = np.array(["철근콘크리트"] * n, dtype=object)
    structure[0] = None
    assessed = rng.uniform(50, 400, n)
    assessed[:12] = np.nan
    frame = pd.DataFrame(
        {
            "price": price,
            "gross_area": gross,
            "building_age": age,
            "structure_group": structure,
            "assessed_land_price": assessed,
            "contract_year": np.resize(np.array([2022, 2023, 2024, 2025]), n),
        }
    )
    ctx = SelectionContext(
        df=frame,
        scope_label="테스트",
        admin_level="sigungu",
        addr4_city=False,
        mode="sigungu_only",
        unified=False,
    )
    req = RegressionRunRequest(
        asset_type="commercial",
        enrich=True,
        categorical_missing="drop",
        variables=RegressionVariableSpec(
            gross_area=False,
            land_area=False,
            building_age=False,
            road_width_dummy=False,
            zone_type_dummy=False,
            building_use_dummy=False,
            structure_dummy=True,
            assessed_land_price=True,
        ),
    )
    out = recommend2_from_context(
        ctx,
        req,
        blocks=["gross_area", "building_age", "structure"],
    )

    assert out.variables.assessed_land_price is False
    assert "assessed_land_price" not in {c.name for c in out.primary.coefficients}
    assert out.primary.n == n
    assert out.primary.categorical_missing == "keep_unknown"
    replay = _fit_ols(
        frame,
        out.variables,
        "sigungu",
        "테스트",
        response_scale=out.response_scale,
        categorical_missing="keep_unknown",
    )
    assert replay.n == out.primary.n
    assert [c.name for c in replay.coefficients] == [c.name for c in out.primary.coefficients]
    for left, right in zip(replay.coefficients, out.primary.coefficients, strict=True):
        assert left.estimate == right.estimate

    assert out.explanatory_scale in {"log", "loglog"}
    assert out.sides
    assert all(side.n < out.primary.n for side in out.sides)
    assert all(
        "assessed_land_price" in {c.name for c in side.result.coefficients} for side in out.sides
    )
