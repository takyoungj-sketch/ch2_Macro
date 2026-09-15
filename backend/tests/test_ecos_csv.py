from pathlib import Path

from app.regional_profile.ecos_csv import (
    _delta_pp,
    _yoy_pct,
    load_macro_ecos,
    parse_ecos_wide,
    ym_int,
)

_FIX = Path(__file__).resolve().parent / "fixtures" / "ecos"
_FIX_M = _FIX / "month"


def test_parse_cd_and_ktb():
    parsed = parse_ecos_wide(_FIX / "시장금리_fixture.csv")
    assert parsed["frequency"] == "year"
    cd = parsed["series"]["CD(91일)"]["points"]
    assert cd[0] == {"year": 2010, "v": 2.67}
    assert "국고채(3년)" in parsed["series"]


def test_parse_m2_strips_commas():
    parsed = parse_ecos_wide(_FIX / "M2_fixture.csv")
    m2 = parsed["series"]["M2(평잔,계절조정계열)"]["points"]
    assert m2[0]["v"] == 1000.0
    assert m2[2]["v"] == 1210.0


def test_load_catalog_includes_bok_base():
    out = load_macro_ecos(data_dir=_FIX)
    assert out["default_rate"] == "cd_91"
    assert out["years"] == [2010, 2011, 2012]
    assert out["rates"]["cd_91"]["d_pp"][0]["year"] == 2011
    assert abs(out["rates"]["cd_91"]["d_pp"][0]["v"] - 0.77) < 1e-6
    assert "bok_base" not in out["missing"]
    assert out["rates"]["bok_base"]["values"][0] == {"year": 2010, "v": 2.5}
    assert "ktb_3y" in out["rates"]
    assert out["m2"]["yoy_pct"][0] == {"year": 2011, "v": 10.0}
    assert out["m2"]["yoy_pct"][1]["v"] == 10.0
    assert out["grain"] == "calendar_year"


def test_parse_month_and_provisional_p_column():
    parsed = parse_ecos_wide(_FIX_M / "시장금리_m.csv")
    assert parsed["frequency"] == "month"
    cd = parsed["series"]["CD(91일)"]["points"]
    months = [p["month"] for p in cd]
    assert months[0] == "2010-01"
    assert "2026-06" in months


def test_parse_skips_daily_columns():
    parsed = parse_ecos_wide(_FIX_M / "한국은행 기준금리_m.csv")
    assert parsed["frequency"] == "month"
    pts = parsed["series"]["한국은행 기준금리"]["points"]
    assert [p["month"] for p in pts] == ["2010-01", "2011-01"]


def test_yoy_same_month_last_year():
    pts = [
        {"month": "2010-01", "v": 100.0},
        {"month": "2011-01", "v": 110.0},
        {"month": "2011-02", "v": 50.0},
    ]
    yoy = _yoy_pct(pts)
    assert yoy == [{"month": "2011-01", "v": 10.0}]
    dpp = _delta_pp([{"month": "2010-01", "v": 1.0}, {"month": "2011-01", "v": 1.5}])
    assert dpp == [{"month": "2011-01", "v": 0.5}]
    assert ym_int("2011-01") == 201101


def test_load_month_catalog():
    out = load_macro_ecos(data_dir=_FIX_M, frequency="month")
    assert out["grain"] == "calendar_month"
    assert out["rates"]["cd_91"]["d_pp"][0]["month"] == "2011-01"
    assert abs(out["rates"]["cd_91"]["d_pp"][0]["v"] - 1.0) < 1e-6
    assert "bok_base" not in out["missing"]
    assert out["m2"]["yoy_pct"][0]["month"] == "2011-01"
    assert abs(out["m2"]["yoy_pct"][0]["v"] - 20.0) < 1e-6
