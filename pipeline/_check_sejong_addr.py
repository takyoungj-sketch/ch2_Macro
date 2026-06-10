from sqlalchemy import text

from built.db_utils import get_built_engine
from collective.db_utils import get_collective_engine

be = get_built_engine()
ce = get_collective_engine()

for label, eng, table, extra in [
    ("built commercial", be, "built_transactions", "AND asset_type='commercial'"),
    ("built factory", be, "built_transactions", "AND asset_type='factory'"),
    ("collective apt", ce, "collective_transactions", "AND asset_type='apartment'"),
    ("commercial shop", ce, "collective_commercial_transactions", ""),
]:
    with eng.connect() as c:
        a2 = c.execute(
            text(
                f"""
                SELECT DISTINCT btrim(addr2::text) AS v, COUNT(*) AS n
                FROM {table}
                WHERE addr1 LIKE '%세종%' {extra}
                GROUP BY 1 ORDER BY n DESC LIMIT 5
                """
            )
        ).fetchall()
        a3 = c.execute(
            text(
                f"""
                SELECT DISTINCT btrim(addr3::text) AS v, COUNT(*) AS n
                FROM {table}
                WHERE addr1 LIKE '%세종%' {extra}
                GROUP BY 1 ORDER BY n DESC LIMIT 8
                """
            )
        ).fetchall()
        print(f"\n=== {label} ===")
        print("addr2:", a2)
        print("addr3:", a3)
