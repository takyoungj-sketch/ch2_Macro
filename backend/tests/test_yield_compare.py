"""전국 수익률 비교 — PDF 12월·연말 종가 확인. DB는 돌리지 않는다."""

from pathlib import Path

from app.rent.sangkwon_agg import compound_annual
from app.yield_compare.build import _add_pct, imputed_monthly_per_m2
from app.yield_compare.price_pdf import december_index, december_return_pct

ROOT = Path(__file__).resolve().parents[2]
PDF = ROOT / "data" / "아파트_전국 매매가격지수.pdf"


def test_apartment_december_matches_table():
    idx = december_index(PDF)
    assert idx[2020] == 96.9
    assert idx[2021] == 110.6
    assert idx[2025] == 98.4
    assert 2026 not in idx


def test_december_return_not_average():
    ret = december_return_pct({2020: 96.9, 2021: 110.6}, 2021)
    assert ret is not None
    assert abs(ret - (110.6 / 96.9 - 1) * 100) < 1e-9
    assert december_return_pct({2021: 110.6}, 2021) is None


def test_converted_rent_adds_deposit_at_r_not_bond():
    # 월세 1, 보증금 1200, r=5% → 환산월세 = 1 + 1200*0.05/12 = 6
    assert imputed_monthly_per_m2(1.0, 1200.0, 5.0) == 6.0


def test_residential_investment_is_annual_sum():
    added = _add_pct({2021: 2.5, 2022: None}, {2021: 14.0, 2022: -7.0})
    assert added[2021] == 16.5
    assert added[2022] is None
    assert added[2023] is None


def test_compound_blank_when_quarter_missing():
    assert compound_annual({1: 1.0, 2: 1.0, 3: 1.0}) is None
    full = compound_annual({1: 1.0, 2: 1.0, 3: 1.0, 4: 1.0})
    assert full is not None
    assert abs(full - ((1.01**4 - 1) * 100)) < 1e-9
