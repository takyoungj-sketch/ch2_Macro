# -*- coding: utf-8 -*-
"""Inspect actual bytes/prefix of sigungu_name in DB."""
from sqlalchemy import text
from db_utils import get_engine

e = get_engine()
with e.connect() as c:
    rows = c.execute(
        text(
            """
            SELECT DISTINCT LEFT(raw_data->>'sigungu_name', 20) AS pfx, COUNT(1)
            FROM land_transactions_raw r
            WHERE r.source_year = 2010 AND r.source_month = 6
              AND r.loaded_at >= '2026-06-10'
              AND raw_data->>'deal_ymd' LIKE '2010%'
            GROUP BY 1
            HAVING COUNT(1) > 1000
            ORDER BY 2 DESC
            LIMIT 30
            """
        )
    ).fetchall()
    print("prefixes (repr):")
    for pfx, n in rows:
        print(repr(pfx), n)

    # pick one row id for jeonbuk-like prefix (2nd highest after 세종?)
    sample = c.execute(
        text(
            """
            SELECT r.id, raw_data->>'sigungu_name', raw_data->>'deal_ymd'
            FROM land_transactions_raw r
            WHERE r.source_year = 2010 AND r.source_month = 6
              AND r.loaded_at >= '2026-06-10'
              AND raw_data->>'deal_ymd' = '201012'
            OFFSET 100 LIMIT 3
            """
        )
    ).fetchall()
    print("\nrandom samples:")
    for s in sample:
        print(s[0], repr(s[1]), s[2])
