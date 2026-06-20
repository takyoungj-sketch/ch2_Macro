#!/usr/bin/env python3
"""collective_commercial_transactions → collective_cluster_stats (3·5y rolling)."""

from __future__ import annotations

import argparse
import logging
import sys
import uuid
from datetime import date
from pathlib import Path

from sqlalchemy import text
from tqdm import tqdm

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "pipeline"))

from build_stats_v2 import default_as_of_month, parse_as_of_month, period_bounds_for_window  # noqa: E402
from collective.db_utils import get_collective_engine  # noqa: E402
from stats import compute_stats  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

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
    MAX(c.confidence_tier) AS confidence_tier,
    array_agg(t.unit_price ORDER BY t.unit_price) AS prices
FROM collective_commercial_transactions t
JOIN commercial_clusters c ON c.id = t.cluster_id
WHERE t.is_valid = true
  AND t.unit_price IS NOT NULL
  AND t.unit_price > 0
  AND t.contract_year IS NOT NULL
  AND COALESCE(
        t.contract_date,
        make_date(t.contract_year::int, COALESCE(t.contract_month, 6)::int, 1)
      ) >= :p_start
  AND COALESCE(
        t.contract_date,
        make_date(t.contract_year::int, COALESCE(t.contract_month, 6)::int, 1)
      ) <= :p_end
  {addr1_clause}
GROUP BY t.cluster_key, t.asset_type
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


def _record(row, *, as_of_month: date, window_years: int, period_start: date, period_end: date, batch_id: str):
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
        "building_year": int(by) if by is not None else None,
        "area_bucket_label": row.get("area_bucket_label"),
        "confidence_tier": row.get("confidence_tier"),
        "count": st["count"],
        "mean": st["mean"],
        "std": st["std"],
        "ci_lower": st["ci_lower"],
        "ci_upper": st["ci_upper"],
        "median": st["median"],
        "batch_id": batch_id,
    }


def upsert(records: list[dict], engine) -> None:
    if not records:
        return
    sql = text(
        """
        INSERT INTO collective_cluster_stats (
            as_of_month, window_years, period_start, period_end,
            cluster_key, asset_type, display_label,
            addr1, addr2, addr3, addr4, road_name, zone_type, building_use,
            building_year, area_bucket_label, confidence_tier,
            count, mean, std, ci_lower, ci_upper, median,
            computed_at, batch_id
        ) VALUES (
            :as_of_month, :window_years, :period_start, :period_end,
            :cluster_key, :asset_type, :display_label,
            :addr1, :addr2, :addr3, :addr4, :road_name, :zone_type, :building_use,
            :building_year, :area_bucket_label, :confidence_tier,
            :count, :mean, :std, :ci_lower, :ci_upper, :median,
            NOW(), :batch_id
        )
        ON CONFLICT (as_of_month, window_years, cluster_key, asset_type)
        DO UPDATE SET
            period_start = EXCLUDED.period_start,
            period_end = EXCLUDED.period_end,
            display_label = EXCLUDED.display_label,
            addr1 = EXCLUDED.addr1, addr2 = EXCLUDED.addr2, addr3 = EXCLUDED.addr3, addr4 = EXCLUDED.addr4,
            road_name = EXCLUDED.road_name, zone_type = EXCLUDED.zone_type, building_use = EXCLUDED.building_use,
            building_year = EXCLUDED.building_year, area_bucket_label = EXCLUDED.area_bucket_label,
            confidence_tier = EXCLUDED.confidence_tier,
            count = EXCLUDED.count, mean = EXCLUDED.mean, std = EXCLUDED.std,
            ci_lower = EXCLUDED.ci_lower, ci_upper = EXCLUDED.ci_upper, median = EXCLUDED.median,
            computed_at = NOW(), batch_id = EXCLUDED.batch_id
        """
    )
    with engine.begin() as conn:
        for rec in records:
            conn.execute(sql, rec)


def build(engine, *, as_of_month: date, windows: list[int]) -> None:
    batch_id = str(uuid.uuid4())
    addr1_list = _distinct_addr1(engine.connect())
    for window_years in windows:
        period_start, period_end = period_bounds_for_window(as_of_month, window_years)
        log.info("cluster_stats window=%sy %s..%s", window_years, period_start, period_end)
        all_recs: list[dict] = []
        chunks = [None] + addr1_list if addr1_list else [None]
        for addr1 in tqdm(chunks, desc=f"cluster_stats w{window_years}"):
            clause = "AND t.addr1 = :addr1" if addr1 else ""
            params = {"p_start": period_start, "p_end": period_end}
            if addr1:
                params["addr1"] = addr1
            with engine.connect() as conn:
                rows = conn.execute(text(ROLLING_SQL.format(addr1_clause=clause)), params).mappings().all()
            for row in rows:
                rec = _record(
                    row,
                    as_of_month=as_of_month,
                    window_years=window_years,
                    period_start=period_start,
                    period_end=period_end,
                    batch_id=batch_id,
                )
                if rec:
                    all_recs.append(rec)
            if len(all_recs) >= 800:
                upsert(all_recs, engine)
                all_recs.clear()
        upsert(all_recs, engine)
        log.info("cluster_stats w=%s rows upserted (batch=%s)", window_years, batch_id[:8])


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--as-of", default=default_as_of_month())
    p.add_argument("--windows", default="3,5")
    args = p.parse_args()
    as_of = parse_as_of_month(args.as_of)
    windows = [int(x.strip()) for x in args.windows.split(",") if x.strip()]
    engine = get_collective_engine()
    ddl = REPO / "db" / "030_collective_cluster_stats.sql"
    if ddl.is_file():
        with engine.begin() as conn:
            conn.execute(text(ddl.read_text(encoding="utf-8")))
    build(engine, as_of_month=as_of, windows=windows)


if __name__ == "__main__":
    main()
