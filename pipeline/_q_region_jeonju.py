from sqlalchemy import text
from db_utils import get_engine

e = get_engine()
with e.connect() as c:
    rows = c.execute(
        text(
            """
            SELECT sido_name, sigungu_name, eupmyeondong_name, beopjungri_name, beopjungri_code
            FROM region_codes
            WHERE sigungu_name LIKE '%전주%' AND eupmyeondong_name LIKE '%효자%'
            LIMIT 10
            """
        )
    ).fetchall()
    for r in rows:
        print(r)
