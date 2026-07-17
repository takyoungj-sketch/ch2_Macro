"""Integrity: Chungbuk zone×group count == sum of member zone×category counts."""
from __future__ import annotations

from collections import defaultdict

from sqlalchemy import text

from db_utils import get_engine

AS_OF = "2026-06-01"
WINDOW = 5
SIDO = "43"

engine = get_engine()
with engine.connect() as c:
    # sample one beopjungri with enough txs
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
        {"a": AS_OF, "w": WINDOW, "p": f"{SIDO}%"},
    ).scalar()
    print("sample_code", code)
    if not code:
        raise SystemExit("no group sample")

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
        {"a": AS_OF, "w": WINDOW, "c": code},
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
        {"a": AS_OF, "w": WINDOW, "c": code},
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

    # ALL×ALL equality
    g_all = c.execute(
        text(
            """
            SELECT count FROM land_basic_stats_v2
            WHERE as_of_month=:a AND window_years=:w AND beopjungri_code=:c
              AND col_axis='group' AND zone_type='ALL' AND land_category='ALL'
            """
        ),
        {"a": AS_OF, "w": WINDOW, "c": code},
    ).scalar()
    c_all = c.execute(
        text(
            """
            SELECT count FROM land_basic_stats_v2
            WHERE as_of_month=:a AND window_years=:w AND beopjungri_code=:c
              AND col_axis='category' AND zone_type='ALL' AND land_category='ALL'
            """
        ),
        {"a": AS_OF, "w": WINDOW, "c": code},
    ).scalar()
    print("ALL×ALL group", g_all, "category", c_all, "eq", g_all == c_all)

    # group labels present
    labels = c.execute(
        text(
            """
            SELECT DISTINCT land_category FROM land_basic_stats_v2
            WHERE as_of_month=:a AND window_years=:w AND beopjungri_code LIKE :p
              AND col_axis='group' AND land_category <> 'ALL'
            ORDER BY 1
            """
        ),
        {"a": AS_OF, "w": WINDOW, "p": f"{SIDO}%"},
    ).fetchall()
    print("group_keys", [r[0] for r in labels])
