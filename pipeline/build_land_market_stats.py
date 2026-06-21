#!/usr/bin/env python3
"""
land_upper_stats_v2 (용도×지목) → collective market_stats land_* domain.

설계: docs/REGIONAL_PROFILE_ARCHITECTURE.md Phase D P0
규칙: pipeline/config/land_domain_extraction.yaml

예:
  cd pipeline
  python build_land_market_stats.py --sido-code 43 --windows 3,5
"""

from __future__ import annotations

import argparse
import logging
import sys
import uuid
from datetime import date
from pathlib import Path

from sqlalchemy import text

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "pipeline"))

from build_collective_market_stats import upsert_market_stats  # noqa: E402
from build_stats_v2 import default_as_of_month, parse_as_of_month  # noqa: E402
from collective.db_utils import get_collective_engine, get_land_engine_for_region_copy  # noqa: E402
from land_domain_extraction import (  # noqa: E402
    build_domain_market_record,
    load_domain_config,
    pick_domain_row,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger(__name__)

LAND_DOMAINS_V1 = ("land_residential", "land_commercial", "land_industrial")
LAND_DOMAINS_EXTENDED = ("land_agricultural", "land_forest")

FETCH_SQL = """
SELECT
    region_level, region_code, zone_type, land_category,
    count, mean, median, std, ci_lower, ci_upper, p25, p75,
    period_start, period_end
FROM land_upper_stats_v2
WHERE as_of_month = :as_of
  AND window_years = :wy
  AND (
        (:sido IS NULL)
     OR (region_level = 'sido' AND region_code = :sido)
     OR (region_level IN ('sigungu', 'eupmyeondong', 'city') AND region_code LIKE :sido_prefix)
  )
"""


def _group_upper_rows(rows: list[dict]) -> dict[tuple[str, str], dict[tuple[str, str], dict]]:
    """(level, code) → {(zone, cat): row}."""
    grouped: dict[tuple[str, str], dict[tuple[str, str], dict]] = {}
    for r in rows:
        level = str(r["region_level"]).strip()
        code = str(r["region_code"]).strip()
        z = str(r["zone_type"]).strip()
        c = str(r["land_category"]).strip()
        grouped.setdefault((level, code), {})[(z, c)] = dict(r)
    return grouped


def build_records_for_window(
    grouped: dict[tuple[str, str], dict[tuple[str, str], dict]],
    *,
    domain_rules,
    as_of: date,
    window_years: int,
    batch_id: str,
    include_extended: bool,
) -> list[dict]:
    names = list(LAND_DOMAINS_V1)
    if include_extended:
        names.extend(LAND_DOMAINS_EXTENDED)

    out: list[dict] = []
    for (level, code), cell_map in grouped.items():
        for dname in names:
            rule = domain_rules.get(dname)
            if not rule:
                continue
            row = pick_domain_row(cell_map, rule)
            if not row:
                continue
            out.append(
                build_domain_market_record(
                    market_domain=dname,
                    region_level=level,
                    region_code=code,
                    row=row,
                    as_of_month=as_of,
                    window_years=window_years,
                    batch_id=batch_id,
                )
            )
    return out


def main() -> None:
    p = argparse.ArgumentParser(description="토지 domain → market_stats (collective DB)")
    p.add_argument("--as-of", type=str, default=None)
    p.add_argument("--windows", type=str, default="3,5")
    p.add_argument(
        "--sido-code",
        type=str,
        default=None,
        help="시도 코드 (미지정=전국). 파일럿: 43",
    )
    p.add_argument("--include-extended", action="store_true", help="land_agricultural/forest 포함")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    as_of = parse_as_of_month(args.as_of) if args.as_of else default_as_of_month()
    windows = [int(x.strip()) for x in args.windows.split(",") if x.strip()]
    sido = str(args.sido_code).strip() if args.sido_code else None
    batch_id = str(uuid.uuid4())
    domain_rules, _ = load_domain_config()

    land_eng = get_land_engine_for_region_copy()
    coll_eng = get_collective_engine()

    params_base = {"as_of": as_of, "sido": sido, "sido_prefix": f"{sido}%" if sido else None}
    total = 0
    with land_eng.connect() as lconn:
        if not lconn.execute(text("SELECT to_regclass('public.land_upper_stats_v2') IS NOT NULL")).scalar():
            raise SystemExit("land_upper_stats_v2 없음 — build_upper_stats_v2 먼저 실행")

        for wy in windows:
            params = {**params_base, "wy": wy}
            rows = lconn.execute(text(FETCH_SQL), params).mappings().all()
            grouped = _group_upper_rows([dict(r) for r in rows])
            records = build_records_for_window(
                grouped,
                domain_rules=domain_rules,
                as_of=as_of,
                window_years=wy,
                batch_id=batch_id,
                include_extended=args.include_extended,
            )
            log.info(
                "window=%sy sido=%s regions=%s records=%s",
                wy,
                sido or "ALL",
                len(grouped),
                len(records),
            )
            if args.dry_run:
                total += len(records)
                continue
            upsert_market_stats(records, coll_eng)
            total += len(records)

    log.info("land market_stats upserted %s rows batch=%s", total, batch_id[:8])


if __name__ == "__main__":
    main()
