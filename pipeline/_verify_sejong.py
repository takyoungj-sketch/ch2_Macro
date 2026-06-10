from sqlalchemy import text
from db_utils import get_engine

e = get_engine()
with e.connect() as c:
    txs = c.execute(
        text(
            "SELECT COUNT(*) FROM land_transactions "
            "WHERE sido_code='36' AND beopjungri_code LIKE '361101%'"
        )
    ).scalar()
    empty = c.execute(
        text(
            "SELECT COUNT(*) FROM land_transactions "
            "WHERE sido_code='36' AND (beopjungri_code IS NULL OR btrim(beopjungri_code::text)='')"
        )
    ).scalar()
    upper = c.execute(
        text(
            "SELECT COUNT(*) FROM land_upper_stats_v2 "
            "WHERE region_code LIKE '361101%' AND as_of_month='2026-05-01'"
        )
    ).scalar()
    dajeong = c.execute(
        text(
            "SELECT COUNT(*) FROM land_upper_stats_v2 "
            "WHERE region_code='36110109' AND as_of_month='2026-05-01'"
        )
    ).scalar()
print(f"361101xx txs: {txs}")
print(f"empty beopjungri (sido 36): {empty}")
print(f"upper stats 361101xx: {upper}")
print(f"dajeong upper stats: {dajeong}")
