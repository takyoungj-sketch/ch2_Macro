"""Inspect Jeonbuk 2010 raw fields and mapping."""
import json

import pandas as pd
from sqlalchemy import text

from clean import build_region_lookup, clean_dataframe, map_beopjungri_codes
from db_utils import get_engine


def main() -> None:
    e = get_engine()
    with e.connect() as c:
        rows = c.execute(
            text(
                """
                SELECT r.id, r.raw_data
                FROM land_transactions_raw r
                WHERE r.source_year = 2010 AND r.source_month = 6
                  AND r.raw_data->>'deal_ymd' LIKE '2010%'
                LIMIT 20
                """
            )
        ).fetchall()
        print("samples:", len(rows))
        for rid, raw in rows[:3]:
            print("--- raw id", rid)
            print(json.dumps(raw, ensure_ascii=False, indent=2)[:800])

        recs = [{"_raw_id": r[0], "_source_year": 2010, "_source_month": 6, **r[1]} for r in rows]
        df = pd.DataFrame(recs)
        cleaned = clean_dataframe(df)
        lookup = build_region_lookup(e)
        mapped = map_beopjungri_codes(cleaned, lookup)
        print("\nmapping notes vc:")
        print(mapped["mapping_notes"].value_counts())
        print("beop prefix vc:")
        print(mapped["beopjungri_code"].astype(str).str[:2].value_counts())

        tx2010 = c.execute(
            text(
                """
                SELECT contract_year, LEFT(btrim(beopjungri_code::text),2) AS sido, COUNT(1)
                FROM land_transactions
                WHERE contract_year IN (2010, 2011, 2013, 2014, 2016, 2020)
                GROUP BY 1, 2
                HAVING LEFT(btrim(beopjungri_code::text),2) = '52'
                ORDER BY 1
                """
            )
        ).fetchall()
        print("\ntx missing years for sido 52:", tx2010)

        # rows upserted but hash dup - raw still unprocessed
        dup = c.execute(
            text(
                """
                SELECT COUNT(1) FROM land_transactions_raw r
                WHERE r.source_year = 2010
                  AND r.raw_data->>'deal_ymd' LIKE '2010%'
                  AND NOT EXISTS (SELECT 1 FROM land_transactions lt WHERE lt.raw_id = r.id)
                  AND EXISTS (
                    SELECT 1 FROM land_transactions lt2
                    WHERE lt2.transaction_hash = (
                      SELECT transaction_hash FROM (
                        SELECT 1
                      ) x
                    )
                  )
                """
            )
        ).scalar()
        print("hash dup probe skipped:", dup)


if __name__ == "__main__":
    main()
