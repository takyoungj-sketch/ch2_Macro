"""backend 전환율 스키마·조회."""

from app.rent.conversion_query import rate_case_sql
from app.rent.schemas import RentConversionCompareRow, RentConversionRate


def test_conversion_rate_schema():
    r = RentConversionRate(
        asset_type="apartment",
        r_selected=5.2,
        method_selected="ols_origin",
        gate_passed=True,
        n_buildings=42,
        n_jeonse=900,
        n_mixed=800,
        r_ols_origin=5.2,
    )
    assert r.r_selected == 5.2
    assert r.gate_passed


def test_rate_case_sql_is_searched_case():
    sql = rate_case_sql({"apartment": 4.2547})
    assert sql.startswith("CASE WHEN t.asset_type = 'apartment' THEN ")
    assert "THEN 0.042547" in sql
    assert "WHEN t.asset_type =" in sql
    assert "CASE t.asset_type WHEN t.asset_type" not in sql


def test_converted_lookup_uses_resolved_building_key():
    import inspect

    from app.rent.conversion_query import fetch_building_converted

    src = inspect.getsource(fetch_building_converted)
    assert "building_key_sql" in src
    assert "NULLIF(btrim(t.building_key::text), '') = :bk" not in src


def test_compare_row_schema():
    row = RentConversionCompareRow(
        addr1="서울특별시",
        addr2="강남구",
        asset_type="apartment",
        window_years=5,
        n_buildings=10,
        r_ols_origin=4.9,
        gate_passed=True,
    )
    assert row.window_years == 5
    assert row.r_ols_origin == 4.9
