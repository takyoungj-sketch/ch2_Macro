from sqlalchemy import text
from db_utils import get_engine

e = get_engine()
with e.connect() as c:
    n_raw = c.execute(
        text(
            """
            SELECT COUNT(1) FROM land_raw
            WHERE source_file LIKE '%전북특별자치도%2010%'
            """
        )
    ).scalar()
    print("raw rows source 2010 jeonbuk:", n_raw)
    sample = c.execute(
        text(
            """
            SELECT id, payload->>'deal_ymd' AS ymd, payload->>'contract_year' AS cy,
                   payload->>'sigungu_name' AS sg, processed
            FROM land_raw
            WHERE source_file LIKE '%전북특별자치도%2010%'
            LIMIT 5
            """
        )
    ).fetchall()
    for r in sample:
        print(r)
    proc = c.execute(
        text(
            """
            SELECT processed, COUNT(1) FROM land_raw
            WHERE source_file LIKE '%전북특별자치도%2010%'
            GROUP BY 1
            """
        )
    ).fetchall()
    print("processed counts:", proc)
