"""비주거 집합 회귀는 개별공시지가를 쓰지 않는다.

대표필지 행이 없어 화면 옵션을 두지 않는다. 요청에 켜져 있어도
`run_commercial_regression`이 그 값을 끈다.
"""

import pandas as pd

from app.collective_commercial.regression.engine import run_commercial_regression
from app.collective_commercial.schemas import CommercialRegressionRequest, CommercialRegressionSpec


def _frame() -> pd.DataFrame:
    rows = []
    for i in range(8):
        rows.append(
            {
                "price": 10000 + i * 500,
                "unit_price": 100 + i,
                "gross_area": 80 + i,
                "building_age": 10,
                "building_year": 2010,
                "contract_year": 2024,
                "floor": 1,
                "assessed_land_price": None if i < 2 else 200000 + i * 1000,
            }
        )
    return pd.DataFrame(rows)


def _req(*, assessed: bool) -> CommercialRegressionRequest:
    return CommercialRegressionRequest(
        variables=CommercialRegressionSpec(
            gross_area=True,
            land_area=False,
            building_age=False,
            floor=False,
            zone_type=False,
            building_use=False,
            road_width=False,
            road_code=False,
            addr4=False,
            contract_period=False,
            assessed_land_price=assessed,
        ),
        model_type="linear",
    )


def test_assessed_price_request_is_ignored():
    result = run_commercial_regression(
        _frame(),
        "cluster",
        "테스트",
        _req(assessed=True),
        is_shop=True,
    )
    names = [c.name for c in result.coefficients]
    assert "assessed_land_price" not in names
    assert result.n == 8
    assert not any("개별공시지가" in w for w in result.warnings)


def test_assessed_price_off_keeps_rows():
    result = run_commercial_regression(
        _frame(),
        "cluster",
        "테스트",
        _req(assessed=False),
        is_shop=True,
    )
    names = [c.name for c in result.coefficients]
    assert "assessed_land_price" not in names
    assert result.n == 8
