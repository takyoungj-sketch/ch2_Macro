#!/usr/bin/env python3
"""
집합 Object Stats — collective_transactions → collective_building_stats (+ annual).

설계: docs/REGIONAL_PROFILE_ARCHITECTURE.md Phase A
"""

from __future__ import annotations

import argparse
import gc
import logging
import sys
import uuid
import warnings
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import text
from tqdm import tqdm

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "pipeline"))

from build_stats_v2 import (  # noqa: E402
    default_as_of_month,
    parse_as_of_month,
    period_bounds_for_window,
)
from collective.db_utils import get_collective_engine  # noqa: E402
from stats import compute_stats  # noqa: E402

warnings.filterwarnings("ignore", category=RuntimeWarning, module="scipy")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger(__name__)

ASSET_TYPES = ("apartment", "rowhouse", "officetel", "presale")
DEFAULT_UPSERT_CHUNK = 400

ROLLING_SQL = """
SELECT
    building_key,
    asset_type,
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
    array_agg(unit_price ORDER BY unit_price) AS prices
FROM collective_transactions
WHERE is_valid = true
  AND unit_price IS NOT NULL
  AND unit_price > 0
  AND contract_date IS NOT NULL
  AND contract_date >= :p_start
  AND contract_date <= :p_end
  {addr1_clause}
GROUP BY building_key, asset_type
"""

ANNUAL_SQL = """
SELECT
    building_key,
    asset_type,
    contract_year,
    MAX(display_name) AS display_name,
    MAX(addr1) AS addr1,
    MAX(addr2) AS addr2,
    MAX(addr3) AS addr3,
    MAX(addr4) AS addr4,
    MAX(beopjungri_code) AS beopjungri_code,
    array_agg(unit_price ORDER BY unit_price) AS prices
FROM collective_transactions
WHERE is_valid = true
  AND unit_price IS NOT NULL
  AND unit_price > 0
  AND contract_year IS NOT NULL
  {addr1_clause}
GROUP BY building_key, asset_type, contract_year
"""


def _distinct_addr1(conn) -> list[str]:
    rows = conn.execute(
        text(
            """
            SELECT DISTINCT addr1 AS a
            FROM collective_transactions
            WHERE addr1 IS NOT NULL AND btrim(addr1::text) <> ''
            ORDER BY 1
            """
        )
    ).fetchall()
    return [str(r.a) for r in rows]


def _records_from_row(
    row,
    *,
    as_of_month: date,
    window_years: int,
    period_start: date,
    period_end: date,
    batch_id: str,
) -> dict | None:
    prices = [float(x) for x in (row["prices"] or []) if x is not None]
    if not prices:
        return None
    st = compute_stats(prices)
    if st["count"] <= 0:
        return None
    by = row.get("building_year")
    return {
        "as_of_month": as_of_month,
        "window_years": window_years,
        "period_start": period_start,
        "period_end": period_end,
        "building_key": row["building_key"],
        "asset_type": row["asset_type"],
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
        "batch_id": batch_id,
    }


def upsert_building_stats(records: list[dict], engine, *, chunk_size: int = DEFAULT_UPSERT_CHUNK) -> None:
    if not records:
        return
    sql = text(
        """
        INSERT INTO collective_building_stats (
            as_of_month, window_years, period_start, period_end,
            building_key, asset_type, display_name,
            addr1, addr2, addr3, addr4, addr5, beopjungri_code, sigungu_code,
            lot_number, road_name, building_year,
            count, mean, std, ci_lower, ci_upper,
            p_min, p25, median, p75, p_max,
            computed_at, batch_id
        ) VALUES (
            :as_of_month, :window_years, :period_start, :period_end,
            :building_key, :asset_type, :display_name,
            :addr1, :addr2, :addr3, :addr4, :addr5, :beopjungri_code, :sigungu_code,
            :lot_number, :road_name, :building_year,
            :count, :mean, :std, :ci_lower, :ci_upper,
            :p_min, :p25, :median, :p75, :p_max,
            NOW(), :batch_id
        )
        ON CONFLICT (as_of_month, window_years, building_key, asset_type)
        DO UPDATE SET
            period_start = EXCLUDED.period_start,
            period_end = EXCLUDED.period_end,
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
            computed_at = NOW(),
            batch_id = EXCLUDED.batch_id
        """
    )
    for start in range(0, len(records), chunk_size):
        chunk = records[start : start + chunk_size]
        with engine.begin() as conn:
            for rec in chunk:
                conn.execute(sql, rec)


def upsert_annual_stats(records: list[dict], engine, *, chunk_size: int = DEFAULT_UPSERT_CHUNK) -> None:
    if not records:
        return
    sql = text(
        """
        INSERT INTO collective_building_annual_stats (
            building_key, asset_type, contract_year, display_name,
            addr1, addr2, addr3, addr4, beopjungri_code,
            count, mean, std, ci_lower, ci_upper, median,
            computed_at, batch_id
        ) VALUES (
            :building_key, :asset_type, :contract_year, :display_name,
            :addr1, :addr2, :addr3, :addr4, :beopjungri_code,
            :count, :mean, :std, :ci_lower, :ci_upper, :median,
            NOW(), :batch_id
        )
        ON CONFLICT (building_key, asset_type, contract_year)
        DO UPDATE SET
            display_name = EXCLUDED.display_name,
            addr1 = EXCLUDED.addr1,
            addr2 = EXCLUDED.addr2,
            addr3 = EXCLUDED.addr3,
            addr4 = EXCLUDED.addr4,
            beopjungri_code = EXCLUDED.beopjungri_code,
            count = EXCLUDED.count,
            mean = EXCLUDED.mean,
            std = EXCLUDED.std,
            ci_lower = EXCLUDED.ci_lower,
            ci_upper = EXCLUDED.ci_upper,
            median = EXCLUDED.median,
            computed_at = NOW(),
            batch_id = EXCLUDED.batch_id
        """
    )
    for start in range(0, len(records), chunk_size):
        chunk = records[start : start + chunk_size]
        with engine.begin() as conn:
            for rec in chunk:
                conn.execute(sql, rec)


def build_rolling(
    engine,
    *,
    as_of_month: date,
    windows: list[int],
    addr1_filter: str | None,
    batch_id: str,
) -> int:
    total = 0
    with engine.connect() as conn:
        addr1_list = [addr1_filter] if addr1_filter else _distinct_addr1(conn)

    for window_years in windows:
        ps, pe = period_bounds_for_window(as_of_month, window_years)
        log.info("window=%sy period=%s..%s", window_years, ps, pe)
        for addr1 in tqdm(addr1_list, desc=f"w{window_years}"):
            addr1_clause = "AND addr1 = :addr1" if addr1 else ""
            sql = ROLLING_SQL.format(addr1_clause=addr1_clause)
            params = {"p_start": ps, "p_end": pe}
            if addr1:
                params["addr1"] = addr1
            with engine.connect() as conn:
                rows = conn.execute(text(sql), params).mappings().all()
            records: list[dict] = []
            for row in rows:
                rec = _records_from_row(
                    row,
                    as_of_month=as_of_month,
                    window_years=window_years,
                    period_start=ps,
                    period_end=pe,
                    batch_id=batch_id,
                )
                if rec:
                    records.append(rec)
            upsert_building_stats(records, engine)
            total += len(records)
            del rows, records
            gc.collect()
    return total


def build_annual(engine, *, addr1_filter: str | None, batch_id: str) -> int:
    total = 0
    with engine.connect() as conn:
        addr1_list = [addr1_filter] if addr1_filter else _distinct_addr1(conn)

    for addr1 in tqdm(addr1_list, desc="annual"):
        addr1_clause = "AND addr1 = :addr1" if addr1 else ""
        sql = ANNUAL_SQL.format(addr1_clause=addr1_clause)
        params = {}
        if addr1:
            params["addr1"] = addr1
        with engine.connect() as conn:
            rows = conn.execute(text(sql), params).mappings().all()
        records: list[dict] = []
        for row in rows:
            prices = [float(x) for x in (row["prices"] or []) if x is not None]
            if not prices:
                continue
            st = compute_stats(prices)
            records.append(
                {
                    "building_key": row["building_key"],
                    "asset_type": row["asset_type"],
                    "contract_year": int(row["contract_year"]),
                    "display_name": row["display_name"] or "",
                    "addr1": row.get("addr1"),
                    "addr2": row.get("addr2"),
                    "addr3": row.get("addr3"),
                    "addr4": row.get("addr4"),
                    "beopjungri_code": row.get("beopjungri_code"),
                    "count": st["count"],
                    "mean": st["mean"],
                    "std": st["std"],
                    "ci_lower": st["ci_lower"],
                    "ci_upper": st["ci_upper"],
                    "median": st["median"],
                    "batch_id": batch_id,
                }
            )
        upsert_annual_stats(records, engine)
        total += len(records)
        del rows, records
        gc.collect()
    return total


def main() -> None:
    p = argparse.ArgumentParser(description="집합 building_stats / building_annual_stats")
    p.add_argument("--as-of", type=str, default=None, help="기준월 YYYY-MM-01")
    p.add_argument("--windows", type=str, default="3,5", help="롤링 창(년)")
    p.add_argument("--addr1", type=str, default=None, help="시도(addr1) 한정 스모크")
    p.add_argument("--skip-annual", action="store_true")
    p.add_argument("--rolling-only", action="store_true")
    args = p.parse_args()

    as_of = parse_as_of_month(args.as_of) if args.as_of else default_as_of_month()
    windows = sorted({int(x.strip()) for x in args.windows.split(",") if x.strip()})
    for w in windows:
        if w < 1 or w > 5:
            raise SystemExit("window_years must be 1..5")

    engine = get_collective_engine()
    batch_id = str(uuid.uuid4())

    with engine.connect() as conn:
        tx_n = conn.execute(text("SELECT COUNT(*) FROM collective_transactions")).scalar()
    log.info("collective_transactions rows=%s as_of=%s windows=%s", tx_n, as_of, windows)
    if not tx_n:
        raise SystemExit("collective_transactions empty — import_refined 먼저 실행")

    rolling_n = build_rolling(
        engine,
        as_of_month=as_of,
        windows=windows,
        addr1_filter=args.addr1,
        batch_id=batch_id,
    )
    log.info("collective_building_stats upserted ~%s rows (batch %s)", rolling_n, batch_id)

    annual_n = 0
    if not args.skip_annual and not args.rolling_only:
        annual_n = build_annual(engine, addr1_filter=args.addr1, batch_id=batch_id)
        log.info("collective_building_annual_stats upserted ~%s rows", annual_n)

    with engine.connect() as conn:
        cbs = conn.execute(text("SELECT COUNT(*) FROM collective_building_stats")).scalar()
        cba = conn.execute(text("SELECT COUNT(*) FROM collective_building_annual_stats")).scalar()
    log.info("totals: building_stats=%s annual_stats=%s", cbs, cba)


if __name__ == "__main__":
    main()
