#!/usr/bin/env python3
"""분양·입주권 → collective_presale_lifetime_stats (전체 거래기간)."""

from __future__ import annotations

import argparse
import gc
import logging
import sys
import uuid
import warnings
from datetime import date
from pathlib import Path

import pandas as pd
from sqlalchemy import text
from tqdm import tqdm

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "pipeline"))

from build_stats_v2 import default_as_of_month, parse_as_of_month  # noqa: E402
from collective.db_utils import get_collective_engine  # noqa: E402
from stats import compute_stats  # noqa: E402

warnings.filterwarnings("ignore", category=RuntimeWarning, module="scipy")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

DEFAULT_UPSERT_CHUNK = 400

LIFETIME_SQL = """
SELECT
    building_key,
    MAX(display_name) AS display_name,
    MAX(addr1) AS addr1,
    MAX(addr2) AS addr2,
    MAX(addr3) AS addr3,
    MAX(addr4) AS addr4,
    MAX(addr5) AS addr5,
    MAX(beopjungri_code) AS beopjungri_code,
    MAX(sigungu_code) AS sigungu_code,
    MAX(lot_number) AS lot_number,
    MAX(road_name) AS road_name,
    MAX(building_year) AS building_year,
    MIN(contract_date) AS period_start,
    MAX(contract_date) AS period_end,
    array_agg(unit_price ORDER BY unit_price) AS prices
FROM collective_transactions
WHERE is_valid = true
  AND asset_type = 'presale'
  AND unit_price IS NOT NULL
  AND unit_price > 0
  AND contract_date IS NOT NULL
  {addr1_clause}
GROUP BY building_key
"""


def _distinct_addr1(conn) -> list[str]:
    rows = conn.execute(
        text(
            """
            SELECT DISTINCT addr1 AS a
            FROM collective_transactions
            WHERE asset_type = 'presale'
              AND addr1 IS NOT NULL AND btrim(addr1::text) <> ''
            ORDER BY 1
            """
        )
    ).fetchall()
    return [str(r.a) for r in rows]


def _record(row, *, snapshot_as_of: date, batch_id: str) -> dict | None:
    prices = [float(x) for x in (row["prices"] or []) if x is not None]
    if not prices:
        return None
    st = compute_stats(prices)
    if st["count"] <= 0:
        return None
    ps, pe = row["period_start"], row["period_end"]
    if ps is None or pe is None:
        return None
    by = row.get("building_year")
    return {
        "building_key": row["building_key"],
        "asset_type": "presale",
        "display_name": row["display_name"] or "",
        "addr1": row.get("addr1"),
        "addr2": row.get("addr2"),
        "addr3": row.get("addr3"),
        "addr4": row.get("addr4"),
        "addr5": row.get("addr5"),
        "beopjungri_code": row.get("beopjungri_code"),
        "sigungu_code": row.get("sigungu_code"),
        "lot_number": row.get("lot_number"),
        "road_name": row.get("road_name"),
        "building_year": int(by) if by is not None and not pd.isna(by) else None,
        "period_start": ps,
        "period_end": pe,
        "count": st["count"],
        "mean": st["mean"],
        "std": st["std"],
        "ci_lower": st["ci_lower"],
        "ci_upper": st["ci_upper"],
        "p_min": st["min"],
        "p25": st["p25"],
        "median": st["median"],
        "p75": st["p75"],
        "p_max": st["max"],
        "snapshot_as_of": snapshot_as_of,
        "batch_id": batch_id,
    }


def upsert(records: list[dict], engine, *, chunk_size: int = DEFAULT_UPSERT_CHUNK) -> None:
    if not records:
        return
    sql = text(
        """
        INSERT INTO collective_presale_lifetime_stats (
            building_key, asset_type, display_name,
            addr1, addr2, addr3, addr4, addr5, beopjungri_code, sigungu_code,
            lot_number, road_name, building_year,
            period_start, period_end,
            count, mean, std, ci_lower, ci_upper,
            p_min, p25, median, p75, p_max,
            snapshot_as_of, computed_at, batch_id
        ) VALUES (
            :building_key, :asset_type, :display_name,
            :addr1, :addr2, :addr3, :addr4, :addr5, :beopjungri_code, :sigungu_code,
            :lot_number, :road_name, :building_year,
            :period_start, :period_end,
            :count, :mean, :std, :ci_lower, :ci_upper,
            :p_min, :p25, :median, :p75, :p_max,
            :snapshot_as_of, NOW(), :batch_id
        )
        ON CONFLICT (building_key) DO UPDATE SET
            display_name = EXCLUDED.display_name,
            addr1 = EXCLUDED.addr1,
            addr2 = EXCLUDED.addr2,
            addr3 = EXCLUDED.addr3,
            addr4 = EXCLUDED.addr4,
            addr5 = EXCLUDED.addr5,
            beopjungri_code = EXCLUDED.beopjungri_code,
            sigungu_code = EXCLUDED.sigungu_code,
            lot_number = EXCLUDED.lot_number,
            road_name = EXCLUDED.road_name,
            building_year = EXCLUDED.building_year,
            period_start = EXCLUDED.period_start,
            period_end = EXCLUDED.period_end,
            count = EXCLUDED.count,
            mean = EXCLUDED.mean,
            std = EXCLUDED.std,
            ci_lower = EXCLUDED.ci_lower,
            ci_upper = EXCLUDED.ci_upper,
            p_min = EXCLUDED.p_min,
            p25 = EXCLUDED.p25,
            median = EXCLUDED.median,
            p75 = EXCLUDED.p75,
            p_max = EXCLUDED.p_max,
            snapshot_as_of = EXCLUDED.snapshot_as_of,
            computed_at = NOW(),
            batch_id = EXCLUDED.batch_id
        """
    )
    for start in range(0, len(records), chunk_size):
        chunk = records[start : start + chunk_size]
        with engine.begin() as conn:
            for rec in chunk:
                conn.execute(sql, rec)


def build(*, engine, snapshot_as_of: date, addr1_filter: str | None, batch_id: str) -> int:
    total = 0
    with engine.connect() as conn:
        addr1_list = [addr1_filter] if addr1_filter else _distinct_addr1(conn)

    for addr1 in tqdm(addr1_list, desc="presale-lifetime"):
        clause = "AND addr1 = :addr1" if addr1 else ""
        params: dict = {}
        if addr1:
            params["addr1"] = addr1
        with engine.connect() as conn:
            rows = conn.execute(text(LIFETIME_SQL.format(addr1_clause=clause)), params).mappings().all()
        records = []
        for row in rows:
            rec = _record(dict(row), snapshot_as_of=snapshot_as_of, batch_id=batch_id)
            if rec:
                records.append(rec)
        upsert(records, engine)
        total += len(records)
        del rows, records
        gc.collect()
    return total


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--as-of", type=str, default=None, help="snapshot_as_of YYYY-MM-01")
    p.add_argument("--addr1", type=str, default=None)
    p.add_argument("--replace", action="store_true", help="빌드 전 테이블 TRUNCATE")
    args = p.parse_args()

    snapshot = parse_as_of_month(args.as_of) if args.as_of else default_as_of_month()
    eng = get_collective_engine()
    batch_id = str(uuid.uuid4())

    with eng.connect() as conn:
        exists = conn.execute(
            text("SELECT to_regclass('public.collective_presale_lifetime_stats')")
        ).scalar()
        if not exists:
            raise SystemExit("collective_presale_lifetime_stats 없음 — db/040_….sql 적용 필요")

    if args.replace:
        with eng.begin() as conn:
            conn.execute(text("TRUNCATE collective_presale_lifetime_stats"))
            log.info("truncated collective_presale_lifetime_stats")

    n = build(engine=eng, snapshot_as_of=snapshot, addr1_filter=args.addr1, batch_id=batch_id)
    with eng.connect() as conn:
        tot = conn.execute(text("SELECT COUNT(*) FROM collective_presale_lifetime_stats")).scalar()
    log.info("upserted ~%s rows; table total=%s snapshot_as_of=%s batch=%s", n, tot, snapshot, batch_id)


if __name__ == "__main__":
    main()
