#!/usr/bin/env python3
"""collective_commercial_transactions → collective_cluster_rolling_stats (12-month buckets)."""

from __future__ import annotations

import argparse
import logging
import sys
import uuid
from datetime import date, timedelta
from pathlib import Path

from sqlalchemy import text
from tqdm import tqdm

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "pipeline"))

from build_stats_v2 import (  # noqa: E402
    _anchor_n_calendar_years_before,
    default_as_of_month,
    last_day_of_month,
    parse_as_of_month,
    period_bounds_for_window,
)
from collective.db_utils import get_collective_engine  # noqa: E402
from stats import compute_stats  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

BUCKET_SQL = """
SELECT
    t.cluster_key,
    t.asset_type,
    MAX(c.display_label) AS display_label,
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


def _bucket_range_closed_ending(bucket_end: date) -> tuple[date, date]:
    pb = _anchor_n_calendar_years_before(bucket_end, 1)
    return pb + timedelta(days=1), bucket_end


def iter_buckets(period_end: date, bucket_count: int) -> list[tuple[date, date, int]]:
    if bucket_count < 1:
        return []
    ends: list[date] = []
    cur = period_end
    ends.append(cur)
    for _ in range(1, bucket_count):
        cur = _anchor_n_calendar_years_before(cur, 1)
        ends.append(cur)
    ends.reverse()
    return [(*_bucket_range_closed_ending(e), idx + 1) for idx, e in enumerate(ends)]


def _distinct_addr1(conn) -> list[str]:
    rows = conn.execute(
        text(
            """
            SELECT DISTINCT addr1 AS a FROM collective_commercial_transactions
            WHERE addr1 IS NOT NULL AND btrim(addr1::text) <> '' ORDER BY 1
            """
        )
    ).fetchall()
    return [str(r.a) for r in rows]


def upsert(records: list[dict], engine) -> None:
    if not records:
        return
    sql = text(
        """
        INSERT INTO collective_cluster_rolling_stats (
            as_of_month, window_years, bucket_index, period_start, period_end,
            cluster_key, asset_type, display_label,
            count, mean, std, ci_lower, ci_upper, median,
            computed_at, batch_id
        ) VALUES (
            :as_of_month, :window_years, :bucket_index, :period_start, :period_end,
            :cluster_key, :asset_type, :display_label,
            :count, :mean, :std, :ci_lower, :ci_upper, :median,
            NOW(), :batch_id
        )
        ON CONFLICT (as_of_month, window_years, bucket_index, cluster_key, asset_type)
        DO UPDATE SET
            period_start = EXCLUDED.period_start, period_end = EXCLUDED.period_end,
            display_label = EXCLUDED.display_label,
            count = EXCLUDED.count, mean = EXCLUDED.mean, std = EXCLUDED.std,
            ci_lower = EXCLUDED.ci_lower, ci_upper = EXCLUDED.ci_upper, median = EXCLUDED.median,
            computed_at = NOW(), batch_id = EXCLUDED.batch_id
        """
    )
    with engine.begin() as conn:
        for rec in records:
            conn.execute(sql, rec)


def build(engine, *, as_of_month: date, window_years: int, bucket_count: int | None = None) -> None:
    _, period_end = period_bounds_for_window(as_of_month, window_years)
    n_buckets = window_years if bucket_count is None else bucket_count
    batch_id = str(uuid.uuid4())
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                DELETE FROM collective_cluster_rolling_stats
                WHERE as_of_month = :as_of AND window_years = :w
                  AND bucket_index > :n_buckets
                """
            ),
            {"as_of": as_of_month, "w": window_years, "n_buckets": n_buckets},
        )
    addr1_list = _distinct_addr1(engine.connect())
    buckets = iter_buckets(period_end, n_buckets)
    for p_start, p_end, bidx in buckets:
        log.info("cluster_rolling bucket %s %s..%s", bidx, p_start, p_end)
        batch: list[dict] = []
        chunks = [None] + addr1_list if addr1_list else [None]
        for addr1 in tqdm(chunks, desc=f"rolling b{bidx}"):
            clause = "AND t.addr1 = :addr1" if addr1 else ""
            params = {"p_start": p_start, "p_end": p_end}
            if addr1:
                params["addr1"] = addr1
            with engine.connect() as conn:
                rows = conn.execute(text(BUCKET_SQL.format(addr1_clause=clause)), params).mappings().all()
            for row in rows:
                prices = [float(x) for x in (row["prices"] or []) if x is not None]
                if not prices:
                    continue
                st = compute_stats(prices)
                if st["count"] <= 0:
                    continue
                batch.append(
                    {
                        "as_of_month": as_of_month,
                        "window_years": window_years,
                        "bucket_index": bidx,
                        "period_start": p_start,
                        "period_end": p_end,
                        "cluster_key": row["cluster_key"],
                        "asset_type": row["asset_type"],
                        "display_label": row["display_label"] or "",
                        "count": st["count"],
                        "mean": st["mean"],
                        "std": st["std"],
                        "ci_lower": st["ci_lower"],
                        "ci_upper": st["ci_upper"],
                        "median": st["median"],
                        "batch_id": batch_id,
                    }
                )
                if len(batch) >= 800:
                    upsert(batch, engine)
                    batch.clear()
        upsert(batch, engine)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--as-of", default=default_as_of_month())
    p.add_argument("--windows", default="3,5")
    p.add_argument("--buckets", type=int, default=None, help="기본: window_years와 동일 (주거 building_rolling 패턴)")
    args = p.parse_args()
    as_of = parse_as_of_month(args.as_of)
    windows = [int(x.strip()) for x in args.windows.split(",") if x.strip()]
    engine = get_collective_engine()
    ddl = REPO / "db" / "030_collective_cluster_stats.sql"
    if ddl.is_file():
        with engine.begin() as conn:
            conn.execute(text(ddl.read_text(encoding="utf-8")))
    for w in windows:
        build(engine, as_of_month=as_of, window_years=w, bucket_count=args.buckets)
    log.info("cluster rolling stats complete")


if __name__ == "__main__":
    main()
