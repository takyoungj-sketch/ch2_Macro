import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "pipeline"))

from macro_ts.csv_month import aggregate_csv, parse_price_value, parse_ym_value
from macro_ts.gate_national_month import evaluate_gate


def test_parse_ym_and_price():
    assert parse_ym_value("201012") == 201012
    assert parse_price_value("16,400") == 16400.0
    assert parse_price_value("0") is None


def test_aggregate_skips_cancel_and_meta(tmp_path: Path):
    lines = ['"□ 면책"'] * 15
    lines.append('"NO","시군구","계약년월","거래금액(만원)","해제사유발생일"')
    lines.append('"1","원주","201001","10,000","-"')
    lines.append('"2","원주","201001","20,000","20100315"')
    lines.append('"3","춘천","201002","5,000",""')
    p = tmp_path / "강원_아파트_매매_2010.csv"
    p.write_text("\n".join(lines), encoding="cp949")
    out = aggregate_csv(p)
    assert out[201001] == [1.0, 10000.0]
    assert out[201002] == [1.0, 5000.0]


def test_gate_rejects_ledger_gap():
    thin = {201801 + i: {"count": 6000.0, "amount": 1.0} for i in range(12)}
    fat = {201901 + i: {"count": 40000.0, "amount": 1.0} for i in range(12)}
    series = {**thin, **fat}
    out = evaluate_gate({"아파트": series})
    assert out["ok"] is False
    assert any("2018" in x for x in out["failures"])


def test_gate_accepts_full_raw_scale():
    apt = {}
    for y in (2018, 2019, 2020, 2021):
        for m in range(1, 13):
            apt[y * 100 + m] = {"count": 40000.0, "amount": 1.0}
    out = evaluate_gate({"아파트": apt})
    assert out["ok"] is True
