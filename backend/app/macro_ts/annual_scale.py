"""연 부동산 거래액 vs GDP·M2·주식 거래대금 + 유형 구성.

G3(월 YoY r)와 다른 질문. 시군구 r 없음. 인과 아님.
재실행 (backend에서):
  python -m app.macro_ts.annual_scale
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any, Iterable

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.regional_profile.ecos_csv import parse_ecos_calendar_years
from app.regional_profile.market_size_lab import MIX_TYPES

ROOT = Path(__file__).resolve().parents[3]
ANNUAL_DIR = ROOT / "data" / "한은 연간"
OUT = ROOT / "docs" / "lab" / "macro_annual_scale_screen.json"

YEAR_LO = 2010
YEAR_HI = 2024
GDP_MATCH = "국내총생산(명목, 원화표시)"
M2_MATCH = "M2(평잔,계절조정계열)"
KOSPI_TURN = "KOSPI_거래대금"
KOSDAQ_TURN = "KOSDAQ_거래대금"

# national_month.amount_10k = 만원. 1십억원 = 100,000만원.
AMOUNT_10K_PER_EOK = 100_000.0
# 주식 거래대금 단위 = 천원. 1십억원 = 1,000,000천원.
CHEONWON_PER_EOK = 1_000_000.0


def amount_10k_to_eok(v: float) -> float:
    return float(v) / AMOUNT_10K_PER_EOK


def cheonwon_to_eok(v: float) -> float:
    return float(v) / CHEONWON_PER_EOK


def _latest(folder: Path, pattern: str) -> Path:
    hits = list(folder.glob(pattern))
    if not hits:
        raise FileNotFoundError(f"{folder} / {pattern} 없음")
    hits.sort(key=lambda p: p.stat().st_mtime)
    return hits[-1]


def _year_map(block: dict[str, Any] | None, *, drop_provisional: bool) -> dict[int, float]:
    out: dict[int, float] = {}
    if not block:
        return out
    for p in block.get("points") or []:
        y = int(p["year"])
        if drop_provisional and p.get("provisional"):
            continue
        out[y] = float(p["v"])
    return out


def load_denominators(data_dir: Path | None = None) -> dict[str, Any]:
    folder = data_dir or ANNUAL_DIR
    gdp_path = _latest(folder, "주요지표*.csv")
    m2_path = _latest(folder, "M2*.csv")
    stock_path = _latest(folder, "주식시장*.csv")
    gdp_parsed = parse_ecos_calendar_years(gdp_path)
    m2_parsed = parse_ecos_calendar_years(m2_path)
    stock_parsed = parse_ecos_calendar_years(stock_path)

    def pick(parsed: dict[str, Any], match: str) -> dict[str, Any] | None:
        series = parsed["series"]
        if match in series:
            return series[match]
        key = match.replace(" ", "")
        for name, block in series.items():
            if name.replace(" ", "") == key:
                return block
        return None

    gdp_block = pick(gdp_parsed, GDP_MATCH)
    m2_block = pick(m2_parsed, M2_MATCH)
    kospi = pick(stock_parsed, KOSPI_TURN)
    kosdaq = pick(stock_parsed, KOSDAQ_TURN)
    missing: list[str] = []
    if gdp_block is None:
        missing.append("gdp")
    if m2_block is None:
        missing.append("m2")
    if kospi is None:
        missing.append("kospi_turnover")
    if kosdaq is None:
        missing.append("kosdaq_turnover")

    gdp = _year_map(gdp_block, drop_provisional=True)
    m2 = _year_map(m2_block, drop_provisional=True)
    stock: dict[int, float] = {}
    kmap = _year_map(kospi, drop_provisional=False)
    dmap = _year_map(kosdaq, drop_provisional=False)
    for y in set(kmap) | set(dmap):
        if y not in kmap or y not in dmap:
            continue
        stock[y] = cheonwon_to_eok(kmap[y] + dmap[y])

    notes: list[str] = []
    if gdp_block and gdp_block.get("unit") and "십억" not in str(gdp_block["unit"]):
        notes.append(f"GDP 단위 확인: {gdp_block['unit']}")
    if m2_block and m2_block.get("unit") and "십억" not in str(m2_block["unit"]):
        notes.append(f"M2 단위 확인: {m2_block['unit']}")
    if kospi and kospi.get("unit") and "천원" not in str(kospi["unit"]).replace(" ", ""):
        notes.append(f"주식 거래대금 단위 확인: {kospi['unit']}")

    return {
        "gdp_eok": gdp,
        "m2_eok": m2,
        "stock_eok": stock,
        "missing": missing,
        "notes": notes,
        "sources": {
            "gdp": gdp_parsed["file"],
            "m2": m2_parsed["file"],
            "stock": stock_parsed["file"],
            "dir": str(folder.name),
            "gdp_unit": (gdp_block or {}).get("unit"),
            "m2_unit": (m2_block or {}).get("unit"),
            "stock_unit": (kospi or {}).get("unit"),
        },
    }


def _add_month(dst: dict[str, dict[int, dict[str, float]]], mix: str, ym: int, amount_10k: float) -> None:
    by_ym = dst.setdefault(mix, {})
    cell = by_ym.setdefault(int(ym), {"amount_10k": 0.0})
    cell["amount_10k"] += float(amount_10k)


def month_rows_to_year_eok(
    rows: Iterable[dict[str, Any]],
    notes: list[str],
    *,
    year_lo: int = YEAR_LO,
    year_hi: int = YEAR_HI,
) -> dict[str, dict[int, float]]:
    """mix_type × 달력연 거래액(십억원). 12개월 미만 해·year_hi 초과는 제외."""
    by_mix: dict[str, dict[int, dict[str, float]]] = {name: {} for name in MIX_TYPES}
    for r in rows:
        name = str(r.get("mix_type") or "")
        if name not in by_mix:
            continue
        _add_month(by_mix, name, int(r["ym"]), float(r.get("amount_10k") or 0))

    incomplete: set[int] = set()
    year_eok: dict[str, dict[int, float]] = {name: {} for name in MIX_TYPES}
    for name, by_ym in by_mix.items():
        months: dict[int, int] = {}
        acc: dict[int, float] = {}
        for ym, cell in by_ym.items():
            y = int(ym) // 100
            acc[y] = acc.get(y, 0.0) + cell["amount_10k"]
            months[y] = months.get(y, 0) + 1
        for y, amt in acc.items():
            if months.get(y, 0) < 12:
                incomplete.add(y)
                continue
            if y < year_lo or y > year_hi:
                if y > year_hi:
                    incomplete.add(y)
                continue
            year_eok[name][y] = amount_10k_to_eok(amt)

    total: dict[int, float] = {}
    for part in year_eok.values():
        for y, v in part.items():
            total[y] = total.get(y, 0.0) + v
    year_eok["합계"] = total
    extra = sorted(y for y in incomplete if y > year_hi or True)
    if extra:
        notes.append("미완결·창밖 연 제외 " + ", ".join(str(y) for y in sorted(incomplete)))
    return year_eok


def _pts(mp: dict[int, float], years: list[int]) -> list[dict[str, Any]]:
    return [{"year": y, "v": round(mp[y], 6)} for y in years if y in mp]


def _ratio_pct(num: dict[int, float], den: dict[int, float], years: list[int]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for y in years:
        a = num.get(y)
        b = den.get(y)
        if a is None or b is None or b == 0:
            continue
        out.append({"year": y, "v": round(100.0 * a / b, 4)})
    return out


def _share_pct(part: dict[int, float], total: dict[int, float], years: list[int]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for y in years:
        a = part.get(y)
        b = total.get(y)
        if a is None or b is None or b == 0:
            continue
        out.append({"year": y, "v": round(100.0 * a / b, 4)})
    return out


def _pearson(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 3 or len(xs) != len(ys):
        return None
    if len(set(xs)) < 2 or len(set(ys)) < 2:
        return None
    from statistics import StatisticsError, correlation

    try:
        return round(float(correlation(xs, ys)), 4)
    except StatisticsError:
        return None


def _aligned(a: dict[int, float], b: dict[int, float], years: list[int]) -> tuple[list[float], list[float]]:
    xs: list[float] = []
    ys: list[float] = []
    for y in years:
        if y in a and y in b:
            xs.append(a[y])
            ys.append(b[y])
    return xs, ys


def _yoy_map(mp: dict[int, float], years: list[int]) -> dict[int, float]:
    out: dict[int, float] = {}
    for i, y in enumerate(years):
        if i == 0:
            continue
        prev = years[i - 1]
        a = mp.get(prev)
        b = mp.get(y)
        if a is None or b is None or a == 0:
            continue
        out[y] = 100.0 * (b - a) / abs(a)
    return out


def _pair_r(a: dict[int, float], b: dict[int, float], years: list[int]) -> float | None:
    xs, ys = _aligned(a, b, years)
    return _pearson(xs, ys)


def annual_corr(
    re: dict[int, float],
    gdp: dict[int, float],
    m2: dict[int, float],
    stock: dict[int, float],
    years: list[int],
) -> dict[str, Any]:
    """같은 해 피어슨 r. 수준은 추세가 섞임. 전년대비가 동조 확인용. 인과 아님."""
    yoy_re = _yoy_map(re, years)
    yoy_gdp = _yoy_map(gdp, years)
    yoy_m2 = _yoy_map(m2, years)
    yoy_stock = _yoy_map(stock, years)
    yoy_years = [y for y in years[1:] if y in yoy_re]
    return {
        "n_level": len(years),
        "n_yoy": len(yoy_years),
        "level": {
            "re_gdp": _pair_r(re, gdp, years),
            "re_m2": _pair_r(re, m2, years),
            "re_stock": _pair_r(re, stock, years),
            "gdp_m2": _pair_r(gdp, m2, years),
            "gdp_stock": _pair_r(gdp, stock, years),
            "m2_stock": _pair_r(m2, stock, years),
        },
        "yoy": {
            "re_gdp": _pair_r(yoy_re, yoy_gdp, yoy_years),
            "re_m2": _pair_r(yoy_re, yoy_m2, yoy_years),
            "re_stock": _pair_r(yoy_re, yoy_stock, yoy_years),
            "gdp_m2": _pair_r(yoy_gdp, yoy_m2, yoy_years),
            "gdp_stock": _pair_r(yoy_gdp, yoy_stock, yoy_years),
            "m2_stock": _pair_r(yoy_m2, yoy_stock, yoy_years),
        },
        "read": "수준 r는 장기 추세의 영향을 받을 수 있다. 전년 대비 r가 같은 해 동조에 더 가깝다. n이 작아 안정적 관계로 읽지 않는다.",
    }


def _smoke_year(y: int, re_eok: dict[int, float], den: dict[str, Any]) -> dict[str, Any]:
    re_v = re_eok.get(y)
    gdp = den["gdp_eok"].get(y)
    m2 = den["m2_eok"].get(y)
    stock = den["stock_eok"].get(y)
    ok = all(v is not None and v > 0 for v in (re_v, gdp, m2, stock))
    return {
        "year": y,
        "re_eok": None if re_v is None else round(re_v, 4),
        "gdp_eok": None if gdp is None else round(gdp, 4),
        "m2_eok": None if m2 is None else round(m2, 4),
        "stock_eok": None if stock is None else round(stock, 4),
        "vs_gdp_pct": None if not (re_v and gdp) else round(100.0 * re_v / gdp, 4),
        "vs_m2_pct": None if not (re_v and m2) else round(100.0 * re_v / m2, 4),
        "vs_stock_pct": None if not (re_v and stock) else round(100.0 * re_v / stock, 4),
        "unit_ok": ok,
    }


def compute_annual_scale(
    *,
    month_rows: Iterable[dict[str, Any]],
    data_dir: Path | None = None,
    year_lo: int = YEAR_LO,
    year_hi: int = YEAR_HI,
    as_of: str | None = None,
) -> dict[str, Any]:
    notes: list[str] = []
    den = load_denominators(data_dir)
    notes.extend(den["notes"])
    year_eok = month_rows_to_year_eok(month_rows, notes, year_lo=year_lo, year_hi=year_hi)
    total = year_eok.get("합계") or {}
    years = sorted(
        y
        for y in total
        if y in den["gdp_eok"] and y in den["m2_eok"] and y in den["stock_eok"]
    )
    mix_share = {name: _share_pct(year_eok.get(name) or {}, total, years) for name in MIX_TYPES}
    mix_amt = {name: _pts(year_eok.get(name) or {}, years) for name in MIX_TYPES}
    mix_amt["합계"] = _pts(total, years)
    type_vs_gdp = {name: _ratio_pct(year_eok.get(name) or {}, den["gdp_eok"], years) for name in MIX_TYPES}
    corr = annual_corr(total, den["gdp_eok"], den["m2_eok"], den["stock_eok"], years)

    return {
        "lab": "macro_annual_scale",
        "note": "연 거래액 회전 vs 명목 GDP·M2 잔액·주식 거래대금. 인과 아님. GDP 기여도 아님.",
        "grain": "calendar_year",
        "unit": "십억원",
        "ratio_unit": "percent",
        "as_of": as_of or date.today().isoformat(),
        "year_start": years[0] if years else year_lo,
        "year_end": years[-1] if years else year_hi,
        "years": years,
        "types": list(MIX_TYPES),
        "sources": den["sources"],
        "coverage_notes": notes,
        "missing": den["missing"],
        "levels_eok": {
            "re_total": _pts(total, years),
            "gdp": _pts(den["gdp_eok"], years),
            "m2": _pts(den["m2_eok"], years),
            "stock": _pts(den["stock_eok"], years),
        },
        "ratios": {
            "vs_gdp": _ratio_pct(total, den["gdp_eok"], years),
            "vs_m2": _ratio_pct(total, den["m2_eok"], years),
            "vs_stock": _ratio_pct(total, den["stock_eok"], years),
        },
        "mix": {"types": list(MIX_TYPES), "share": mix_share, "amount_eok": mix_amt},
        "type_vs_gdp": type_vs_gdp,
        "corr": corr,
        "smoke": {
            "2010": _smoke_year(2010, total, den),
            "2024": _smoke_year(2024, total, den),
        },
        "limits": [
            "거래액/GDP는 부동산이 경제에서 차지하는 비중이 아니다. 기존 자산의 거래액을 그해 GDP와 비교한 규모 지표다.",
            "거래액/M2는 시중 돈이 부동산으로 이동했다는 뜻이 아니다. M2는 잔액, 거래액은 그해 발생액이다.",
            "주식 대비는 대체 투자의 증거가 아니다.",
            "합계는 여덟 유형 단순 합이며 모든 부동산이 아니다.",
            "연 전년대비 r는 같은 해 동조 확인용이다. 인과가 아니며 월 시차 r(1번)과 다른 질문이다.",
        ],
        "resume": {
            "next_id": "hold",
            "title": "1차 유지",
            "say": "공개 본문은 /insight/?q=5. 이 랩은 스냅샷 재계산·단위 게이트. M2 상품 구성은 다른 실험.",
            "do_not": "원 금액 이중축, 금리, GDP 기여도 문장, #1에 연 그래프, M2 상품을 이 랩에 붙이기.",
            "how": "docs/MACRO_INSIGHT_05.md · python -m app.macro_ts.annual_scale",
        },
    }


def fetch_national_month_rows(db: Session | None) -> list[dict[str, Any]]:
    if db is None:
        return []
    row = db.execute(
        text("SELECT to_regclass('public.national_month')::text IS NOT NULL AS ok")
    ).mappings().first()
    if not row or not row["ok"]:
        return []
    return [
        {"mix_type": r["mix_type"], "ym": int(r["ym"]), "amount_10k": r["amount_10k"] or 0}
        for r in db.execute(text("SELECT mix_type, ym, amount_10k FROM national_month")).mappings().all()
    ]


def write_snapshot(payload: dict[str, Any], path: Path | None = None) -> Path:
    dest = path or OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return dest


def main() -> None:
    from app.macro_ts.db import get_macro_ts_session_factory

    factory = get_macro_ts_session_factory()
    if factory is None:
        raise SystemExit("MACRO_TS_DATABASE_URL 없음")
    db = factory()
    try:
        rows = fetch_national_month_rows(db)
        if not rows:
            raise SystemExit("national_month 비어 있음")
        payload = compute_annual_scale(month_rows=rows)
        path = write_snapshot(payload)
    finally:
        db.close()
    smoke = payload["smoke"]
    print("wrote", path)
    print("years", payload["years"][0], "-", payload["years"][-1], "n=", len(payload["years"]))
    for key in ("2010", "2024"):
        s = smoke[key]
        print(
            f"smoke {key}: re={s['re_eok']} gdp={s['gdp_eok']} m2={s['m2_eok']} "
            f"stock={s['stock_eok']} vs_gdp={s['vs_gdp_pct']} unit_ok={s['unit_ok']}"
        )


if __name__ == "__main__":
    main()
