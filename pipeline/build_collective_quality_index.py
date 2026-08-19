#!/usr/bin/env python3
"""
집합(주거) 1단계 단지 품질지수 mart.

설계: docs/COLLECTIVE_TWO_STAGE_HEDONIC_DESIGN.md §2 · §5
  py pipeline/build_collective_quality_index.py --as-of 2026-07-01 --windows 5 --replace
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date
from pathlib import Path

import pandas as pd
from sqlalchemy import text

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend"))
sys.path.insert(0, str(REPO / "pipeline"))

from build_stats_v2 import default_as_of_month, parse_as_of_month  # noqa: E402
from collective.db_utils import get_collective_engine  # noqa: E402
from app.collective.hedonic.constants import DEFAULT_ASSET_TYPE  # noqa: E402
from app.collective.hedonic.stage1 import build_stage1_from_transactions  # noqa: E402
from app.v2_stats_windows import period_bounds_for_window  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

TX_SQL = """
SELECT building_key, sigungu_code, unit_price, exclusive_area, floor,
       contract_year, contract_date
FROM collective_transactions
WHERE is_valid = true
  AND asset_type = :asset_type
  AND unit_price IS NOT NULL AND unit_price > 0
  AND exclusive_area IS NOT NULL AND exclusive_area > 0
  AND contract_date >= :p_start AND contract_date <= :p_end
  AND sigungu_code IS NOT NULL
"""


def delete_snapshot(engine, as_of: date, window_years: int, asset_type: str) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                DELETE FROM collective_building_quality_index
                WHERE as_of_month = :as_of AND window_years = :wy AND asset_type = :at
                """
            ),
            {"as_of": as_of, "wy": window_years, "at": asset_type},
        )
        conn.execute(
            text(
                """
                DELETE FROM collective_sigungu_base_level
                WHERE as_of_month = :as_of AND window_years = :wy AND asset_type = :at
                """
            ),
            {"as_of": as_of, "wy": window_years, "at": asset_type},
        )


def upsert_rows(engine, table: str, rows: list[dict], chunk: int = 500) -> None:
    if not rows:
        return
    cols = list(rows[0].keys())
    placeholders = ", ".join(f":{c}" for c in cols)
    col_list = ", ".join(cols)
    sql = text(f"INSERT INTO {table} ({col_list}) VALUES ({placeholders})")
    with engine.begin() as conn:
        for i in range(0, len(rows), chunk):
            batch = rows[i : i + chunk]
            conn.execute(sql, batch)


def main() -> None:
    p = argparse.ArgumentParser(description="집합 1단계 품질지수 mart")
    p.add_argument("--as-of", dest="as_of", default=None)
    p.add_argument("--windows", default="5", help="쉼표 구분 window_years")
    p.add_argument("--asset-type", default=DEFAULT_ASSET_TYPE)
    p.add_argument("--replace", action="store_true")
    args = p.parse_args()

    as_of = parse_as_of_month(args.as_of) if args.as_of else default_as_of_month()
    windows = [int(x.strip()) for x in args.windows.split(",") if x.strip()]
    engine = get_collective_engine()

    for wy in windows:
        p_start, p_end = period_bounds_for_window(as_of, wy)
        log.info("window=%sy  %s .. %s", wy, p_start, p_end)
        tx = pd.read_sql(
            text(TX_SQL),
            engine,
            params={"asset_type": args.asset_type, "p_start": p_start, "p_end": p_end},
        )
        log.info("transactions loaded: %s", len(tx))
        result = build_stage1_from_transactions(
            tx,
            as_of_month=as_of,
            window_years=wy,
            asset_type=args.asset_type,
        )
        log.info(
            "stage1: buildings=%s sigungu=%s excluded_sg=%s",
            len(result.building_rows),
            result.included_sigungu,
            result.excluded_sigungu,
        )
        for w in result.warnings[:10]:
            log.warning(w)
        if args.replace:
            delete_snapshot(engine, as_of, wy, args.asset_type)
        upsert_rows(engine, "collective_building_quality_index", result.building_rows)
        upsert_rows(engine, "collective_sigungu_base_level", result.base_rows)


if __name__ == "__main__":
    main()
