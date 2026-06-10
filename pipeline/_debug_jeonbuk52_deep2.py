# -*- coding: utf-8 -*-
from sqlalchemy import text
from db_utils import get_engine

e = get_engine()
with e.connect() as c:
    # linked Jeonbuk raw -> tx contract_year
    rows = c.execute(
        text(
            """
            SELECT lt.contract_year, COUNT(1)
            FROM land_transactions lt
            JOIN land_transactions_raw r ON r.id = lt.raw_id
            WHERE r.raw_data->>'sigungu_name' LIKE '전라북도%'
               OR r.raw_data->>'sigungu_name' LIKE '전북특별자치도%'
            GROUP BY 1 ORDER BY 1
            """
        )
    ).fetchall()
    print("tx years from Jeonbuk-linked raw:")
    for r in rows:
        print(r)

    # 2010 CSV deal_ymd quality
    q = c.execute(
        text(
            """
            SELECT
              COUNT(1) FILTER (WHERE r.raw_data->>'deal_ymd' ~ '^2010') AS ok_2010,
              COUNT(1) FILTER (WHERE r.raw_data->>'deal_ymd' !~ '^2010' AND r.raw_data->>'contract_year' = '2010') AS cy2010_bad_ymd,
              COUNT(1) AS total
            FROM land_transactions_raw r
            WHERE (r.raw_data->>'sigungu_name' LIKE '전라북도%'
               OR r.raw_data->>'sigungu_name' LIKE '전북특별자치도%')
              AND (r.raw_data->>'deal_ymd' LIKE '2010%' OR r.raw_data->>'contract_year' = '2010')
            """
        )
    ).one()
    print("\n2010 Jeonbuk raw deal_ymd quality:", q)

    bad = c.execute(
        text(
            """
            SELECT r.raw_data->>'deal_ymd', r.raw_data->>'contract_year',
                   r.raw_data->>'sigungu_name', lt.contract_year, lt.beopjungri_code
            FROM land_transactions_raw r
            LEFT JOIN land_transactions lt ON lt.raw_id = r.id
            WHERE (r.raw_data->>'sigungu_name' LIKE '전라북도%'
               OR r.raw_data->>'sigungu_name' LIKE '전북특별자치도%')
              AND r.raw_data->>'contract_year' = '2010'
              AND r.raw_data->>'deal_ymd' !~ '^2010'
            LIMIT 10
            """
        )
    ).fetchall()
    print("\nbad deal_ymd samples:", len(bad))
    for b in bad[:5]:
        print(b)

    # txs with beop 52 and year 2010-2011 from any source
    yr = c.execute(
        text(
            """
            SELECT contract_year, COUNT(1)
            FROM land_transactions
            WHERE LEFT(btrim(beopjungri_code::text), 2) = '52'
              AND contract_year BETWEEN 2010 AND 2011
            GROUP BY 1
            """
        )
    ).fetchall()
    print("\ntx 52 years 2010-2011:", yr)
