"""G3 랩 — 전국 8유형 건수·액 × ECOS 금리·M2 (연도·월).

시군구 r 없음. 인과 아님. 상가·공장은 yearly_mix와 같이 일반+집합을 합친다.
월은 전년동월 YoY, 시차 0/1/3/6개월.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Any, Literal

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.regional_profile.ecos_csv import (
    Grain,
    _yoy_pct,
    add_periods,
    load_macro_ecos,
    ym_int,
    ym_str,
)
from app.regional_profile.market_size_lab import MIX_TYPES, pearson

_Y0 = 2010
_Y1_YEAR = 2025
_Y1_MONTH = 2026

LAGS_YEAR = (0, 1)
LAGS_MONTH = (0, 1, 3, 6)

KeyMap = dict[int, dict[str, float]]
DomainMap = dict[str, KeyMap]


def _table_ok(db: Session | None, name: str) -> bool:
    if db is None:
        return False
    row = db.execute(
        text("SELECT to_regclass(:n)::text IS NOT NULL AS ok"),
        {"n": f"public.{name}"},
    ).mappings().first()
    return bool(row and row["ok"])


def _point_map(points: list[dict[str, Any]]) -> dict[int, float]:
    out: dict[int, float] = {}
    for p in points:
        if "month" in p:
            out[ym_int(str(p["month"]))] = float(p["v"])
        elif "year" in p:
            out[int(p["year"])] = float(p["v"])
    return out


def _lag_pearson(
    left: dict[int, float],
    right: dict[int, float],
    lag: int,
    *,
    grain: Grain,
) -> dict[str, Any]:
    """left[t] vs right[t+lag]."""
    xs: list[float] = []
    ys: list[float] = []
    for t, xv in left.items():
        yv = right.get(add_periods(t, lag, grain=grain))
        if yv is None:
            continue
        xs.append(xv)
        ys.append(yv)
    r = pearson(xs, ys)
    return {"n": len(xs), "r": round(r, 4) if r is not None else None, "lag": lag}


def _pack_series(by_key: KeyMap, *, grain: Grain) -> dict[str, Any]:
    keys = sorted(by_key)
    if grain == "month":
        counts = [{"month": ym_str(k), "v": by_key[k]["count"]} for k in keys]
        amounts = [{"month": ym_str(k), "v": by_key[k]["amount"]} for k in keys]
    else:
        counts = [{"year": k, "v": by_key[k]["count"]} for k in keys]
        amounts = [{"year": k, "v": by_key[k]["amount"]} for k in keys]
    return {
        "count": counts,
        "amount": amounts,
        "yoy_count": _yoy_pct(counts),
        "yoy_amount": _yoy_pct(amounts),
    }


def _add(dst: KeyMap, key: int, count: float, amount: float) -> None:
    cell = dst.setdefault(int(key), {"count": 0.0, "amount": 0.0})
    cell["count"] += float(count)
    cell["amount"] += float(amount)


def _clip_open_month(dst: KeyMap, notes: list[str], *, today: date | None = None) -> KeyMap:
    if not dst:
        return dst
    today = today or date.today()
    cur = today.year * 100 + today.month
    last = max(dst)
    if last >= cur:
        notes.append(f"미완결월 제외 {ym_str(last)}")
        return {k: v for k, v in dst.items() if k < cur}
    return dst


def _fetch_national_month(db: Session | None, notes: list[str]) -> dict[str, KeyMap]:
    out: dict[str, KeyMap] = {name: {} for name in MIX_TYPES}
    if not _table_ok(db, "national_month"):
        notes.append("national_month 없음")
        out["합계"] = {}
        return out
    assert db is not None
    rows = db.execute(
        text("SELECT mix_type, ym, n, amount_10k FROM national_month")
    ).mappings().all()
    for r in rows:
        name = str(r["mix_type"] or "")
        if name not in out:
            continue
        _add(out[name], int(r["ym"]), r["n"] or 0, r["amount_10k"] or 0)
    for name in list(out):
        out[name] = _clip_open_month(out[name], notes)
    total: KeyMap = {}
    for part in out.values():
        for y, cell in part.items():
            _add(total, y, cell["count"], cell["amount"])
    out["합계"] = total
    if not total:
        notes.append("national_month 비어 있음")
    return out


def _rollup_calendar_year(month_mixed: dict[str, KeyMap], notes: list[str]) -> dict[str, KeyMap]:
    """월(yyyymm)을 달력연도로 더한다. 12개월이 안 찬 해는 빼서 부분 연 YoY를 만들지 않는다."""
    out: dict[str, KeyMap] = {}
    incomplete: set[int] = set()
    for name, by_ym in month_mixed.items():
        months: dict[int, int] = {}
        acc: KeyMap = {}
        for ym, cell in by_ym.items():
            y = int(ym) // 100
            _add(acc, y, cell["count"], cell["amount"])
            months[y] = months.get(y, 0) + 1
        dropped = [y for y in acc if months.get(y, 0) < 12]
        incomplete.update(dropped)
        out[name] = {y: acc[y] for y in acc if months.get(y, 0) >= 12}
    if incomplete:
        notes.append("미완결연 제외 " + ", ".join(str(y) for y in sorted(incomplete)))
    return out


def _fetch_land(db: Session | None, notes: list[str]) -> KeyMap:
    out: KeyMap = {}
    if not _table_ok(db, "land_annual_stats"):
        notes.append("land_annual_stats 없음")
        return out
    assert db is not None
    try:
        rows = db.execute(
            text(
                """
                SELECT calendar_year,
                       SUM(transaction_count) AS n,
                       SUM(amount_sum_10k) AS amt
                FROM land_annual_stats
                WHERE col_axis = 'category'
                  AND zone_type = 'ALL'
                  AND land_category = 'ALL'
                  AND calendar_year BETWEEN :y0 AND :y1
                GROUP BY calendar_year
                """
            ),
            {"y0": _Y0, "y1": _Y1_YEAR},
        ).mappings().all()
    except Exception as exc:
        notes.append(f"토지 연도 합 실패: {exc}")
        return out
    for r in rows:
        _add(out, int(r["calendar_year"]), r["n"] or 0, r["amt"] or 0)
    return out


def _fetch_sido_annual(
    db: Session | None,
    *,
    table: str,
    domain_col: str,
    notes: list[str],
) -> DomainMap:
    out: DomainMap = defaultdict(dict)
    if not _table_ok(db, table):
        notes.append(f"{table} 없음")
        return out
    assert db is not None
    try:
        rows = db.execute(
            text(
                f"""
                SELECT {domain_col} AS domain, calendar_year,
                       SUM(count) AS n, SUM(amount_sum) AS amt
                FROM {table}
                WHERE region_level = 'sido'
                  AND calendar_year BETWEEN :y0 AND :y1
                GROUP BY {domain_col}, calendar_year
                """
            ),
            {"y0": _Y0, "y1": _Y1_YEAR},
        ).mappings().all()
    except Exception as exc:
        notes.append(f"{table} 합 실패: {exc}")
        return out
    for r in rows:
        domain = str(r["domain"] or "").strip()
        _add(out[domain], int(r["calendar_year"]), r["n"] or 0, r["amt"] or 0)
    return out


def _fetch_land_month(db: Session | None, notes: list[str]) -> KeyMap:
    out: KeyMap = {}
    if not _table_ok(db, "land_transactions"):
        notes.append("land_transactions 없음")
        return out
    assert db is not None
    try:
        rows = db.execute(
            text(
                """
                SELECT (EXTRACT(YEAR FROM contract_date)::int * 100
                        + EXTRACT(MONTH FROM contract_date)::int) AS ym,
                       COUNT(*)::int AS n,
                       SUM(total_price_10k) AS amt
                FROM land_transactions
                WHERE is_valid = TRUE
                  AND is_cancelled = FALSE
                  AND unit_price_per_sqm IS NOT NULL
                  AND contract_date IS NOT NULL
                  AND btrim(COALESCE(zone_type::text, '')) <> ''
                  AND btrim(COALESCE(land_category::text, '')) <> ''
                  AND EXTRACT(YEAR FROM contract_date)::int BETWEEN :y0 AND :y1
                GROUP BY 1
                """
            ),
            {"y0": _Y0, "y1": _Y1_MONTH},
        ).mappings().all()
    except Exception as exc:
        notes.append(f"토지 월 합 실패: {exc}")
        return out
    for r in rows:
        _add(out, int(r["ym"]), r["n"] or 0, r["amt"] or 0)
    return _clip_open_month(out, notes)


def _fetch_built_month(db: Session | None, notes: list[str]) -> DomainMap:
    out: DomainMap = defaultdict(dict)
    if not _table_ok(db, "built_transactions"):
        notes.append("built_transactions 없음")
        return out
    assert db is not None
    try:
        rows = db.execute(
            text(
                """
                SELECT asset_type,
                       (contract_year * 100 + contract_month) AS ym,
                       COUNT(*)::int AS n,
                       SUM(price) AS amt
                FROM built_transactions
                WHERE is_valid = TRUE
                  AND contract_year BETWEEN :y0 AND :y1
                  AND contract_month BETWEEN 1 AND 12
                  AND price > 0
                GROUP BY 1, 2
                """
            ),
            {"y0": _Y0, "y1": _Y1_MONTH},
        ).mappings().all()
    except Exception as exc:
        notes.append(f"복합 월 합 실패: {exc}")
        return out
    for r in rows:
        domain = str(r["asset_type"] or "").strip()
        _add(out[domain], int(r["ym"]), r["n"] or 0, r["amt"] or 0)
    for domain, mp in list(out.items()):
        out[domain] = _clip_open_month(mp, notes)
    return out


def _fetch_coll_month(
    db: Session | None,
    *,
    table: str,
    domain_col: str,
    notes: list[str],
) -> DomainMap:
    out: DomainMap = defaultdict(dict)
    if not _table_ok(db, table):
        notes.append(f"{table} 없음")
        return out
    assert db is not None
    try:
        rows = db.execute(
            text(
                f"""
                SELECT {domain_col} AS domain,
                       (contract_year * 100 + contract_month) AS ym,
                       COUNT(*)::int AS n,
                       SUM(price) AS amt
                FROM {table}
                WHERE is_valid = TRUE
                  AND contract_year BETWEEN :y0 AND :y1
                  AND contract_month BETWEEN 1 AND 12
                  AND price > 0
                GROUP BY 1, 2
                """
            ),
            {"y0": _Y0, "y1": _Y1_MONTH},
        ).mappings().all()
    except Exception as exc:
        notes.append(f"{table} 월 합 실패: {exc}")
        return out
    for r in rows:
        domain = str(r["domain"] or "").strip()
        _add(out[domain], int(r["ym"]), r["n"] or 0, r["amt"] or 0)
    for domain, mp in list(out.items()):
        out[domain] = _clip_open_month(mp, notes)
    return out


def _merge_mix(
    land: KeyMap,
    built: DomainMap,
    cc: DomainMap,
    market: DomainMap,
) -> dict[str, KeyMap]:
    sources: dict[str, list[KeyMap]] = {
        "토지": [land],
        "상가": [built.get("commercial") or {}, cc.get("collective_shop") or {}],
        "공장": [built.get("factory") or {}, cc.get("collective_factory") or {}],
        "단독다가구": [built.get("detached") or {}],
        "아파트": [market.get("apartment") or market.get("apartment_market") or {}],
        "오피스텔": [market.get("officetel") or market.get("officetel_market") or {}],
        "연립다세대": [market.get("rowhouse") or market.get("rowhouse_market") or {}],
        "분양권": [market.get("presale") or market.get("presale_market") or {}],
    }
    types: dict[str, KeyMap] = {}
    for name in MIX_TYPES:
        acc: KeyMap = {}
        for part in sources[name]:
            for y, cell in part.items():
                _add(acc, y, cell["count"], cell["amount"])
        types[name] = acc
    total: KeyMap = {}
    for part in types.values():
        for y, cell in part.items():
            _add(total, y, cell["count"], cell["amount"])
    types["합계"] = total
    return types


def _pair_rows(
    types_out: dict[str, dict[str, Any]],
    *,
    ecos: dict[str, Any],
    grain: Grain,
    lags: tuple[int, ...],
) -> list[dict[str, Any]]:
    rate_dpp = {rid: _point_map(block["d_pp"]) for rid, block in ecos["rates"].items()}
    m2_yoy = _point_map(ecos["m2"]["yoy_pct"]) if ecos.get("m2") else {}
    pairs: list[dict[str, Any]] = []
    for name, series in types_out.items():
        yc = _point_map(series["yoy_count"])
        ya = _point_map(series["yoy_amount"])
        row: dict[str, Any] = {"type": name}
        for rid, dpp in rate_dpp.items():
            for lag in lags:
                row[f"{rid}_count_lag{lag}"] = _lag_pearson(dpp, yc, lag, grain=grain)
                row[f"{rid}_amount_lag{lag}"] = _lag_pearson(dpp, ya, lag, grain=grain)
        if m2_yoy:
            for lag in lags:
                row[f"m2_count_lag{lag}"] = _lag_pearson(m2_yoy, yc, lag, grain=grain)
                row[f"m2_amount_lag{lag}"] = _lag_pearson(m2_yoy, ya, lag, grain=grain)
        pairs.append(row)
    return pairs


def compute_macro_ts(
    *,
    land_db: Session | None,
    built_db: Session | None,
    coll_db: Session | None,
    macro_ts_db: Session | None = None,
    data_dir=None,
    grain: Literal["calendar_year", "calendar_month"] | Grain = "calendar_year",
) -> dict[str, Any]:
    freq: Grain = "month" if grain in {"month", "calendar_month"} else "year"
    ecos = load_macro_ecos(data_dir=data_dir, frequency=freq)
    notes: list[str] = list(ecos.get("coverage_notes") or [])
    lags = LAGS_MONTH if freq == "month" else LAGS_YEAR

    month_mixed = _fetch_national_month(macro_ts_db, notes)
    if freq == "month":
        mixed = month_mixed
        if mixed.get("합계") and "월 거래는 국토부 CSV 전국 합" not in "".join(notes):
            notes.append("월 거래는 국토부 CSV 전국 합. 제품 원장과 행이 다를 수 있음.")
        note = (
            "전국 달력월. 금리·M2·거래는 전년동월 변화. 시차 0/1/3/6개월. "
            "거래는 국토부 CSV 월 합. 수준 상관은 추세 주의. 인과 아님."
        )
    else:
        mixed = _rollup_calendar_year(month_mixed, notes)
        if mixed.get("합계") and "연 거래는 국토부 CSV 월 합" not in "".join(notes):
            notes.append("연 거래는 국토부 CSV 월 합을 달력연도로 더한 값. 제품 연 마트와 행이 다를 수 있음.")
        note = (
            "전국 달력연도. 금리 변화(%p)·M2 YoY ↔ 거래 건수/액 YoY. "
            "거래는 국토부 CSV 월 합을 연으로 더한 값. 수준 상관은 추세 주의. 인과 아님."
        )

    types_out = {name: _pack_series(by_k, grain=freq) for name, by_k in mixed.items()}
    pairs = _pair_rows(types_out, ecos=ecos, grain=freq, lags=lags)

    return {
        **ecos,
        "lab": "macro_ts",
        "note": note,
        "lags": list(lags),
        "types": list(MIX_TYPES) + ["합계"],
        "series": types_out,
        "pairs": pairs,
        "coverage_notes": notes,
    }
