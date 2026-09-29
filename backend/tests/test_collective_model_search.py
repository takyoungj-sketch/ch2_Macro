"""모형 추천은 사용자가 고른 거래에서 변수 풀과 선형·로그를 탐색한다."""

from __future__ import annotations

import numpy as np
import pandas as pd

from app.collective.regression.engine import recommendation_pool, suggest_collective_regression
from app.collective.schemas import CollectiveRegressionRequest, CollectiveRegressionSpec


def _req(asset: str = "apartment", **flags) -> CollectiveRegressionRequest:
    return CollectiveRegressionRequest(
        asset_type=asset,
        variables=CollectiveRegressionSpec(**flags),
    )


def test_pool_is_not_the_checked_variables():
    req = _req(
        exclusive_area=True,
        building_age=False,
        floor=False,
        dong=False,
        contract_period=False,
    )
    single = recommendation_pool(req, cohort_mode=False)
    assert "building_age" in single
    assert "dong" in single
    assert "households" not in single
    assert "households" in recommendation_pool(req, cohort_mode=True)


def test_officetel_and_presale_pools():
    officetel = recommendation_pool(_req("officetel"), cohort_mode=False)
    assert "dong" not in officetel
    assert "building_age" in officetel
    presale = recommendation_pool(_req("presale"), cohort_mode=False)
    assert "building_age" not in presale
    assert "housing_subtype" in presale


def test_search_includes_unchecked_variables_on_the_same_rows():
    rng = np.random.default_rng(0)
    rows = []
    for i in range(36):
        area = 40 + (i % 12) * 5
        age = float(i % 8)
        price = float(np.exp(8.2 + 0.025 * area - 0.04 * age + float(rng.normal(0, 0.02))))
        rows.append(
            {
                "building_key": "a",
                "price": price,
                "exclusive_area": area,
                "building_age": age,
                "floor": 1 + (i % 12),
                "dong": "101" if i % 2 == 0 else "102",
                "contract_year": 2024,
                "contract_month": 3,
                "unit_price": price / area,
            }
        )
    df = pd.DataFrame(rows)
    found = suggest_collective_regression(
        df,
        _req(
            exclusive_area=True,
            building_age=False,
            floor=False,
            dong=False,
            contract_period=False,
            floor_mode="linear",
        ),
        cohort_mode=False,
    )
    assert found
    assert any("building_age" in item.blocks for item in found)
    assert {item.purpose for item in found} == {"predictive", "explanatory"}
    assert any(item.model_type == "log" for item in found)
    assert all(item.n <= len(df) for item in found)
