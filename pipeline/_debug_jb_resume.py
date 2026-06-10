# -*- coding: utf-8 -*-
"""Resume debug: Jeonbuk 2010 raw field inspection."""
from sqlalchemy import text
from db_utils import get_engine

e = get_engine()
with e.connect() as c:
    # Sample from source_year=2010/6 batch (Jeonbuk historical collect)
    rows = c.execute(
        text(
            """
            SELECT raw_data->>'deal_ymd' AS ymd,
                   raw_data->>'sigungu_name' AS addr,
                   raw_data->>'sigungu_code' AS sgc,
                   EXISTS (SELECT 1 FROM land_transactions lt WHERE lt.raw_id = r.id) AS linked
            FROM land_transactions_raw r
            WHERE r.source_year = 2010 AND r.source_month = 6
              AND r.loaded_at >= '2026-06-10'
            LIMIT 8
            """
        )
    ).fetchall()
    print("source 2010/6 recent load samples:")
    for r in rows:
        print(r)

    # Address prefix distribution in that batch
    pref = c.execute(
        text(
            """
            SELECT LEFT(raw_data->>'sigungu_name', 8) AS pfx, COUNT(1)
            FROM land_transactions_raw r
            WHERE r.source_year = 2010 AND r.source_month = 6
              AND r.loaded_at >= '2026-06-10'
            GROUP BY 1 ORDER BY 2 DESC LIMIT 15
            """
        )
    ).fetchall()
    print("\naddr prefix top (2010/6 recent):")
    for p in pref:
        print(p)

    # deal_ymd year distribution same batch
    dy = c.execute(
        text(
            """
            SELECT LEFT(raw_data->>'deal_ymd', 4) AS y4, COUNT(1),
              SUM(CASE WHEN EXISTS (SELECT 1 FROM land_transactions lt WHERE lt.raw_id = r.id)
                  THEN 1 ELSE 0 END)
            FROM land_transactions_raw r
            WHERE r.source_year = 2010 AND r.source_month = 6
              AND r.loaded_at >= '2026-06-10'
            GROUP BY 1 ORDER BY 1
            """
        )
    ).fetchall()
    print("\ndeal_ymd years (2010/6 recent):")
    for d in dy:
        print(d)

    # 전주광역시 anywhere
    n = c.execute(
        text(
            """
            SELECT COUNT(1) FROM land_transactions_raw
            WHERE raw_data->>'sigungu_name' LIKE '전주%'
            """
        )
    ).scalar()
    print("\nraw with addr LIKE 전주%:", n)

    n2 = c.execute(
        text(
            """
            SELECT COUNT(1) FROM land_transactions_raw
            WHERE raw_data->>'sigungu_name' LIKE '%전주%'
            """
        )
    ).scalar()
    print("raw with addr LIKE %전주%:", n2)

    # annual + tx
    ann = c.execute(
        text(
            """
            SELECT MIN(calendar_year), MAX(calendar_year), COUNT(*)
            FROM land_annual_stats
            WHERE LEFT(btrim(beopjungri_code::text), 2) = '52'
            """
        )
    ).fetchone()
    print("\nannual 52:", ann)

    tx = c.execute(
        text(
            """
            SELECT contract_year, COUNT(1)
            FROM land_transactions
            WHERE LEFT(btrim(beopjungri_code::text), 2) = '52'
            GROUP BY 1 ORDER BY 1
            """
        )
    ).fetchall()
    print("tx 52 by year:", tx)
