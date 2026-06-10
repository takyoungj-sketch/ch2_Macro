from sqlalchemy import text
from db_utils import get_engine

e = get_engine()
with e.connect() as c:
    n = c.execute(
        text(
            """
            SELECT COUNT(1) FROM land_transactions_raw
            WHERE loaded_at >= '2026-06-10'
            """
        )
    ).scalar()
    print("raw loaded today:", n)
    rows = c.execute(
        text(
            """
            SELECT source_year, COUNT(1)
            FROM land_transactions_raw
            WHERE loaded_at >= '2026-06-10'
            GROUP BY 1 ORDER BY 1
            """
        )
    ).fetchall()
    print("by source_year:", rows)
    sample = c.execute(
        text(
            """
            SELECT raw_data->>'sigungu_name', raw_data->>'deal_ymd'
            FROM land_transactions_raw
            WHERE source_year = 2010 AND loaded_at >= '2026-06-10'
            LIMIT 3
            """
        )
    ).fetchall()
    print("2010 samples:", sample)
