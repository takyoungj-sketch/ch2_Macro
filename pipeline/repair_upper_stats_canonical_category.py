# -*- coding: utf-8 -*-
"""Repair land_upper_stats_v2: copy category col_axis from historical → canonical eup.

Partial canonical rebuild left category rows on historical eup prefix and group on
canonical — upper-stats default matrix_mode=category then returns empty matrix.

Usage:
  cd backend
  .venv/Scripts/python.exe ../pipeline/repair_upper_stats_canonical_category.py
  .venv/Scripts/python.exe ../pipeline/repair_upper_stats_canonical_category.py --dry-run
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))

from dotenv import load_dotenv

load_dotenv(ROOT / "backend" / ".env", override=True)
load_dotenv()

from sqlalchemy import text

from db_utils import get_engine
from region_canonical import RESOLVE_CHANGE_TYPES

_TYPES = ",".join(f"'{t}'" for t in RESOLVE_CHANGE_TYPES)

COPY_SQL = text(
    """
    INSERT INTO land_upper_stats_v2 (
        region_level, region_code, as_of_month, window_years,
        zone_type, land_category, col_axis,
        count, mean, std, ci_lower, ci_upper,
        p_min, p25, median, p75, p_max,
        period_start, period_end
    )
    SELECT
        region_level, :canon_eup, as_of_month, window_years,
        zone_type, land_category, col_axis,
        count, mean, std, ci_lower, ci_upper,
        p_min, p25, median, p75, p_max,
        period_start, period_end
    FROM land_upper_stats_v2
    WHERE region_level = 'eupmyeondong'
      AND btrim(region_code::text) = :hist_eup
      AND col_axis = 'category'
    ON CONFLICT ON CONSTRAINT land_upper_stats_v2_grain_uq DO NOTHING
    """
)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    eng = get_engine()
    with eng.connect() as conn:
        pairs = conn.execute(
            text(
                f"""
                SELECT DISTINCT ON (from_code) from_code, to_code
                FROM region_code_history
                WHERE change_type IN ({_TYPES})
                ORDER BY from_code, effective_from DESC, id DESC
                """
            )
        ).fetchall()

    eup_pairs: list[tuple[str, str]] = []
    for row in pairs:
        hist = str(row.from_code).strip()[:8]
        canon = str(row.to_code).strip()[:8]
        if hist != canon and (hist, canon) not in eup_pairs:
            eup_pairs.append((hist, canon))

    copied = 0
    deleted = 0
    with eng.begin() as conn:
        for hist_eup, canon_eup in eup_pairs:
            before_canon = conn.execute(
                text(
                    """
                    SELECT COUNT(*)::int FROM land_upper_stats_v2
                    WHERE region_level='eupmyeondong' AND region_code=:c AND col_axis='category'
                    """
                ),
                {"c": canon_eup},
            ).scalar()
            before_hist = conn.execute(
                text(
                    """
                    SELECT COUNT(*)::int FROM land_upper_stats_v2
                    WHERE region_level='eupmyeondong' AND region_code=:c AND col_axis='category'
                    """
                ),
                {"c": hist_eup},
            ).scalar()
            if before_canon > 0 or before_hist == 0:
                continue
            if args.dry_run:
                print(f"DRY {hist_eup} -> {canon_eup}: would copy {before_hist} category rows")
                continue
            n = conn.execute(COPY_SQL, {"canon_eup": canon_eup, "hist_eup": hist_eup}).rowcount
            copied += int(n or 0)
            d = conn.execute(
                text(
                    """
                    DELETE FROM land_upper_stats_v2
                    WHERE region_level='eupmyeondong'
                      AND btrim(region_code::text) = :hist_eup
                      AND col_axis = 'category'
                    """
                ),
                {"hist_eup": hist_eup},
            ).rowcount
            deleted += int(d or 0)
            print(f"OK {hist_eup} -> {canon_eup}: copied={n} deleted_hist={d}")

    print(f"done copied={copied} deleted_hist={deleted} dry_run={args.dry_run}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
