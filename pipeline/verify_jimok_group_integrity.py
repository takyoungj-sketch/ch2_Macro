"""Integrity: zone×group count == sum of member zone×category counts."""
from __future__ import annotations

import argparse
from collections import defaultdict

from sqlalchemy import text

from db_utils import get_engine

DEFAULT_AS_OF = "2026-06-01"
DEFAULT_WINDOW = 5
DEFAULT_SIDO = "43"


def main() -> None:
    p = argparse.ArgumentParser(description="지목군 V2 integrity (Chungbuk sample + ALL×ALL)")
    p.add_argument("--as-of-month", default=DEFAULT_AS_OF, help="YYYY-MM-DD (월 1일)")
    p.add_argument("--window-years", type=int, default=DEFAULT_WINDOW)
    p.add_argument("--sido-code", default=DEFAULT_SIDO)
    args = p.parse_args()

    as_of = args.as_of_month.strip()
    window = int(args.window_years)
    sido = args.sido_code.strip()

    engine = get_engine()
    with engine.connect() as c:
        code = c.execute(
            text(
                """
                SELECT beopjungri_code
                FROM land_basic_stats_v2
                WHERE as_of_month = :a AND window_years = :w
                  AND col_axis = 'group' AND beopjungri_code LIKE :p
                  AND zone_type = 'ALL' AND land_category = 'ALL' AND count > 50
                ORDER BY count DESC
                LIMIT 1
                """
            ),
            {"a": as_of, "w": window, "p": f"{sido}%"},
        ).scalar()
        print("sample_code", code)
        if not code:
            raise SystemExit(f"no group sample (as_of={as_of}, sido={sido})")

        map_rows = c.execute(
            text(
                """
                SELECT jimok_key, group_code FROM land_jimok_group_map
                """
            )
        ).fetchall()
        members: dict[str, set[str]] = defaultdict(set)
        for k, g in map_rows:
            members[str(g)].add(str(k))

        group_rows = c.execute(
            text(
                """
                SELECT zone_type, land_category, count
                FROM land_basic_stats_v2
                WHERE as_of_month = :a AND window_years = :w
                  AND beopjungri_code = :c AND col_axis = 'group'
                  AND zone_type <> 'ALL' AND land_category <> 'ALL'
                """
            ),
            {"a": as_of, "w": window, "c": code},
        ).fetchall()

        cat_rows = c.execute(
            text(
                """
                SELECT zone_type, land_category, count
                FROM land_basic_stats_v2
                WHERE as_of_month = :a AND window_years = :w
                  AND beopjungri_code = :c AND col_axis = 'category'
                  AND zone_type <> 'ALL' AND land_category <> 'ALL'
                """
            ),
            {"a": as_of, "w": window, "c": code},
        ).fetchall()

        cat_lookup: dict[tuple[str, str], int] = {
            (str(z), str(lc)): int(n) for z, lc, n in cat_rows
        }

        mismatches = 0
        checked = 0
        for z, g, n in group_rows:
            z, g = str(z), str(g)
            expected = sum(cat_lookup.get((z, m), 0) for m in members.get(g, set()))
            checked += 1
            if expected != int(n):
                mismatches += 1
                if mismatches <= 8:
                    print("MISMATCH", z, g, "group=", n, "sum_cat=", expected)

        print("checked_cells", checked, "mismatches", mismatches)

        g_all = c.execute(
            text(
                """
                SELECT count FROM land_basic_stats_v2
                WHERE as_of_month=:a AND window_years=:w AND beopjungri_code=:c
                  AND col_axis='group' AND zone_type='ALL' AND land_category='ALL'
                """
            ),
            {"a": as_of, "w": window, "c": code},
        ).scalar()
        c_all = c.execute(
            text(
                """
                SELECT count FROM land_basic_stats_v2
                WHERE as_of_month=:a AND window_years=:w AND beopjungri_code=:c
                  AND col_axis='category' AND zone_type='ALL' AND land_category='ALL'
                """
            ),
            {"a": as_of, "w": window, "c": code},
        ).scalar()
        print("ALL×ALL group", g_all, "category", c_all, "eq", g_all == c_all)

        labels = c.execute(
            text(
                """
                SELECT DISTINCT land_category FROM land_basic_stats_v2
                WHERE as_of_month=:a AND window_years=:w AND beopjungri_code LIKE :p
                  AND col_axis='group' AND land_category <> 'ALL'
                ORDER BY 1
                """
            ),
            {"a": as_of, "w": window, "p": f"{sido}%"},
        ).fetchall()
        print("group_keys", [r[0] for r in labels])

    if mismatches:
        raise SystemExit(f"jimok group integrity FAILED: mismatches={mismatches}")


if __name__ == "__main__":
    main()
