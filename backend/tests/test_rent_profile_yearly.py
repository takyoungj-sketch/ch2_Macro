from datetime import date

import pytest

from app.rent.profile_yearly import completed_calendar_years, _region_sql


def test_completed_calendar_years_july_2026():
    assert completed_calendar_years(date(2026, 7, 1), 3) == [2023, 2024, 2025]


def test_completed_calendar_years_window_1():
    assert completed_calendar_years(date(2026, 1, 15), 1) == [2025]


def test_region_sql_single_eq():
    sql, params, expand = _region_sql("eupmyeondong", "43113114", conn=None)  # type: ignore[arg-type]
    assert sql == "eupmyeondong_code = :rc"
    assert params == {"rc": "43113114"}
    assert expand is False


def test_region_sql_beop_eq():
    sql, params, expand = _region_sql("beopjungri", "4311311401", conn=None)  # type: ignore[arg-type]
    assert sql == "beopjungri_code = :rc"
    assert "ANY" not in sql
    assert params["rc"] == "4311311401"
    assert expand is False


def test_fetch_sql_avoids_any(monkeypatch):
    from app.rent import profile_yearly as py

    captured: dict = {}

    class _Conn:
        def execute(self, stmt, params):
            captured["sql"] = str(stmt)
            captured["params"] = params

            class _R:
                def mappings(self):
                    return self

                def all(self):
                    return []

            return _R()

    py.fetch_profile_yearly(
        _Conn(),  # type: ignore[arg-type]
        region_level="eupmyeondong",
        region_code="43113114",
        years=[2023, 2024, 2025],
    )
    sql = captured["sql"].upper()
    assert "ANY" not in sql
    assert ">= :Y0" in sql or ">= :y0" in captured["sql"]


def test_region_sql_rejects_blank():
    with pytest.raises(ValueError):
        _region_sql("eupmyeondong", "", conn=None)  # type: ignore[arg-type]
