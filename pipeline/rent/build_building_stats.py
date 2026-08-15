#!/usr/bin/env python3
"""rent_transactions → rent_building_stats + rent_building_rolling_stats."""

from __future__ import annotations

import argparse
import logging
import sys
import uuid
import warnings
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
from psycopg2.extras import execute_values
from sqlalchemy import text
from tqdm import tqdm

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "pipeline"))

from build_stats_v2 import (  # noqa: E402
    default_as_of_month,
    parse_as_of_month,
    period_bounds_for_window,
    _anchor_n_calendar_years_before,
)
from rent.db_utils import get_rent_engine  # noqa: E402
from rent.stats_pack import (  # noqa: E402
    ASSET_TYPES,
    BUILDING_KEY_SQL,
    has_any_lease,
    pack_building_lease_stats,
)

warnings.filterwarnings("ignore", category=RuntimeWarning, module="scipy")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

DDL = REPO / "db" / "056_rent_building_stats.sql"

STAT_COLS = (
    "jeonse_n",
    "jeonse_mean",
    "jeonse_median",
    "jeonse_ci_lower",
    "jeonse_ci_upper",
    "mixed_n",
    "mixed_deposit_mean",
    "mixed_deposit_median",
    "mixed_deposit_ci_lower",
    "mixed_deposit_ci_upper",
    "mixed_monthly_mean",
    "mixed_monthly_median",
    "mixed_monthly_ci_lower",
    "mixed_monthly_ci_upper",
    "monthly_n",
    "monthly_mean",
    "monthly_median",
    "monthly_ci_lower",
    "monthly_ci_upper",
)

LIST_COLS = (
    "as_of_month",
    "window_years",
    "period_start",
    "period_end",
    "building_key",
    "asset_type",
    "display_name",
    "addr1",
    "addr2",
    "addr3",
    "addr4",
    "addr5",
    "beopjungri_code",
    "sigungu_code",
    "lot_number",
    "road_name",
    "building_year",
) + STAT_COLS + ("batch_id",)

ROLL_COLS = (
    "as_of_month",
    "window_years",
    "bucket_index",
    "period_start",
    "period_end",
    "building_key",
    "asset_type",
    "display_name",
) + STAT_COLS + ("batch_id",)

GROUP_SQL = f"""
SELECT
    {BUILDING_KEY_SQL} AS building_key,
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
    array_agg(deposit_per_m2) FILTER (
        WHERE COALESCE(monthly_rent_manwon, 0) = 0 AND deposit_per_m2 IS NOT NULL
    ) AS jeonse_deposit,
    array_agg(deposit_per_m2) FILTER (
        WHERE COALESCE(deposit_manwon, 0) > 0
          AND COALESCE(monthly_rent_manwon, 0) > 0
          AND deposit_per_m2 IS NOT NULL
    ) AS mixed_deposit,
    array_agg(monthly_per_m2) FILTER (
        WHERE COALESCE(deposit_manwon, 0) > 0
          AND COALESCE(monthly_rent_manwon, 0) > 0
          AND monthly_per_m2 IS NOT NULL
    ) AS mixed_monthly,
    array_agg(monthly_per_m2) FILTER (
        WHERE COALESCE(deposit_manwon, 0) = 0
          AND COALESCE(monthly_rent_manwon, 0) > 0
          AND monthly_per_m2 IS NOT NULL
    ) AS monthly_rent
FROM rent_transactions
WHERE is_valid = true
  AND contract_date IS NOT NULL
  AND contract_date >= :p_start
  AND contract_date <= :p_end
  {{addr1_clause}}
  {{asset_clause}}
GROUP BY 1, asset_type
"""


def _bucket_range_closed_ending(bucket_end: date) -> tuple[date, date]:
    pb = _anchor_n_calendar_years_before(bucket_end, 1)
    return pb + timedelta(days=1), bucket_end


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
    for i, end in enumerate(ends, start=1):
        start, _ = _bucket_range_closed_ending(end)
        out.append((start, end, i))
    return out


def _int_or_none(val):
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


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


def _apply_ddl(engine) -> None:
    sql = DDL.read_text(encoding="utf-8")
    with engine.begin() as conn:
        conn.execute(text(sql))
    log.info("applied %s", DDL.name)


def _row_identity(row) -> dict:
    return {
        "building_key": str(row["building_key"]),
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
        "building_year": _int_or_none(row.get("building_year")),
    }


def _fetch_groups(engine, *, p_start: date, p_end: date, addr1: str | None, asset_type: str | None):
    addr1_clause = "AND addr1 = :addr1" if addr1 else ""
    asset_clause = "AND asset_type = :asset_type" if asset_type else ""
    sql = GROUP_SQL.format(addr1_clause=addr1_clause, asset_clause=asset_clause)
    params: dict = {"p_start": p_start, "p_end": p_end}
    if addr1:
        params["addr1"] = addr1
    if asset_type:
        params["asset_type"] = asset_type
    with engine.connect() as conn:
        return conn.execute(text(sql), params).mappings().all()


def _list_records(rows, *, as_of_month, window_years, period_start, period_end, batch_id) -> list[dict]:
    out: list[dict] = []
    for row in rows:
        stats = pack_building_lease_stats(row)
        if not has_any_lease(stats):
            continue
        rec = {
            "as_of_month": as_of_month,
            "window_years": window_years,
            "period_start": period_start,
            "period_end": period_end,
            "batch_id": batch_id,
            **_row_identity(row),
            **stats,
        }
        out.append(rec)
    return out


def _roll_records(rows, *, as_of_month, window_years, bucket_index, period_start, period_end, batch_id) -> list[dict]:
    out: list[dict] = []
    for row in rows:
        stats = pack_building_lease_stats(row)
        if not has_any_lease(stats):
            continue
        out.append(
            {
                "as_of_month": as_of_month,
                "window_years": window_years,
                "bucket_index": bucket_index,
                "period_start": period_start,
                "period_end": period_end,
                "building_key": str(row["building_key"]),
                "asset_type": row["asset_type"],
                "display_name": row["display_name"] or "",
                "batch_id": batch_id,
                **stats,
            }
        )
    return out


def _upsert(engine, table: str, cols: tuple[str, ...], conflict: str, records: list[dict], updates: tuple[str, ...]) -> None:
    if not records:
        return
    placeholders = "(" + ",".join(["%s"] * len(cols)) + ")"
    set_sql = ", ".join(f"{c} = EXCLUDED.{c}" for c in updates)
    sql = f"""
        INSERT INTO {table} ({", ".join(cols)})
        VALUES %s
        ON CONFLICT ({conflict})
        DO UPDATE SET {set_sql}, computed_at = NOW()
    """
    tuples = [tuple(rec.get(c) for c in cols) for rec in records]
    raw = engine.raw_connection()
    try:
        cur = raw.cursor()
        execute_values(cur, sql, tuples, template=placeholders, page_size=800)
        raw.commit()
        cur.close()
    finally:
        raw.close()


def upsert_list(engine, records: list[dict]) -> None:
    updates = tuple(c for c in LIST_COLS if c not in ("as_of_month", "window_years", "building_key", "asset_type"))
    _upsert(
        engine,
        "rent_building_stats",
        LIST_COLS,
        "as_of_month, window_years, building_key, asset_type",
        records,
        updates,
    )


def upsert_roll(engine, records: list[dict]) -> None:
    updates = tuple(
        c
        for c in ROLL_COLS
        if c not in ("as_of_month", "window_years", "bucket_index", "building_key", "asset_type")
    )
    _upsert(
        engine,
        "rent_building_rolling_stats",
        ROLL_COLS,
        "as_of_month, window_years, bucket_index, building_key, asset_type",
        records,
        updates,
    )


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--as-of", default=None)
    p.add_argument("--windows", default="3,5,7")
    p.add_argument("--addr1", default=None)
    p.add_argument("--asset-type", default=None, choices=ASSET_TYPES)
    p.add_argument("--skip-rolling", action="store_true")
    args = p.parse_args()

    as_of = parse_as_of_month(args.as_of) if args.as_of else default_as_of_month()
    windows = [int(x.strip()) for x in args.windows.split(",") if x.strip()]
    engine = get_rent_engine()
    _apply_ddl(engine)
    batch_id = uuid.uuid4().hex[:12]
    log.info("as_of=%s windows=%s batch=%s", as_of, windows, batch_id)

    with engine.connect() as conn:
        addr1_list = [args.addr1] if args.addr1 else _distinct_addr1(conn)

    for window_years in windows:
        ps, pe = period_bounds_for_window(as_of, window_years)
        log.info("list window=%sy %s..%s", window_years, ps, pe)
        n = 0
        for addr1 in tqdm(addr1_list, desc=f"list w{window_years}"):
            rows = _fetch_groups(
                engine, p_start=ps, p_end=pe, addr1=addr1, asset_type=args.asset_type
            )
            recs = _list_records(
                rows,
                as_of_month=as_of,
                window_years=window_years,
                period_start=ps,
                period_end=pe,
                batch_id=batch_id,
            )
            upsert_list(engine, recs)
            n += len(recs)
        log.info("list window=%s rows=%s", window_years, n)

        if args.skip_rolling:
            continue
        buckets = iter_rolling_year_buckets_old_first(pe, window_years)
        for b_start, b_end, b_idx in buckets:
            log.info("roll w%s bucket=%s %s..%s", window_years, b_idx, b_start, b_end)
            rn = 0
            for addr1 in tqdm(addr1_list, desc=f"roll w{window_years}b{b_idx}"):
                rows = _fetch_groups(
                    engine,
                    p_start=b_start,
                    p_end=b_end,
                    addr1=addr1,
                    asset_type=args.asset_type,
                )
                recs = _roll_records(
                    rows,
                    as_of_month=as_of,
                    window_years=window_years,
                    bucket_index=b_idx,
                    period_start=b_start,
                    period_end=b_end,
                    batch_id=batch_id,
                )
                upsert_roll(engine, recs)
                rn += len(recs)
            log.info("roll w%s b%s rows=%s", window_years, b_idx, rn)

    log.info("done batch=%s", batch_id)


if __name__ == "__main__":
    main()
