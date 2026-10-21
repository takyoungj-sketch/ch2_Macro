"""임대 회귀는 개별공시지가를 붙이지 않는다."""

import pandas as pd

from app.collective.regression.engine import run_cohort_regression
from app.collective.schemas import CollectiveRegressionRequest, CollectiveRegressionSpec
from app.rent.land_price import prepare_rent_regression


def _body(*, assessed: bool) -> CollectiveRegressionRequest:
    return CollectiveRegressionRequest(
        asset_type="apartment",
        model_type="linear",
        variables=CollectiveRegressionSpec(
            exclusive_area=True,
            floor=False,
            building_age=False,
            dong=False,
            contract_period=False,
            assessed_land_price=assessed,
        ),
    )


def _frame() -> pd.DataFrame:
    rows = []
    for key, land, bump in (("a" * 64, 100_000.0, 0), ("b" * 64, 300_000.0, 400)):
        for i in range(8):
            area = 20 + i
            rows.append(
                {
                    "building_key": key,
                    "display_name": key[:4],
                    "exclusive_area": float(area),
                    "floor": float(1 + (i % 4)),
                    "building_age": 10,
                    "price": 1000 + area * 20 + bump,
                    "unit_price": 50,
                    "housing_subtype": None,
                }
            )
    return pd.DataFrame(rows)


def test_request_does_not_attach_price():
    prices = {("a" * 64): (100_000.0, 2026), ("b" * 64): (300_000.0, 2026)}
    for asset in ("detached", "apartment", "rowhouse"):
        df, body, notes = prepare_rent_regression(
            _frame(), _body(assessed=True), asset, prices=prices
        )
        assert "assessed_land_price" not in df.columns
        assert body.variables.assessed_land_price is False
        assert notes == []


def test_flag_off_keeps_area_coefficient():
    bare = _frame()
    off = run_cohort_regression(bare, ["a" * 64, "b" * 64], "2동", _body(assessed=False))
    attached, body, _notes = prepare_rent_regression(
        bare, _body(assessed=True), "rowhouse", prices={}
    )
    again = run_cohort_regression(attached, ["a" * 64, "b" * 64], "2동", body)
    assert off.n == 16
    assert "assessed_land_price" not in {c.name for c in again.coefficients}
    off_area = next(c.coef for c in off.coefficients if c.name == "exclusive_area")
    again_area = next(c.coef for c in again.coefficients if c.name == "exclusive_area")
    assert again_area == off_area
