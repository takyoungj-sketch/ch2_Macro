"""도로 지목 2차 — 연도별 비와 칸 안 회귀. DB 없음."""
import math

from app.land_lab.road_jimok_ratio_phase2 import build_yearly, fit_regressions


def _agg(**kw):
    base = {
        "sido_name": "충북",
        "sigungu_name": "청주시",
        "eup_code": "A",
        "eup_name": "가경동",
        "n": 12,
        "p50": 100.0,
        "mean_px": 100.0,
        "contract_year": 2023,
        "zone_type": "1주",
        "land_category": "대",
    }
    base.update(kw)
    return base


def test_yearly_keeps_years_apart_and_marks_partial_edges():
    rows = []
    for year, road_p in ((2021, 30.0), (2023, 60.0)):
        rows.append(_agg(contract_year=year, land_category="도", p50=road_p, mean_px=road_p))
        rows.append(_agg(contract_year=year, land_category="대", p50=100.0, mean_px=100.0))
    yearly = build_yearly(
        rows,
        as_of_month="2026-08",
        period_start="2021-09-01",
        period_end="2026-08-31",
    )
    by = {y["year"]: y for y in yearly}
    assert by[2021]["partial"] is True
    assert by[2023]["partial"] is False
    r2021 = by[2021]["bands"][0]["cuts"]["10"]["r_p50"]
    r2023 = by[2023]["bands"][0]["cuts"]["10"]["r_p50"]
    assert r2021 == 0.3
    assert r2023 == 0.6


def _balanced_trades(*, zone: str, base: str, factor: float, n_cells: int = 6):
    rows = []
    for cell in range(n_cells):
        for year in (2022, 2023):
            for area in (100.0, 400.0):
                for road_c in ("8미만", "25이상"):
                    for is_road in (0, 1):
                        for _k in range(3):
                            log_p = (
                                0.2 * cell
                                + (0.15 if year == 2023 else 0.0)
                                + 0.4 * math.log(area)
                                + (0.08 if road_c == "25이상" else 0.0)
                                + math.log(factor) * is_road
                            )
                            rows.append(
                                {
                                    "eup_code": f"E{cell}",
                                    "zone_type": zone,
                                    "land_category": "도" if is_road else base,
                                    "contract_year": year,
                                    "road_condition": road_c,
                                    "area_sqm": area,
                                    "unit_price_per_sqm": math.exp(log_p),
                                }
                            )
    return rows


def test_within_regression_recovers_road_factor():
    fitted = fit_regressions(_balanced_trades(zone="1주", base="대", factor=0.55))
    urban = next(b for b in fitted["bands"] if b["id"] == "urban_dae")
    cut = urban["cuts"]["10"]
    assert cut["error"] is None
    assert cut["n_cells"] == 6
    assert abs(cut["factor"] - 0.55) < 0.02
    assert abs(cut["log_area"] - 0.4) < 0.02
    assert next(b for b in fitted["bands"] if b["id"] == "nonurban_dae")["cuts"]["10"]["n_cells"] == 0


def test_nonurban_jeon_is_its_own_fit():
    rows = _balanced_trades(zone="계관", base="전", factor=0.8)
    fitted = fit_regressions(rows)
    jeon = next(b for b in fitted["bands"] if b["id"] == "nonurban_jeon")["cuts"]["10"]
    dae = next(b for b in fitted["bands"] if b["id"] == "nonurban_dae")["cuts"]["10"]
    urban = next(b for b in fitted["bands"] if b["id"] == "urban_dae")["cuts"]["10"]
    assert abs(jeon["factor"] - 0.8) < 0.02
    assert dae["n_cells"] == 0
    assert urban["n_cells"] == 0
