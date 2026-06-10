# -*- coding: utf-8 -*-
"""After mapping fix: how much Jeonbuk 2010 raw got into land_transactions?"""
import pandas as pd
from sqlalchemy import text

from clean import build_region_lookup, clean_dataframe, map_beopjungri_codes
from db_utils import get_engine

e = get_engine()
with e.connect() as c:
    rows = c.execute(
        text(
            """
            SELECT r.id, r.raw_data
            FROM land_transactions_raw r
            WHERE r.source_year = 2010 AND r.source_month = 6
              AND r.raw_data->>'deal_ymd' LIKE '2010%'
              AND r.raw_data->>'sigungu_name' LIKE '전주%'
            LIMIT 500
            """
        )
    ).fetchall()
    print("sample Jeonju 2010 raw:", len(rows))
    if not rows:
        # try gunsan pattern
        rows = c.execute(
            text(
                """
                SELECT r.id, r.raw_data->>'sigungu_name' AS addr
                FROM land_transactions_raw r
                WHERE r.source_year = 2010 AND r.source_month = 6
                  AND r.raw_data->>'deal_ymd' LIKE '2010%'
                  AND (r.raw_data->>'sigungu_name' LIKE '군산%' OR r.raw_data->>'sigungu_name' LIKE '전주%')
                LIMIT 5
                """
            )
        ).fetchall()
        print("addr samples:", rows)
    else:
        recs = [{"_raw_id": r[0], "_source_year": 2010, "_source_month": 6, **r[1]} for r in rows]
        df = pd.DataFrame(recs)
        cleaned = clean_dataframe(df)
        lookup = build_region_lookup(e)
        mapped = map_beopjungri_codes(cleaned, lookup)
        ok = mapped["beopjungri_code"].astype(str).str.startswith("52").sum()
        print(f"mapped to 52: {ok}/{len(mapped)}")
        print("notes:", mapped["mapping_notes"].value_counts().head().to_dict())

    tx2010 = c.execute(
        text(
            """
            SELECT COUNT(1) FROM land_transactions
            WHERE contract_year = 2010
              AND LEFT(btrim(beopjungri_code::text), 2) = '52'
            """
        )
    ).scalar()
    print("land_transactions 2010 sido 52:", tx2010)

    linked = c.execute(
        text(
            """
            SELECT COUNT(1) FROM land_transactions lt
            JOIN land_transactions_raw r ON r.id = lt.raw_id
            WHERE r.source_year = 2010 AND r.source_month = 6
              AND lt.contract_year = 2010
              AND LEFT(btrim(lt.beopjungri_code::text), 2) = '52'
            """
        )
    ).scalar()
    print("linked from 2010 raw batch:", linked)
