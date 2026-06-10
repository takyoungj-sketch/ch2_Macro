from sqlalchemy import text
from db_utils import get_engine

e = get_engine()
with e.connect() as c:
    n = c.execute(
        text(
            """
            SELECT COUNT(1) FROM land_transactions_raw
            WHERE raw_data->>'deal_ymd' = '201012'
            """
        )
    ).scalar()
    print("raw deal_ymd=201012:", n)

    samples = c.execute(
        text(
            """
            SELECT source_year, source_month, raw_data->>'sigungu_name' AS addr,
                   EXISTS (SELECT 1 FROM land_transactions lt WHERE lt.raw_id = land_transactions_raw.id) AS linked
            FROM land_transactions_raw
            WHERE raw_data->>'deal_ymd' = '201012'
            LIMIT 10
            """
        )
    ).fetchall()
    for s in samples:
        print(s)

    # Jeonbuk collect batch: loaded today, source 2010-2020 month 6
    jb = c.execute(
        text(
            """
            SELECT source_year, COUNT(1),
              SUM(CASE WHEN EXISTS (SELECT 1 FROM land_transactions lt WHERE lt.raw_id = r.id) THEN 1 ELSE 0 END)
            FROM land_transactions_raw r
            WHERE r.loaded_at >= '2026-06-10'
              AND r.source_month = 6
              AND r.source_year BETWEEN 2010 AND 2020
            GROUP BY 1 ORDER BY 1
            """
        )
    ).fetchall()
    print("\nloaded today source 2010-2020/6:")
    for r in jb:
        print(r)

    # find 전주광역시 anywhere
    j = c.execute(
        text(
            """
            SELECT COUNT(1) FROM land_transactions_raw
            WHERE raw_data->>'sigungu_name' LIKE '%광역시%'
              AND raw_data->>'deal_ymd' LIKE '2010%'
            """
        )
    ).scalar()
    print("\n2010 rows with 광역시 in addr:", j)
