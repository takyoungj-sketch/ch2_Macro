#!/usr/bin/env python3
"""집합상가·공장 cluster stats — collective_commercial_transactions → mart."""

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

from build_stats_v2 import default_as_of_month, parse_as_of_month, period_bounds_for_window  # noqa: E402
from collective.db_utils import get_collective_engine  # noqa: E402
from stats import compute_stats  # noqa: E402

warnings.filterwarnings("ignore", category=RuntimeWarning, module="scipy")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", stream=sys.stdout)
log = logging.getLogger(__name__)

DEFAULT_UPSERT_CHUNK = 400

ROLLING_SQL = """
SELECT
    t.cluster_key,
    t.asset_type,
    MAX(c.display_label) AS display_label,
    MAX(t.addr1) AS addr1,
    MAX(t.addr2) AS addr2,
    MAX(t.addr3) AS addr3,
    MAX(t.addr4) AS addr4,
    MAX(c.road_name) AS road_name,
    MAX(t.zone_type) AS zone_type,
    MAX(t.building_use) AS building_use,
    MAX(t.building_year) AS building_year,
    MAX(t.area_bucket_label) AS area_bucket_label,
    MAX(c.resolution_mode) AS resolution_mode,
    MAX(c.confidence_tier) AS confidence_tier,
    array_agg(t.unit_price ORDER BY t.unit_price) AS prices
FROM collective_commercial_transactions t
JOIN commercial_clusters c ON c.id = t.cluster_id
WHERE t.is_valid = true
  AND t.unit_price IS NOT NULL
  AND t.unit_price > 0
  AND t.contract_date IS NOT NULL
  AND t.contract_date >= :p_start
  AND t.contract_date <= :p_end
  {addr1_clause}
GROUP BY t.cluster_key, t.asset_type
"""

ANNUAL_SQL = """
SELECT
    t.cluster_key,
    t.asset_type,
    t.contract_year,
    MAX(c.display_label) AS display_label,
    MAX(t.addr1) AS addr1,
    MAX(t.addr2) AS addr2,
    MAX(t.addr3) AS addr3,
    MAX(t.addr4) AS addr4,
    MAX(c.road_name) AS road_name,
    array_agg(t.unit_price ORDER BY t.unit_price) AS prices
FROM collective_commercial_transactions t
JOIN commercial_clusters c ON c.id = t.cluster_id
WHERE t.is_valid = true
  AND t.unit_price IS NOT NULL
  AND t.unit_price > 0
  AND t.contract_year IS NOT NULL
  {addr1_clause}
GROUP BY t.cluster_key, t.asset_type, t.contract_year
"""


def _distinct_addr1(conn) -> list[str]:
    rows = conn.execute(
        text(
            """
            SELECT DISTINCT addr1 AS a
            FROM collective_commercial_transactions
            WHERE addr1 IS NOT NULL AND btrim(addr1::text) <> ''
            ORDER BY 1
            """
        )
    ).fetchall()
    return [str(r.a) for r in rows]


def _record_from_row(row, *, as_of_month, window_years, period_start, period_end, batch_id) -> dict | None:
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
        "cluster_key": row["cluster_key"],
        "asset_type": row["asset_type"],
        "display_label": row["display_label"] or "",
        "addr1": row.get("addr1"),
        "addr2": row.get("addr2"),
        "addr3": row.get("addr3"),
        "addr4": row.get("addr4"),
        "road_name": row.get("road_name"),
        "zone_type": row.get("zone_type"),
        "building_use": row.get("building_use"),
        "building_year": int(by) if by is not None and not pd.isna(by) else None,
        "area_bucket_label": row.get("area_bucket_label"),
        "resolution_mode": row.get("resolution_mode"),
        "confidence_tier": row.get("confidence_tier"),
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


def upsert_cluster_stats(records: list[dict], engine, *, chunk_size: int = DEFAULT_UPSERT_CHUNK) -> None:
    if not records:
        return
    sql = text(
        """
        INSERT INTO collective_commercial_cluster_stats (
            as_of_month, window_years, period_start, period_end,
            cluster_key, asset_type, display_label,
            addr1, addr2, addr3, addr4, road_name,
            zone_type, building_use, building_year, area_bucket_label,
            resolution_mode, confidence_tier,
            count, mean, std, ci_lower, ci_upper,
            p_min, p25, median, p75, p_max,
            computed_at, batch_id
        ) VALUES (
            :as_of_month, :window_years, :period_start, :period_end,
            :cluster_key, :asset_type, :display_label,
            :addr1, :addr2, :addr3, :addr4, :road_name,
            :zone_type, :building_use, :building_year, :area_bucket_label,
            :resolution_mode, :confidence_tier,
            :count, :mean, :std, :ci_lower, :ci_upper,
            :p_min, :p25, :median, :p75, :p_max,
            NOW(), :batch_id
        )
        ON CONFLICT (as_of_month, window_years, cluster_key, asset_type)
        DO UPDATE SET
            period_start = EXCLUDED.period_start,
            period_end = EXCLUDED.period_end,
            display_label = EXCLUDED.display_label,
            addr1 = EXCLUDED.addr1, addr2 = EXCLUDED.addr2, addr3 = EXCLUDED.addr3, addr4 = EXCLUDED.addr4,
            road_name = EXCLUDED.road_name,
            zone_type = EXCLUDED.zone_type, building_use = EXCLUDED.building_use,
            building_year = EXCLUDED.building_year, area_bucket_label = EXCLUDED.area_bucket_label,
            resolution_mode = EXCLUDED.resolution_mode, confidence_tier = EXCLUDED.confidence_tier,
            count = EXCLUDED.count, mean = EXCLUDED.mean, std = EXCLUDED.std,
            ci_lower = EXCLUDED.ci_lower, ci_upper = EXCLUDED.ci_upper,
            p_min = EXCLUDED.p_min, p25 = EXCLUDED.p25, median = EXCLUDED.median,
            p75 = EXCLUDED.p75, p_max = EXCLUDED.p_max,
            computed_at = NOW(), batch_id = EXCLUDED.batch_id
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
        INSERT INTO collective_commercial_cluster_annual_stats (
            cluster_key, asset_type, contract_year, display_label,
            addr1, addr2, addr3, addr4, road_name,
            count, mean, std, ci_lower, ci_upper, median,
            computed_at, batch_id
        ) VALUES (
            :cluster_key, :asset_type, :contract_year, :display_label,
            :addr1, :addr2, :addr3, :addr4, :road_name,
            :count, :mean, :std, :ci_lower, :ci_upper, :median,
            NOW(), :batch_id
        )
        ON CONFLICT (cluster_key, asset_type, contract_year)
        DO UPDATE SET
            display_label = EXCLUDED.display_label,
            addr1 = EXCLUDED.addr1, addr2 = EXCLUDED.addr2, addr3 = EXCLUDED.addr3, addr4 = EXCLUDED.addr4,
            road_name = EXCLUDED.road_name,
            count = EXCLUDED.count, mean = EXCLUDED.mean, std = EXCLUDED.std,
            ci_lower = EXCLUDED.ci_lower, ci_upper = EXCLUDED.ci_upper, median = EXCLUDED.median,
            computed_at = NOW(), batch_id = EXCLUDED.batch_id
        """
    )
    for start in range(0, len(records), chunk_size):
        chunk = records[start : start + chunk_size]
        with engine.begin() as conn:
            for rec in chunk:
                conn.execute(sql, rec)


def build_rolling(engine, *, as_of_month: date, windows: list[int], addr1_filter: str | None, batch_id: str) -> int:
    total = 0
    with engine.connect() as conn:
        addr1_list = [addr1_filter] if addr1_filter else _distinct_addr1(conn)
    for window_years in windows:
        ps, pe = period_bounds_for_window(as_of_month, window_years)
        log.info("window=%sy period=%s..%s", window_years, ps, pe)
        for addr1 in tqdm(addr1_list, desc=f"w{window_years}"):
            addr1_clause = "AND t.addr1 = :addr1" if addr1 else ""
            sql = ROLLING_SQL.format(addr1_clause=addr1_clause)
            params = {"p_start": ps, "p_end": pe}
            if addr1:
                params["addr1"] = addr1
            with engine.connect() as conn:
                rows = conn.execute(text(sql), params).mappings().all()
            records = [
                rec
                for row in rows
                if (rec := _record_from_row(
                    row,
                    as_of_month=as_of_month,
                    window_years=window_years,
                    period_start=ps,
                    period_end=pe,
                    batch_id=batch_id,
                ))
            ]
            upsert_cluster_stats(records, engine)
            total += len(records)
            del rows, records
            gc.collect()
    return total


def build_annual(engine, *, addr1_filter: str | None, batch_id: str) -> int:
    total = 0
    with engine.connect() as conn:
        addr1_list = [addr1_filter] if addr1_filter else _distinct_addr1(conn)
    for addr1 in tqdm(addr1_list, desc="annual"):
        addr1_clause = "AND t.addr1 = :addr1" if addr1 else ""
        sql = ANNUAL_SQL.format(addr1_clause=addr1_clause)
        params = {"addr1": addr1} if addr1 else {}
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
                    "cluster_key": row["cluster_key"],
                    "asset_type": row["asset_type"],
                    "contract_year": int(row["contract_year"]),
                    "display_label": row["display_label"] or "",
                    "addr1": row.get("addr1"),
                    "addr2": row.get("addr2"),
                    "addr3": row.get("addr3"),
                    "addr4": row.get("addr4"),
                    "road_name": row.get("road_name"),
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
    p = argparse.ArgumentParser(description="집합상가·공장 cluster_stats / cluster_annual_stats")
    p.add_argument("--as-of", type=str, default=None)
    p.add_argument("--windows", type=str, default="3,5")
    p.add_argument("--addr1", type=str, default=None)
    p.add_argument("--skip-annual", action="store_true")
    p.add_argument("--rolling-only", action="store_true")
    args = p.parse_args()

    as_of = parse_as_of_month(args.as_of) if args.as_of else default_as_of_month()
    windows = sorted({int(x.strip()) for x in args.windows.split(",") if x.strip()})
    engine = get_collective_engine()
    batch_id = str(uuid.uuid4())

    with engine.connect() as conn:
        tx_n = conn.execute(text("SELECT COUNT(*) FROM collective_commercial_transactions")).scalar()
    log.info("commercial_transactions rows=%s as_of=%s windows=%s", tx_n, as_of, windows)
    if not tx_n:
        raise SystemExit("collective_commercial_transactions empty")

    rolling_n = build_rolling(engine, as_of_month=as_of, windows=windows, addr1_filter=args.addr1, batch_id=batch_id)
    log.info("collective_commercial_cluster_stats upserted ~%s rows", rolling_n)
    if not args.rolling_only and not args.skip_annual:
        annual_n = build_annual(engine, addr1_filter=args.addr1, batch_id=batch_id)
        log.info("collective_commercial_cluster_annual_stats upserted ~%s rows", annual_n)


if __name__ == "__main__":
    main()
