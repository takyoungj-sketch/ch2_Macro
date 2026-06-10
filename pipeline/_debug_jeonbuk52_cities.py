# -*- coding: utf-8 -*-
"""Find Jeonbuk 2010 raw by city names (no sido prefix in historical CSV)."""
from sqlalchemy import text
from db_utils import get_engine

# 전북 시군구 키워드 (2010 CSV는 '전라북도' 접두 없이 '전주시' 등만 표기)
JB_CITIES = (
    "전주", "군산", "익산", "정읍", "남원", "김제", "완주", "진안", "무주",
    "장수", "임실", "순창", "고창", "부안",
)

e = get_engine()
with e.connect() as c:
    cond = " OR ".join(
        f"r.raw_data->>'sigungu_name' LIKE '{city}%'" for city in JB_CITIES
    )
    rows = c.execute(
        text(
            f"""
            SELECT LEFT(r.raw_data->>'deal_ymd', 4) AS yr, COUNT(1) AS n,
                   SUM(CASE WHEN EXISTS (
                     SELECT 1 FROM land_transactions lt WHERE lt.raw_id = r.id
                   ) THEN 1 ELSE 0 END) AS linked
            FROM land_transactions_raw r
            WHERE ({cond})
            GROUP BY 1 ORDER BY 1
            """
        )
    ).fetchall()
    print("Jeonbuk city-pattern raw by deal year:")
    for r in rows:
        if str(r[0]).isdigit() and len(str(r[0])) == 4:
            print(f"  {r[0]}: linked={r[2]}/{r[1]}")

    y2010 = c.execute(
        text(
            f"""
            SELECT COUNT(1) FROM land_transactions_raw r
            WHERE r.raw_data->>'deal_ymd' LIKE '2010%'
              AND ({cond})
            """
        )
    ).scalar()
    print("\n2010 Jeonbuk city-pattern raw total:", y2010)

    unproc = c.execute(
        text(
            f"""
            SELECT COUNT(1) FROM land_transactions_raw r
            WHERE r.raw_data->>'deal_ymd' LIKE '2010%'
              AND ({cond})
              AND NOT EXISTS (
                SELECT 1 FROM land_transactions lt WHERE lt.raw_id = r.id
              )
            """
        )
    ).scalar()
    print("unprocessed 2010:", unproc)
