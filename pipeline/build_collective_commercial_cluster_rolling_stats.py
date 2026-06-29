#!/usr/bin/env python3
"""collective_commercial_transactions → collective_commercial_cluster_rolling_stats."""

from __future__ import annotations

import argparse
import gc
import logging
import sys
import uuid
import warnings
from datetime import date, timedelta
from pathlib import Path

from sqlalchemy import text
from tqdm import tqdm

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "pipeline"))

from build_stats_v2 import (  # noqa: E402
    _anchor_n_calendar_years_before,
    default_as_of_month,
    parse_as_of_month,
    period_bounds_for_window,
)
from collective.db_utils import get_collective_engine  # noqa: E402
from stats import compute_stats  # noqa: E402

warnings.filterwarnings("ignore", category=RuntimeWarning, module="scipy")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", stream=sys.stdout)
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
  AND t.contract_date IS NOT NULL
  AND t.contract_date >= :p_start
  AND t.contract_date <= :p_end
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


def iter_rolling_year_buckets_old_first(period_end: date, bucket_count: int) -> list[tuple[date, date, int]]:
    if bucket_count < 1:
        return []
    ends: list[date] = []
    cur = period_end
    ends.append(cur)
    for _ in range(1, bucket_count):
        cur = _anchor_n_calendar_years_before(cur, 1)
        ends.append(cur)
    ends.reverse()
    out: list[tuple[date, date, int]] = []
    for i, bucket_end in enumerate(ends):
        pb = _anchor_n_calendar_years_before(bucket_end, 1)
        ps = pb + timedelta(days=1)
        out.append((ps, bucket_end, i + 1))
    return out


def upsert_rolling(records: list[dict], engine, *, chunk_size: int = 400) -> None:
    if not records:
        return
    sql = text(
        """
        INSERT INTO collective_commercial_cluster_rolling_stats (
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
                addr1_clause = "AND t.addr1 = :addr1" if addr1 else ""
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
            upsert_rolling(records, engine)
            total += len(records)
            del records
            gc.collect()
    return total


def main() -> None:
    p = argparse.ArgumentParser(description="집합상가·공장 cluster_rolling_stats")
    p.add_argument("--as-of", type=str, default=None)
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
    log.info("collective_commercial_cluster_rolling_stats upserted ~%s rows", n)


if __name__ == "__main__":
    main()
