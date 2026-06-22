#!/usr/bin/env python3
"""built_transactions → built_scope_stats (as_of_month × window_years × 시도·시군구)."""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date
from pathlib import Path

from sqlalchemy import text

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "pipeline"))

from build_stats_v2 import default_as_of_month, parse_as_of_month, period_bounds_for_window  # noqa: E402
from built.db_utils import get_built_engine  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

DDL_029 = REPO / "db" / "029_built_scope_stats.sql"

ASSET_TYPES = ("commercial", "factory", "detached", "all")
DEFAULT_WINDOWS = (3, 5)

UPSERT_SQL = text(
    """
    INSERT INTO built_scope_stats (
        asset_type, addr1, addr2, as_of_month, window_years,
        tx_count, median_price, mean_price, updated_at
    ) VALUES (
        :asset_type, :addr1, :addr2, :as_of_month, :window_years,
        :tx_count, :median_price, :mean_price, NOW()
    )
    ON CONFLICT (asset_type, addr1, addr2, as_of_month, window_years)
    DO UPDATE SET
        tx_count = EXCLUDED.tx_count,
        median_price = EXCLUDED.median_price,
        mean_price = EXCLUDED.mean_price,
        updated_at = NOW()
    """
)

AGG_SQL_TEMPLATE = """
    SELECT
        addr1,
        COALESCE(addr2, '') AS addr2,
        COUNT(*)::bigint AS tx_count,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY price) AS median_price,
        AVG(price)::numeric(14,2) AS mean_price
    FROM built_transactions
    WHERE is_valid = true
      AND price IS NOT NULL AND price > 0
      AND contract_date >= :p_start
      AND contract_date <= :p_end
      {asset_clause}
    GROUP BY addr1, COALESCE(addr2, '')
"""


def ensure_schema(engine) -> None:
    if DDL_029.is_file():
        with engine.begin() as conn:
            conn.execute(text(DDL_029.read_text(encoding="utf-8")))
        log.info("schema ready (%s)", DDL_029.name)


def _resolve_as_of(conn, as_of: str | None) -> date:
    if as_of:
        return parse_as_of_month(as_of)
    row = conn.execute(
        text(
            """
            SELECT MAX(contract_date) AS max_d FROM built_transactions
            WHERE is_valid = true AND contract_date IS NOT NULL
            """
        )
    ).one()
    if row.max_d:
        d = row.max_d if isinstance(row.max_d, date) else row.max_d.date()
        return date(d.year, d.month, 1)
    return default_as_of_month()


def build_for_window(
    conn,
    *,
    as_of_month: date,
    window_years: int,
) -> int:
    p_start, p_end = period_bounds_for_window(as_of_month, window_years)
    n = 0
    for asset in ASSET_TYPES:
        asset_clause = ""
        params: dict = {"p_start": p_start, "p_end": p_end}
        if asset != "all":
            asset_clause = "AND asset_type = :asset_type"
            params["asset_type"] = asset
        sql = AGG_SQL_TEMPLATE.format(asset_clause=asset_clause)
        rows = conn.execute(text(sql), params).mappings().all()
        for row in rows:
            conn.execute(
                UPSERT_SQL,
                {
                    "asset_type": asset,
                    "addr1": row["addr1"],
                    "addr2": row["addr2"] or "",
                    "as_of_month": as_of_month,
                    "window_years": window_years,
                    "tx_count": int(row["tx_count"] or 0),
                    "median_price": row["median_price"],
                    "mean_price": row["mean_price"],
                },
            )
            n += 1
    return n


def main() -> None:
    p = argparse.ArgumentParser(description="built_scope_stats mart 구축")
    p.add_argument("--as-of", help="YYYY-MM (기본: 원장 MAX contract_date 월)")
    p.add_argument("--windows", default="3,5", help="쉼표 구분 window_years (기본 3,5)")
    args = p.parse_args()

    windows = [int(w.strip()) for w in args.windows.split(",") if w.strip()]
    engine = get_built_engine()
    ensure_schema(engine)

    with engine.begin() as conn:
        as_of = _resolve_as_of(conn, args.as_of)
        total = 0
        for wy in windows:
            cnt = build_for_window(conn, as_of_month=as_of, window_years=wy)
            log.info("built_scope_stats as_of=%s window=%sy rows=%s", as_of.strftime("%Y-%m"), wy, cnt)
            total += cnt
    log.info("built_scope_stats upserted %s rows", total)


if __name__ == "__main__":
    main()
