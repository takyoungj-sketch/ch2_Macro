# -*- coding: utf-8 -*-
"""Jeonbuk 2010: linked vs unlinked, mapping outcome."""
import pandas as pd
from sqlalchemy import text

from clean import build_region_lookup, clean_dataframe, map_beopjungri_codes
from db_utils import get_engine

e = get_engine()
with e.connect() as c:
    # 전주광역시 pattern in 2010 deal_ymd
    stats = c.execute(
        text(
            """
            SELECT
              COUNT(1) AS total,
              SUM(CASE WHEN EXISTS (SELECT 1 FROM land_transactions lt WHERE lt.raw_id = r.id)
                  THEN 1 ELSE 0 END) AS linked,
              SUM(CASE WHEN NOT EXISTS (SELECT 1 FROM land_transactions lt WHERE lt.raw_id = r.id)
                  THEN 1 ELSE 0 END) AS unlinked
            FROM land_transactions_raw r
            WHERE r.raw_data->>'deal_ymd' LIKE '2010%'
              AND r.raw_data->>'sigungu_name' LIKE '%전주광역시%'
            """
        )
    ).fetchone()
    print("2010 전주광역시 raw:", stats)

    # linked txs - what sido/year?
    tx = c.execute(
        text(
            """
            SELECT lt.contract_year,
                   LEFT(btrim(lt.beopjungri_code::text), 2) AS sido,
                   COUNT(1)
            FROM land_transactions lt
            JOIN land_transactions_raw r ON r.id = lt.raw_id
            WHERE r.raw_data->>'deal_ymd' LIKE '2010%'
              AND r.raw_data->>'sigungu_name' LIKE '%전주광역시%'
            GROUP BY 1, 2 ORDER BY 1, 2
            """
        )
    ).fetchall()
    print("linked tx by year/sido:", tx)

    # unlinked sample + map test
    rows = c.execute(
        text(
            """
            SELECT r.id, r.raw_data
            FROM land_transactions_raw r
            WHERE r.raw_data->>'deal_ymd' LIKE '2010%'
              AND r.raw_data->>'sigungu_name' LIKE '%전주광역시%'
              AND NOT EXISTS (SELECT 1 FROM land_transactions lt WHERE lt.raw_id = r.id)
            LIMIT 200
            """
        )
    ).fetchall()
    print("unlinked sample count fetched:", len(rows))

    if rows:
        recs = [{"_raw_id": r[0], "_source_year": 2010, "_source_month": 6, **r[1]} for r in rows]
        df = pd.DataFrame(recs)
        cleaned = clean_dataframe(df)
        lookup = build_region_lookup(e)
        mapped = map_beopjungri_codes(cleaned, lookup)
        ok = mapped["beopjungri_code"].astype(str).str.startswith("52").sum()
        valid = cleaned["is_valid"].sum()
        print(f"map to 52: {ok}/{len(mapped)}, is_valid: {valid}/{len(cleaned)}")
        print("mapping notes:", mapped["mapping_notes"].value_counts().head().to_dict())
        print("sample addrs:", df["sigungu_name"].head(3).tolist())
        print("sample codes:", mapped["beopjungri_code"].head(5).tolist())

    # 전북특별자치도 prefix in 2010
    jb = c.execute(
        text(
            """
            SELECT COUNT(1),
              SUM(CASE WHEN EXISTS (SELECT 1 FROM land_transactions lt WHERE lt.raw_id = r.id)
                  THEN 1 ELSE 0 END)
            FROM land_transactions_raw r
            WHERE r.raw_data->>'deal_ymd' LIKE '2010%'
              AND r.raw_data->>'sigungu_name' LIKE '전북특별자치도%'
            """
        )
    ).fetchone()
    print("\n2010 전북특별자치도% raw:", jb)

    tx2 = c.execute(
        text(
            """
            SELECT lt.contract_year, COUNT(1)
            FROM land_transactions lt
            JOIN land_transactions_raw r ON r.id = lt.raw_id
            WHERE r.raw_data->>'deal_ymd' LIKE '2010%'
              AND r.raw_data->>'sigungu_name' LIKE '전북특별자치도%'
              AND LEFT(btrim(lt.beopjungri_code::text), 2) = '52'
            GROUP BY 1 ORDER BY 1
            """
        )
    ).fetchall()
    print("linked tx 52 from 전북특별 prefix:", tx2)
