"""G3 랩 — 전국 달력연도 8유형 건수·액 × ECOS 금리·M2.

시군구 r 없음. 인과 아님. 상가·공장은 yearly_mix와 같이 일반+집합을 합친다.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.regional_profile.ecos_csv import _yoy_pct, load_macro_ecos
from app.regional_profile.market_size_lab import MIX_TYPES, pearson

_Y0, _Y1 = 2010, 2025


def _table_ok(db: Session | None, name: str) -> bool:
    if db is None:
        return False
    row = db.execute(
        text("SELECT to_regclass(:n)::text IS NOT NULL AS ok"),
        {"n": f"public.{name}"},
    ).mappings().first()
    return bool(row and row["ok"])


def _year_map(points: list[dict[str, Any]], field: str = "v") -> dict[int, float]:
    return {int(p["year"]): float(p[field]) for p in points if "year" in p}


def _lag_pearson(left: dict[int, float], right: dict[int, float], lag: int) -> dict[str, Any]:
    """left[t] vs right[t+lag]."""
    xs: list[float] = []
    ys: list[float] = []
    for t, xv in left.items():
        yv = right.get(t + lag)
        if yv is None:
            continue
        xs.append(xv)
        ys.append(yv)
    r = pearson(xs, ys)
    return {"n": len(xs), "r": round(r, 4) if r is not None else None, "lag": lag}


def _pack_series(by_year: dict[int, dict[str, float]]) -> dict[str, Any]:
    years = sorted(by_year)
    counts = [{"year": y, "v": by_year[y]["count"]} for y in years]
    amounts = [{"year": y, "v": by_year[y]["amount"]} for y in years]
    return {
        "count": counts,
        "amount": amounts,
        "yoy_count": _yoy_pct(counts),
        "yoy_amount": _yoy_pct(amounts),
    }


def _add(dst: dict[int, dict[str, float]], year: int, count: float, amount: float) -> None:
    cell = dst.setdefault(int(year), {"count": 0.0, "amount": 0.0})
    cell["count"] += float(count)
    cell["amount"] += float(amount)


def _fetch_land(db: Session | None, notes: list[str]) -> dict[int, dict[str, float]]:
    out: dict[int, dict[str, float]] = {}
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
            {"y0": _Y0, "y1": _Y1},
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
) -> dict[str, dict[int, dict[str, float]]]:
    out: dict[str, dict[int, dict[str, float]]] = defaultdict(dict)
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
            {"y0": _Y0, "y1": _Y1},
        ).mappings().all()
    except Exception as exc:
        notes.append(f"{table} 합 실패: {exc}")
        return out
    for r in rows:
        domain = str(r["domain"] or "").strip()
        _add(out[domain], int(r["calendar_year"]), r["n"] or 0, r["amt"] or 0)
    return out


def _merge_mix(
    land: dict[int, dict[str, float]],
    built: dict[str, dict[int, dict[str, float]]],
    cc: dict[str, dict[int, dict[str, float]]],
    market: dict[str, dict[int, dict[str, float]]],
) -> dict[str, dict[int, dict[str, float]]]:
    sources: dict[str, list[dict[int, dict[str, float]]]] = {
        "토지": [land],
        "상가": [built.get("commercial") or {}, cc.get("collective_shop") or {}],
        "공장": [built.get("factory") or {}, cc.get("collective_factory") or {}],
        "단독다가구": [built.get("detached") or {}],
        "아파트": [market.get("apartment_market") or {}],
        "오피스텔": [market.get("officetel_market") or {}],
        "연립다세대": [market.get("rowhouse_market") or {}],
        "분양권": [market.get("presale_market") or {}],
    }
    types: dict[str, dict[int, dict[str, float]]] = {}
    for name in MIX_TYPES:
        acc: dict[int, dict[str, float]] = {}
        for part in sources[name]:
            for y, cell in part.items():
                _add(acc, y, cell["count"], cell["amount"])
        types[name] = acc
    total: dict[int, dict[str, float]] = {}
    for part in types.values():
        for y, cell in part.items():
            _add(total, y, cell["count"], cell["amount"])
    types["합계"] = total
    return types


def compute_macro_ts(
    *,
    land_db: Session | None,
    built_db: Session | None,
    coll_db: Session | None,
    data_dir=None,
) -> dict[str, Any]:
    ecos = load_macro_ecos(data_dir=data_dir)
    notes: list[str] = []
    land = _fetch_land(land_db, notes)
    built = _fetch_sido_annual(
        built_db, table="built_annual_stats", domain_col="asset_type", notes=notes
    )
    cc = _fetch_sido_annual(
        coll_db,
        table="collective_commercial_region_annual_stats",
        domain_col="asset_type",
        notes=notes,
    )
    market = _fetch_sido_annual(
        coll_db, table="market_annual_stats", domain_col="market_domain", notes=notes
    )
    mixed = _merge_mix(land, built, cc, market)
    types_out = {name: _pack_series(by_y) for name, by_y in mixed.items()}

    rate_dpp = {
        rid: _year_map(block["d_pp"]) for rid, block in ecos["rates"].items()
    }
    m2_yoy = _year_map(ecos["m2"]["yoy_pct"]) if ecos.get("m2") else {}

    pairs: list[dict[str, Any]] = []
    for name, series in types_out.items():
        yc = _year_map(series["yoy_count"])
        ya = _year_map(series["yoy_amount"])
        row: dict[str, Any] = {"type": name}
        for rid, dpp in rate_dpp.items():
            row[f"{rid}_count_lag0"] = _lag_pearson(dpp, yc, 0)
            row[f"{rid}_count_lag1"] = _lag_pearson(dpp, yc, 1)
            row[f"{rid}_amount_lag0"] = _lag_pearson(dpp, ya, 0)
            row[f"{rid}_amount_lag1"] = _lag_pearson(dpp, ya, 1)
        if m2_yoy:
            row["m2_count_lag0"] = _lag_pearson(m2_yoy, yc, 0)
            row["m2_count_lag1"] = _lag_pearson(m2_yoy, yc, 1)
            row["m2_amount_lag0"] = _lag_pearson(m2_yoy, ya, 0)
            row["m2_amount_lag1"] = _lag_pearson(m2_yoy, ya, 1)
        pairs.append(row)

    return {
        **ecos,
        "lab": "macro_ts",
        "note": "전국 달력연도. 금리 변화(%p)·M2 YoY ↔ 거래 건수/액 YoY. 수준 상관은 추세 주의. 인과 아님.",
        "types": list(MIX_TYPES) + ["합계"],
        "series": types_out,
        "pairs": pairs,
        "coverage_notes": notes,
    }
