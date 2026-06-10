from db_utils import get_engine
from sqlalchemy import text

e = get_engine()
with e.connect() as c:
    n = c.execute(
        text(
            """
            SELECT count FROM land_upper_stats_v2
            WHERE region_level='eupmyeondong' AND region_code='36110109'
              AND as_of_month='2026-05-01' AND window_years=5
              AND zone_type='ALL' AND land_category='ALL'
            """
        )
    ).scalar()
    print("다정동 upper count:", n)

    tops = c.execute(
        text(
            """
            SELECT region_code, count FROM land_upper_stats_v2
            WHERE region_level='eupmyeondong' AND region_code LIKE '361101%'
              AND as_of_month='2026-05-01' AND window_years=5
              AND zone_type='ALL' AND land_category='ALL'
            ORDER BY count DESC LIMIT 8
            """
        )
    ).fetchall()
    print("top 361101xx upper:", tops)

    ntx = c.execute(
        text(
            """
            SELECT COUNT(*) FROM land_transactions
            WHERE sido_code='36' AND LEFT(btrim(beopjungri_code::text),8) LIKE '361101%'
            """
        )
    ).scalar()
    print("361101xx txs total:", ntx)
