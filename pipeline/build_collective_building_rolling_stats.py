#!/usr/bin/env python3
"""
collective_transactions → collective_building_rolling_stats (12개월 버킷).

모달 기본 추세 — 토지 matrix_rolling_buckets 와 동일 버킷 정의.
"""

from __future__ import annotations

import argparse
import gc
import logging
import sys
import uuid
import warnings
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
from sqlalchemy import text
from tqdm import tqdm

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "pipeline"))

from build_stats_v2 import (  # noqa: E402
    default_as_of_month,
    last_day_of_month,
    parse_as_of_month,
    period_bounds_for_window,
    _anchor_n_calendar_years_before,
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

BUCKET_SQL = """
SELECT
    building_key,
    asset_type,
    MAX(display_name) AS display_name,
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


def _bucket_range_closed_ending(bucket_end: date) -> tuple[date, date]:
    pb = _anchor_n_calendar_years_before(bucket_end, 1)
    start = pb + timedelta(days=1)
    return start, bucket_end


def iter_rolling_year_buckets_old_first(period_end: date, bucket_count: int) -> list[tuple[date, date, int]]:
    """과거→최근, bucket_index 1..N."""
    if bucket_count < 1:
        return []
    ends: list[date] = []
    cur = period_end
    ends.append(cur)
    for _ in range(1, bucket_count):
        cur = _anchor_n_calendar_years_before(cur, 1)
        ends.append(cur)
    ends.reverse()
    return [
        (*_bucket_range_closed_ending(e), idx + 1)
        for idx, e in enumerate(ends)
    ]


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


def upsert_rolling(records: list[dict], engine, *, chunk_size: int = 400) -> None:
    if not records:
        return
    sql = text(
        """
        INSERT INTO collective_building_rolling_stats (
            as_of_month, window_years, bucket_index, period_start, period_end,
            building_key, asset_type, display_name,
            count, mean, std, ci_lower, ci_upper, median,
            computed_at, batch_id
        ) VALUES (
            :as_of_month, :window_years, :bucket_index, :period_start, :period_end,
            :building_key, :asset_type, :display_name,
            :count, :mean, :std, :ci_lower, :ci_upper, :median,
            NOW(), :batch_id
        )
        ON CONFLICT (as_of_month, window_years, bucket_index, building_key, asset_type)
        DO UPDATE SET
            period_start = EXCLUDED.period_start,
            period_end = EXCLUDED.period_end,
            display_name = EXCLUDED.display_name,
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


def build_rolling_buckets(
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
        _, period_end = period_bounds_for_window(as_of_month, window_years)
        buckets = iter_rolling_year_buckets_old_first(period_end, window_years)
        log.info("window=%sy buckets=%s end=%s", window_years, len(buckets), period_end)
        for addr1 in tqdm(addr1_list, desc=f"roll-w{window_years}"):
            records: list[dict] = []
            for ps, pe, bidx in buckets:
                addr1_clause = "AND addr1 = :addr1" if addr1 else ""
                sql = BUCKET_SQL.format(addr1_clause=addr1_clause)
                params = {"p_start": ps, "p_end": pe}
                if addr1:
                    params["addr1"] = addr1
                with engine.connect() as conn:
                    rows = conn.execute(text(sql), params).mappings().all()
                for row in rows:
                    prices = [float(x) for x in (row["prices"] or []) if x is not None]
                    if not prices:
                        continue
                    st = compute_stats(prices)
                    if st["count"] <= 0:
                        continue
                    records.append(
                        {
                            "as_of_month": as_of_month,
                            "window_years": window_years,
                            "bucket_index": bidx,
                            "period_start": ps,
                            "period_end": pe,
                            "building_key": row["building_key"],
                            "asset_type": row["asset_type"],
                            "display_name": row["display_name"] or "",
                            "count": st["count"],
                            "mean": st["mean"],
                            "std": st["std"],
                            "ci_lower": st["ci_lower"],
                            "ci_upper": st["ci_upper"],
                            "median": st["median"],
                            "batch_id": batch_id,
                        }
                    )
            upsert_rolling(records, engine)
            total += len(records)
            del records
            gc.collect()
    return total


def main() -> None:
    p = argparse.ArgumentParser(description="집합 building_rolling_stats (12개월 버킷)")
    p.add_argument("--as-of", type=str, default="2026-05-01")
    p.add_argument("--windows", type=str, default="3,5")
    p.add_argument("--addr1", type=str, default=None)
    args = p.parse_args()

    as_of = parse_as_of_month(args.as_of) if args.as_of else default_as_of_month()
    windows = sorted({int(x.strip()) for x in args.windows.split(",") if x.strip()})

    engine = get_collective_engine()
    batch_id = str(uuid.uuid4())
    n = build_rolling_buckets(
        engine,
        as_of_month=as_of,
        windows=windows,
        addr1_filter=args.addr1,
        batch_id=batch_id,
    )
    log.info("collective_building_rolling_stats upserted ~%s rows", n)


if __name__ == "__main__":
    main()
