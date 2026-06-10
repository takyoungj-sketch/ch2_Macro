from sqlalchemy import text
from db_utils import get_engine

e = get_engine()
with e.connect() as c:
    rows = c.execute(
        text(
            """
            SELECT contract_year, COUNT(1) AS n
            FROM land_transactions
            WHERE LEFT(btrim(beopjungri_code::text), 2) = '52'
            GROUP BY 1 ORDER BY 1
            """
        )
    ).fetchall()
    print("land_transactions by year (52):")
    for r in rows:
        print(r)
    ann = c.execute(
        text(
            """
            SELECT MIN(calendar_year), MAX(calendar_year), COUNT(1)
            FROM land_annual_stats
            WHERE LEFT(btrim(beopjungri_code::text), 2) = '52'
            """
        )
    ).one()
    print("annual_stats 52:", ann)
