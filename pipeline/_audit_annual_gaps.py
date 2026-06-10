# -*- coding: utf-8 -*-
"""DB annual min year per sido — detect gaps that CSV issues might cause."""
from sqlalchemy import text
from db_utils import get_engine

e = get_engine()
with e.connect() as c:
    rows = c.execute(
        text(
            """
            SELECT LEFT(btrim(beopjungri_code::text), 2) AS sido,
                   MIN(calendar_year) AS min_y,
                   MAX(calendar_year) AS max_y,
                   COUNT(*) AS n
            FROM land_annual_stats
            GROUP BY 1 ORDER BY 1
            """
        )
    ).fetchall()
    print("sido | min | max | rows")
    for r in rows:
        flag = " OK" if r[1] == 2010 and r[2] >= 2026 else " GAP"
        print(f"  {r[0]} | {r[1]} | {r[2]} | {r[3]}{flag}")
