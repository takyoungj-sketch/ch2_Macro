from db_utils import get_engine
from sqlalchemy import text

e = get_engine()
with e.connect() as c:
    n = c.execute(
        text(
            """
            SELECT COUNT(*) FROM land_transactions lt
            JOIN land_transactions_raw r ON r.id = lt.raw_id
            WHERE r.raw_data->>'sigungu_name' ~ '^세종특별자치시\\s+[가-힣]+동\\s*$'
              AND LEFT(btrim(lt.beopjungri_code::text), 8) LIKE '361101%'
            """
        )
    ).scalar()
    print("dong rows with 361101xx after partial run:", n)
