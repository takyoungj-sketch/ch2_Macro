from pathlib import Path

from app.regional_profile.ecos_csv import load_macro_ecos, parse_ecos_wide

_FIX = Path(__file__).resolve().parent / "fixtures" / "ecos"


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
