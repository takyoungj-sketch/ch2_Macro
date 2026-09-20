"""토지 면적 탄성 랩 — 유형·게이트·1차 할당·SQL 계약."""
from __future__ import annotations

import numpy as np

from app.land_lab.area_elasticity import (
    cell_from_agg,
    classify_region_type,
    evaluate_gate,
    select_phase1,
    spectrum_key,
)
from app.land_lab.area_elasticity_fit import fit_cell
from app.land_lab.area_elasticity_screen import build_screen_sql
from app.ledger_region_sql import beopjungri_eq_or_in
from app.region_canonical import region_codes_join_on_canonical


def test_classify_region_type():
    assert classify_region_type("서울특별시", "강남구") == "metro_gu"
    assert classify_region_type("부산광역시", "해운대구") == "metro_gu"
    assert classify_region_type("전남광주통합특별시", "동구") == "metro_gu"
    assert classify_region_type("인천광역시", "강화군") == "gun"
    assert classify_region_type("부산광역시", "기장군") == "gun"
    assert classify_region_type("충청북도", "음성군") == "gun"
    assert classify_region_type("경기도", "화성시") == "cap_city"
    assert classify_region_type("경기도", "수원시 장안구") == "cap_city"
    assert classify_region_type("충청북도", "청주시 흥덕구") == "urban_rural"
    assert classify_region_type("전북특별자치도", "전주시 완산구") == "urban_rural"
    assert classify_region_type("경상남도", "창원시 의창구") == "urban_rural"
    assert classify_region_type("제주특별자치도", "제주시") == "urban_rural"
    assert classify_region_type("세종특별자치시", "세종특별자치시") == "urban_rural"
    assert classify_region_type("전남광주통합특별시", "나주시") == "urban_rural"
    assert classify_region_type("전라남도", "목포시") == "prov_city"
    assert classify_region_type("강원특별자치도", "속초시") == "prov_city"


def test_metro_dae_gate():
    ok, reasons, ratio = evaluate_gate(
        region_type="metro_gu",
        land_category="대",
        n=149,
        area_p50=100,
        area_p90=300,
        n_ge_300=40,
    )
    assert not ok
    assert any("n<" in r for r in reasons)

    ok, _, ratio = evaluate_gate(
        region_type="metro_gu",
        land_category="대",
        n=150,
        area_p50=100,
        area_p90=200,
        n_ge_300=29,
    )
    assert not ok  # 폭 미달
    assert ratio == 2.0

    ok, _, _ = evaluate_gate(
        region_type="metro_gu",
        land_category="대",
        n=150,
        area_p50=100,
        area_p90=300,
        n_ge_300=10,
    )
    assert ok

    ok, _, _ = evaluate_gate(
        region_type="metro_gu",
        land_category="대",
        n=150,
        area_p50=100,
        area_p90=220,
        n_ge_300=30,
    )
    assert ok


def test_national_1000_gate_not_applied_to_seoul_dae():
    ok, reasons, _ = evaluate_gate(
        region_type="metro_gu",
        land_category="대",
        n=200,
        area_p50=80,
        area_p90=200,
        n_ge_300=40,
        n_ge_1000=0,
    )
    assert ok
    assert not any("1000" in r for r in reasons)


def test_gun_dae_gate_no_ratio():
    ok, _, _ = evaluate_gate(
        region_type="gun",
        land_category="대",
        n=80,
        area_p50=200,
        area_p90=250,
        n_ge_500=15,
    )
    assert ok


def test_imya_has_no_gate():
    ok, reasons, _ = evaluate_gate(
        region_type="gun",
        land_category="임야",
        n=500,
        area_p50=1000,
        area_p90=8000,
        n_ge_1000=200,
    )
    assert not ok
    assert reasons == ["optional_imya"]


def test_cell_from_agg_does_not_need_unit_price():
    cell = cell_from_agg(
        {
            "sido_code": "11",
            "sido_name": "서울특별시",
            "sigungu_code": "11680",
            "sigungu_name": "강남구",
            "land_category": "대",
            "n": 200,
            "area_p10": 50,
            "area_p50": 100,
            "area_p75": 180,
            "area_p90": 320,
            "n_ge_300": 40,
            "n_ge_500": 10,
            "n_ge_1000": 0,
            "n_ge_3000": 0,
            "n_ge_5000": 0,
            "n_dongs": 10,
            "dong_n_median": 12,
        }
    )
    assert "unit_price" not in cell.to_dict()
    assert cell.eligible is True
    assert cell.region_type == "metro_gu"
    assert cell.b_preview == "B_ok"


def _cell(**kw):
    base = dict(
        sido_code="41",
        sido_name="경기도",
        sigungu_code="00000",
        sigungu_name="화성시",
        land_category="대",
        n=200,
        area_p10=80,
        area_p50=150,
        area_p75=400,
        area_p90=900,
        n_ge_300=80,
        n_ge_500=40,
        n_ge_1000=20,
        n_ge_3000=2,
        n_ge_5000=0,
        n_dongs=8,
        dong_n_median=10,
    )
    base.update(kw)
    return cell_from_agg(base)


def test_phase1_metro_only_dae_and_unique_gu():
    cells = [
        _cell(
            sido_name="서울특별시",
            sigungu_name="강남구",
            sigungu_code=f"1168{i}",
            n=200 + i,
            area_p90=400 + 10 * i,
        )
        for i in range(8)
    ]
    # 같은 구 전 — 게이트 없음
    cells.append(
        _cell(
            sido_name="서울특별시",
            sigungu_name="강남구",
            sigungu_code="11680",
            land_category="전",
            n=300,
            area_p90=5000,
        )
    )
    picked = select_phase1(cells)
    metro = [c for c in picked if c.region_type == "metro_gu"]
    assert len(metro) == 5
    assert all(c.land_category == "대" for c in metro)
    assert len({c.sigungu_code for c in metro}) == 5


def test_phase1_urban_rural_pairs_same_sigungu():
    cells = []
    for i, name in enumerate(["청주시 흥덕구", "청주시 상당구", "충주시"]):
        cells.append(
            _cell(
                sido_name="충청북도",
                sigungu_name=name,
                sigungu_code=f"4311{i}",
                land_category="대",
                n=200,
                area_p90=800,
            )
        )
        cells.append(
            _cell(
                sido_name="충청북도",
                sigungu_name=name,
                sigungu_code=f"4311{i}",
                land_category="전",
                n=180,
                area_p50=200,
                area_p90=1200,
                n_ge_1000=30,
            )
        )
    picked = select_phase1(cells)
    ur = [c for c in picked if c.region_type == "urban_rural"]
    assert ur
    codes = [c.sigungu_code for c in ur]
    # 같은 시군구에서 대지+전 쌍이 우선
    paired = any(codes.count(c) == 2 for c in set(codes))
    assert paired


def test_spectrum_ignores_would_be_price():
    a = _cell(sigungu_code="1", n=100, area_p50=100, area_p90=400, n_ge_500=30)
    b = _cell(sigungu_code="2", n=100, area_p50=100, area_p90=250, n_ge_500=80)
    assert spectrum_key(a)[0] > spectrum_key(b)[0]


def test_screen_sql_no_any_on_beopjungri():
    join = region_codes_join_on_canonical("lt", "r", active_only=True)
    sql = build_screen_sql(join)
    compact = " ".join(sql.split())
    assert "ANY(" not in compact.upper()
    assert "= ANY" not in compact.upper()
    assert "beopjungri_code = ANY" not in compact


def test_cell_fetch_pattern_uses_eq_or_expanding_in():
    sql, params = beopjungri_eq_or_in(["1111010100"], column="lt.beopjungri_code")
    assert sql == "lt.beopjungri_code = :region_code"
    sql, params = beopjungri_eq_or_in(
        ["1111010100", "1111010200"], column="lt.beopjungri_code"
    )
    assert "IN :region_codes" in sql
    assert "_expand_region_codes" in params


def test_fit_cell_recovers_negative_beta():
    rng = np.random.default_rng(0)
    rows = []
    for i in range(180):
        area = float(np.exp(rng.uniform(3.5, 7.0)))
        year = int(rng.integers(2021, 2026))
        dong = f"d{i % 12}"
        log_p = 2.0 - 0.35 * np.log(area) + 0.02 * (year - 2023) + rng.normal(0, 0.08)
        rows.append(
            {
                "beopjungri_code": dong,
                "road_condition": "8미만" if i % 2 == 0 else "소로",
                "contract_year": year,
                "area_sqm": area,
                "unit_price_per_sqm": float(np.exp(log_p)),
            }
        )
    out = fit_cell(rows)
    assert out["A"]["beta"] is not None
    assert out["A"]["beta"] < 0
    assert out["B"] != "B_skip"
    assert out["B"]["beta"] < 0
    assert out["A_robust"]["beta"] < 0
