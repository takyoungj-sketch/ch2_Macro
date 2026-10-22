"""토지 회귀의 개별공시지가는 켠 식에서만 log(원/㎡)로 들어간다."""

from app.land_regression import run_land_regression
from app.schemas import LandRegressionRequest, LandRegressionVariables


def _rows() -> list[dict]:
    out = []
    for i in range(20):
        out.append(
            {
                "unit_price_per_sqm": 80 + i,
                "area_sqm": 150 + i * 3,
                "contract_year": 2020,
                "road_condition": "8미만",
                "deal_type": "중개거래",
                "official_price_won": None if i >= 18 else 400_000 + i * 1_000,
            }
        )
    return out


def _req(*, assessed: bool) -> LandRegressionRequest:
    return LandRegressionRequest(
        zone_type="주거지역",
        land_category="대",
        variables=LandRegressionVariables(
            area_sqm=True,
            log_area=True,
            road_condition=False,
            deal_type=False,
            partial_ownership=False,
            year_trend=False,
            beopjungri_fe=False,
            assessed_land_price=assessed,
        ),
        min_n=10,
    )


def test_assessed_price_is_log_and_drops_missing():
    res = run_land_regression(_rows(), _req(assessed=True))
    names = [c.name for c in res.coefficients]
    assert "log_assessed_land_price" in names
    assert res.n == 18
    assert any("개별공시지가 결측 2건" in w for w in res.warnings)


def test_assessed_price_off_keeps_rows_and_marks_caution():
    res = run_land_regression(_rows(), _req(assessed=False))
    names = [c.name for c in res.coefficients]
    assert "log_assessed_land_price" not in names
    assert res.n == 20
    assert any(w == "분석 제공 기준(30건, 계수당 5건)에 못 미쳐 참고용" for w in res.warnings)


def test_land_standard_when_n_and_rank_both_clear():
    rows = []
    for i in range(40):
        rows.append(
            {
                "unit_price_per_sqm": 80 + i,
                "area_sqm": 150 + i * 3,
                "contract_year": 2020,
                "road_condition": "8미만",
                "deal_type": "중개거래",
                "official_price_won": None,
            }
        )
    res = run_land_regression(rows, _req(assessed=False))
    assert res.n == 40
    assert res.coefficients
    assert not any("참고용" in w for w in res.warnings)
    assert not any("계산 불가" in w for w in res.warnings)
