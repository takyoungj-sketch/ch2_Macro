from sqlalchemy import text
from db_utils import get_engine

e = get_engine()
with e.connect() as c:
    unproc = c.execute(
        text(
            """
            SELECT COUNT(1) FROM land_transactions_raw r
            WHERE NOT EXISTS (
              SELECT 1 FROM land_transactions lt WHERE lt.raw_id = r.id
            )
            """
        )
    ).scalar()
    print("unprocessed raw total:", unproc)

    jb2010 = c.execute(
        text(
            """
            SELECT COUNT(1) FROM land_transactions_raw r
            WHERE source_year = 2010 AND source_month = 6
              AND raw_data->>'deal_ymd' LIKE '2010%'
            """
        )
    ).scalar()
    print("raw source_year=2010/6 with deal_ymd 2010:", jb2010)

    since = c.execute(
        text(
            """
            SELECT COUNT(1) FROM land_transactions_raw
            WHERE loaded_at >= '2026-06-10'
            """
        )
    ).scalar()
    print("raw loaded since 2026-06-10:", since)
