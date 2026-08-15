#!/usr/bin/env python3
"""rent_transactions → rent_conversion_rates (4후보 r + gate)."""

from __future__ import annotations

import argparse
import json
import logging
import sys
import uuid
from collections import defaultdict
from datetime import date
from pathlib import Path

from psycopg2.extras import execute_values
from sqlalchemy import text
from tqdm import tqdm

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "pipeline"))

from build_stats_v2 import (  # noqa: E402
    default_as_of_month,
    parse_as_of_month,
    period_bounds_for_window,
)
from rent.conversion import (  # noqa: E402
    DEFAULT_METHOD,
    building_obs_from_rows,
    candidate_rates,
    region_gate,
    select_rate,
)
from rent.db_utils import get_rent_engine  # noqa: E402
from rent.stats_pack import ASSET_TYPES, BUILDING_KEY_SQL  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

DDL = REPO / "db" / "057_rent_conversion_rates.sql"
DDL_ADDR3 = REPO / "db" / "058_rent_conversion_addr3.sql"
IDENTIFY_TYPES = ("apartment", "rowhouse", "officetel")

FETCH_SQL = f"""
SELECT
    {BUILDING_KEY_SQL} AS building_key,
    addr1,
    addr2,
    addr3,
    asset_type,
    deposit_per_m2,
    monthly_per_m2,
    COALESCE(deposit_manwon, 0) AS deposit_manwon,
    COALESCE(monthly_rent_manwon, 0) AS monthly_rent_manwon
FROM rent_transactions
WHERE is_valid = true
  AND contract_date IS NOT NULL
  AND contract_date >= :p_start
  AND contract_date <= :p_end
  AND asset_type = ANY(:asset_types)
  {{addr1_clause}}
ORDER BY addr1, addr2, asset_type, building_key
"""

COLS = (
    "as_of_month",
    "window_years",
    "period_start",
    "period_end",
    "addr1",
    "addr2",
    "addr3",
    "asset_type",
    "n_buildings",
    "n_jeonse",
    "n_mixed",
    "r_mean_simple",
    "r_mean_weighted",
    "r_ols_origin",
    "r_ols_weighted",
    "r_selected",
    "method_selected",
    "gate_passed",
    "batch_id",
)

UPDATES = tuple(
    c for c in COLS if c not in ("as_of_month", "window_years", "addr1", "addr2", "addr3", "asset_type")
)


def _apply_ddl(engine) -> None:
    with engine.begin() as conn:
        exists = conn.execute(text("SELECT to_regclass('public.rent_conversion_rates')")).scalar()
        if not exists:
            conn.execute(text(DDL.read_text(encoding="utf-8")))
        if DDL_ADDR3.exists():
            conn.execute(text(DDL_ADDR3.read_text(encoding="utf-8")))
    log.info("applied %s %s", DDL.name, DDL_ADDR3.name)


def _fetch_rows(engine, *, p_start: date, p_end: date, addr1: str | None) -> list[dict]:
    addr1_clause = "AND addr1 = :addr1" if addr1 else ""
    sql = FETCH_SQL.format(addr1_clause=addr1_clause)
    params: dict = {
        "p_start": p_start,
        "p_end": p_end,
        "asset_types": list(IDENTIFY_TYPES),
    }
    if addr1:
        params["addr1"] = addr1
    with engine.connect() as conn:
        return [dict(r) for r in conn.execute(text(sql), params).mappings().all()]


def _group_region(rows: list[dict], *, with_dong: bool) -> dict[tuple[str, str, str, str], list]:
    by_bld: dict[tuple, list[dict]] = defaultdict(list)
    for r in rows:
        a2 = str(r.get("addr2") or "").strip()
        a3 = str(r.get("addr3") or "").strip() if with_dong else ""
        if with_dong and not a3:
            continue
        key = (r["addr1"], str(a2).strip(), a3, r["asset_type"], str(r["building_key"]))
        by_bld[key].append(r)
    regions: dict[tuple[str, str, str, str], list] = defaultdict(list)
    for (a1, a2, a3, at, _bk), brows in by_bld.items():
        obs = building_obs_from_rows(brows)
        if obs:
            regions[(a1, a2, a3, at)].append(obs)
    return regions


def _build_records(
    regions: dict[tuple[str, str, str, str], list],
    *,
    as_of_month: date,
    window_years: int,
    period_start: date,
    period_end: date,
    batch_id: str,
    method: str,
    level: str,
) -> list[dict]:
    out: list[dict] = []
    for (a1, a2, a3, at), obs in sorted(regions.items()):
        ok, nb, nj, nm = region_gate(obs, level=level)
        cand = candidate_rates(obs)
        r_sel = select_rate(cand, method=method) if ok else None
        out.append(
            {
                "as_of_month": as_of_month,
                "window_years": window_years,
                "period_start": period_start,
                "period_end": period_end,
                "addr1": a1,
                "addr2": a2,
                "addr3": a3 or "",
                "asset_type": at,
                "n_buildings": nb,
                "n_jeonse": nj,
                "n_mixed": nm,
                **cand,
                "r_selected": r_sel,
                "method_selected": method,
                "gate_passed": ok and r_sel is not None,
                "batch_id": batch_id,
            }
        )
    return out


def _upsert(engine, records: list[dict]) -> None:
    if not records:
        return
    placeholders = "(" + ",".join(["%s"] * len(COLS)) + ")"
    set_sql = ", ".join(f"{c} = EXCLUDED.{c}" for c in UPDATES)
    sql = f"""
        INSERT INTO rent_conversion_rates ({", ".join(COLS)})
        VALUES %s
        ON CONFLICT (as_of_month, window_years, addr1, addr2, addr3, asset_type)
        DO UPDATE SET {set_sql}, computed_at = NOW()
    """
    tuples = [tuple(rec.get(c) for c in COLS) for rec in records]
    raw = engine.raw_connection()
    try:
        cur = raw.cursor()
        execute_values(cur, sql, tuples, template=placeholders, page_size=500)
        raw.commit()
        cur.close()
    finally:
        raw.close()


def _distinct_addr1(conn) -> list[str]:
    rows = conn.execute(
        text(
            """
            SELECT DISTINCT addr1 AS a
            FROM rent_transactions
            WHERE addr1 IS NOT NULL AND btrim(addr1::text) <> ''
            ORDER BY 1
            """
        )
    ).fetchall()
    return [str(r.a) for r in rows]


def _json_safe(obj):
    if isinstance(obj, date):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_json_safe(x) for x in obj]
    return obj


def coverage_report(records: list[dict]) -> dict:
    """서울 5년 식별 커버리지 요약."""
    seoul = [
        r
        for r in records
        if r.get("addr1") == "서울특별시"
        and r.get("window_years") == 5
        and not (r.get("addr3") or "").strip()
    ]
    by_type: dict[str, list] = defaultdict(list)
    for r in seoul:
        by_type[r["asset_type"]].append(r)
    summary = {}
    for at, rows in sorted(by_type.items()):
        passed = [r for r in rows if r.get("gate_passed")]
        summary[at] = {
            "sigungu_total": len(rows),
            "sigungu_gate_passed": len(passed),
            "median_buildings": _median([r["n_buildings"] for r in rows]),
            "p25_buildings": _pct(rows, "n_buildings", 0.25),
            "p75_buildings": _pct(rows, "n_buildings", 0.75),
            "median_jeonse_n": _median([r["n_jeonse"] for r in rows]),
            "median_mixed_n": _median([r["n_mixed"] for r in rows]),
        }
    return _json_safe({"seoul_5y": summary, "regions": seoul})


def _median(vals: list) -> float | None:
    if not vals:
        return None
    s = sorted(vals)
    m = len(s) // 2
    return float(s[m]) if len(s) % 2 else (s[m - 1] + s[m]) / 2.0


def _pct(rows: list[dict], key: str, q: float) -> float | None:
    vals = sorted(r[key] for r in rows if r.get(key) is not None)
    if not vals:
        return None
    idx = int(q * (len(vals) - 1))
    return float(vals[idx])


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--as-of", default=None)
    p.add_argument("--windows", default="3,5,7")
    p.add_argument("--addr1", default=None)
    p.add_argument("--method", default=DEFAULT_METHOD)
    p.add_argument("--report-json", default=None, help="커버리지·후보 비교 JSON 저장")
    args = p.parse_args()

    as_of = parse_as_of_month(args.as_of) if args.as_of else default_as_of_month()
    windows = [int(x.strip()) for x in args.windows.split(",") if x.strip()]
    engine = get_rent_engine()
    _apply_ddl(engine)
    batch_id = uuid.uuid4().hex[:12]
    log.info("as_of=%s windows=%s method=%s batch=%s", as_of, windows, args.method, batch_id)

    with engine.connect() as conn:
        addr1_list = [args.addr1] if args.addr1 else _distinct_addr1(conn)

    all_records: list[dict] = []
    for window_years in windows:
        ps, pe = period_bounds_for_window(as_of, window_years)
        log.info("conversion window=%sy %s..%s", window_years, ps, pe)
        chunk: list[dict] = []
        for addr1 in tqdm(addr1_list, desc=f"conv w{window_years}"):
            rows = _fetch_rows(engine, p_start=ps, p_end=pe, addr1=addr1)
            recs = []
            for with_dong, level in ((False, "sigungu"), (True, "dong")):
                regions = _group_region(rows, with_dong=with_dong)
                recs.extend(
                    _build_records(
                        regions,
                        as_of_month=as_of,
                        window_years=window_years,
                        period_start=ps,
                        period_end=pe,
                        batch_id=batch_id,
                        method=args.method,
                        level=level,
                    )
                )
            _upsert(engine, recs)
            chunk.extend(recs)
        passed = sum(1 for r in chunk if r["gate_passed"])
        log.info("window=%s regions=%s gate_passed=%s", window_years, len(chunk), passed)
        all_records.extend(chunk)

    if args.report_json:
        report = coverage_report(all_records)
        Path(args.report_json).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        log.info("wrote report %s", args.report_json)

    log.info("done batch=%s", batch_id)


if __name__ == "__main__":
    main()
