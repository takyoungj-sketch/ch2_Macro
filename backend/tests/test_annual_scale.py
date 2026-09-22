from pathlib import Path

from app.macro_ts.annual_scale import (
    amount_10k_to_eok,
    annual_corr,
    cheonwon_to_eok,
    compute_annual_scale,
    month_rows_to_year_eok,
)
from app.regional_profile.ecos_csv import parse_ecos_calendar_years, parse_ecos_wide
from app.regional_profile.market_size_lab import MIX_TYPES

_FIX = Path(__file__).resolve().parent / "fixtures" / "ecos" / "annual_scale"


def test_units_to_eok():
    assert amount_10k_to_eok(100_000) == 1.0
    assert cheonwon_to_eok(1_000_000) == 1.0


def test_parse_year_not_per_capita_gdp():
    parsed = parse_ecos_calendar_years(_FIX / "주요지표(연간지표)_fix.csv")
    assert "국내총생산(명목, 원화표시)" in parsed["series"]
    gdp = parsed["series"]["국내총생산(명목, 원화표시)"]
    years = [p["year"] for p in gdp["points"]]
    assert years == [2010, 2011, 2024, 2025]
    by_y = {p["year"]: p for p in gdp["points"]}
    assert by_y[2024]["v"] == 2000.0
    assert by_y[2025]["provisional"] is True
    assert by_y[2010]["provisional"] is False


def test_parse_stock_prefers_year_over_month():
    mixed = parse_ecos_wide(_FIX / "주식시장(월,년)_fix.csv")
    assert mixed["frequency"] == "month"
    yearly = parse_ecos_calendar_years(_FIX / "주식시장(월,년)_fix.csv")
    assert yearly["frequency"] == "year"
    kospi = yearly["series"]["KOSPI_거래대금"]["points"]
    assert [p["year"] for p in kospi] == [2010, 2011, 2024, 2025]
    assert kospi[0]["v"] == 500_000_000


def test_incomplete_year_dropped():
    rows = []
    for mix in MIX_TYPES:
        for m in range(1, 13):
            rows.append({"mix_type": mix, "ym": 2010 * 100 + m, "amount_10k": 100_000})
        for m in range(1, 7):
            rows.append({"mix_type": mix, "ym": 2011 * 100 + m, "amount_10k": 100_000})
    notes: list[str] = []
    out = month_rows_to_year_eok(rows, notes)
    assert 2010 in out["합계"]
    assert 2011 not in out["합계"]
    assert out["합계"][2010] == 96.0
    assert "2011" in " ".join(notes)


def test_compute_ratios_and_mix_from_fixtures():
    rows = []
    for mix in MIX_TYPES:
        for m in range(1, 13):
            amt = 200_000 if mix == "아파트" else 100_000
            rows.append({"mix_type": mix, "ym": 2010 * 100 + m, "amount_10k": amt})
            rows.append({"mix_type": mix, "ym": 2024 * 100 + m, "amount_10k": amt * 2})
    payload = compute_annual_scale(month_rows=rows, data_dir=_FIX)
    assert payload["years"] == [2010, 2024]
    assert payload["missing"] == []
    smoke = payload["smoke"]["2010"]
    assert smoke["unit_ok"] is True
    assert abs(smoke["re_eok"] - 108.0) < 1e-6
    assert smoke["gdp_eok"] == 1000.0
    assert abs(smoke["vs_gdp_pct"] - 10.8) < 1e-6
    assert abs(smoke["stock_eok"] - 1000.0) < 1e-6
    apt_share = {p["year"]: p["v"] for p in payload["mix"]["share"]["아파트"]}
    assert abs(apt_share[2010] - 22.2222) < 1e-4
    assert 2025 not in payload["years"]
    vs_gdp = {p["year"]: p["v"] for p in payload["ratios"]["vs_gdp"]}
    assert set(vs_gdp) == {2010, 2024}
    assert payload["corr"]["n_level"] == 2
    assert payload["corr"]["level"]["re_gdp"] is None


def test_annual_corr_perfect_and_yoy_split():
    years = [2010, 2011, 2012, 2013, 2014]
    re = {2010: 100.0, 2011: 120.0, 2012: 90.0, 2013: 135.0, 2014: 108.0}
    gdp = {y: 1000.0 + 50 * i for i, y in enumerate(years)}
    m2 = {y: 2000.0 + 80 * i for i, y in enumerate(years)}
    stock = dict(re)
    out = annual_corr(re, gdp, m2, stock, years)
    assert out["n_level"] == 5
    assert out["n_yoy"] == 4
    assert out["level"]["re_stock"] == 1.0
    assert out["yoy"]["re_stock"] == 1.0
    assert out["level"]["gdp_m2"] == 1.0
    assert abs(out["yoy"]["re_gdp"] or 0) < 0.95

