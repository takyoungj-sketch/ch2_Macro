# -*- coding: utf-8 -*-
from sqlalchemy import text
from db_utils import get_engine

e = get_engine()
with e.connect() as c:
    n = c.execute(
        text(
            """
            SELECT COUNT(1) FROM land_transactions_raw r
            WHERE r.raw_data->>'deal_ymd' = '201012'
              AND r.raw_data->>'sigungu_name' LIKE '전주%'
            """
        )
    ).scalar()
    print("raw 201012 전주*:", n)

    sy = c.execute(
        text(
            """
            SELECT source_year, source_month, COUNT(1)
            FROM land_transactions_raw r
            WHERE r.raw_data->>'sigungu_name' LIKE '전주%'
            GROUP BY 1, 2 ORDER BY 1, 2
            """
        )
    ).fetchall()
    print("전주* raw by source_year/month:")
    for r in sy:
        print(r)

    recent = c.execute(
        text(
            """
            SELECT COUNT(1) FROM land_transactions_raw
            WHERE loaded_at >= '2026-06-10'
              AND raw_data->>'sigungu_name' LIKE '전주%'
            """
        )
    ).scalar()
    print("전주* loaded since 2026-06-10:", recent)

    deal2010 = c.execute(
        text(
            """
            SELECT COUNT(1) FROM land_transactions_raw
            WHERE raw_data->>'deal_ymd' LIKE '2010%'
              AND raw_data->>'sigungu_name' LIKE '전주%'
            """
        )
    ).scalar()
    print("deal_ymd 2010 + 전주:", deal2010)
