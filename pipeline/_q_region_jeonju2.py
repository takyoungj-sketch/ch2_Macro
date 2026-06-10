from sqlalchemy import text
from db_utils import get_engine

e = get_engine()
with e.connect() as c:
    rows = c.execute(
        text(
            """
            SELECT DISTINCT sido_name FROM region_codes
            WHERE sido_code = '52' OR LEFT(beopjungri_code::text, 2) = '52'
            """
        )
    ).fetchall()
    print("sido names for 52:", rows)
    rows2 = c.execute(
        text(
            """
            SELECT sido_name, sigungu_name, eupmyeondong_name, beopjungri_code
            FROM region_codes
            WHERE sigungu_name LIKE '%전주시 완산구%' AND eupmyeondong_name LIKE '효자동%'
            LIMIT 5
            """
        )
    ).fetchall()
    print("hyoja variants:")
    for r in rows2:
        print(r)
