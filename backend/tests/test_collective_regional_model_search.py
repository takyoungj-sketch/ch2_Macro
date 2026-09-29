"""지역회귀 모형 추천은 고른 단지에서 변수 풀과 선형·로그를 탐색한다."""

from __future__ import annotations

import numpy as np
import pandas as pd

from app.collective.regional_regression.engine import suggest_regional_regression
from app.collective.regional_regression.schemas import (
    RegionalRegressionRunRequest,
    RegionalRegressionVariables,
)


def test_search_includes_unchecked_variables_on_the_same_complexes():
    rng = np.random.default_rng(1)
    rows = []
    for i in range(24):
        households = 80 + i * 12
        age = float(i % 10)
        builder_bump = 180.0 if i % 3 == 0 else 0.0
        price = 500 + 0.35 * households - 6 * age + builder_bump + float(rng.normal(0, 4))
        rows.append(
            {
                "median": price,
                "match_tier": "A",
                "households": households,
                "max_floor": 8 + (i % 6),
                "building_age": age,
                "parking_per_household": 0.7 + (i % 4) * 0.1,
                "assessed_land_price": 150 + i * 3,
                "structure_group": "철근콘크리트" if i % 2 == 0 else "기타",
                "builder_group": "가나다" if i % 3 == 0 else "기타",
                "n_tx": 8,
                "asset_type": "apartment",
            }
        )
    df = pd.DataFrame(rows)
    req = RegionalRegressionRunRequest(
        addr1="충청북도",
        addr2="청주시",
        asset_type="apartment",
        variables=RegionalRegressionVariables(
            households=True,
            max_floor=False,
            building_age=False,
            parking=False,
            structure=False,
            builder=False,
            asset_type_dummy=False,
            assessed_land_price=False,
        ),
        model_type="linear",
        min_tx=5,
        region_dummy=False,
    )
    found = suggest_regional_regression(df, req, unified=False)
    assert found
    assert any("building_age" in item.blocks for item in found)
    assert {item.purpose for item in found} == {"predictive", "explanatory"}
    assert all("asset_type_dummy" not in item.blocks for item in found)
    assert all(item.n <= len(df) for item in found)
    assert all(item.hold_mape is None for item in found)
