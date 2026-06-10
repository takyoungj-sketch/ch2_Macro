# -*- coding: utf-8 -*-
"""Jeonbuk 52 raw vs tx deep dive."""
from sqlalchemy import text
from db_utils import get_engine

e = get_engine()
with e.connect() as c:
    # Jeonbuk raw by deal year
    rows = c.execute(
        text(
            """
            SELECT LEFT(r.raw_data->>'deal_ymd', 4) AS yr, COUNT(1) AS n,
                   SUM(CASE WHEN EXISTS (
                     SELECT 1 FROM land_transactions lt WHERE lt.raw_id = r.id
                   ) THEN 1 ELSE 0 END) AS linked
            FROM land_transactions_raw r
            WHERE COALESCE(r.raw_data->>'sigungu_name', '') LIKE '전%'
              AND (
                r.raw_data->>'sigungu_name' LIKE '전라북도%'
                OR r.raw_data->>'sigungu_name' LIKE '전북특별자치도%'
              )
            GROUP BY 1 ORDER BY 1
            """
        )
    ).fetchall()
    print("Jeonbuk raw by deal year (linked/total):")
    for r in rows:
        print(f"  {r[0]}: linked={r[2]}/{r[1]}")

    sample = c.execute(
        text(
            """
            SELECT r.id, r.loaded_at::date, r.raw_data->>'sigungu_name' AS addr,
                   r.raw_data->>'deal_ymd' AS ymd
            FROM land_transactions_raw r
            WHERE r.raw_data->>'sigungu_name' LIKE '전라북도%'
               OR r.raw_data->>'sigungu_name' LIKE '전북특별자치도%'
            ORDER BY r.id LIMIT 5
            """
        )
    ).fetchall()
    print("\nSample Jeonbuk raw:")
    for s in sample:
        print(s)

    unproc2010 = c.execute(
        text(
            """
            SELECT COUNT(1) FROM land_transactions_raw r
            WHERE r.raw_data->>'deal_ymd' LIKE '2010%'
              AND (
                r.raw_data->>'sigungu_name' LIKE '전라북도%'
                OR r.raw_data->>'sigungu_name' LIKE '전북특별자치도%'
              )
              AND NOT EXISTS (
                SELECT 1 FROM land_transactions lt WHERE lt.raw_id = r.id
              )
            """
        )
    ).scalar()
    print("\nunprocessed Jeonbuk 2010 raw:", unproc2010)

    # hash collision: unprocessed raw whose hash exists in lt
    from clean import clean_dataframe, build_region_lookup, map_beopjungri_codes
    import pandas as pd

    raw_rows = c.execute(
        text(
            """
            SELECT r.id, r.raw_data
            FROM land_transactions_raw r
            WHERE r.raw_data->>'deal_ymd' LIKE '2010%'
              AND r.raw_data->>'sigungu_name' LIKE '전라북도%'
            LIMIT 200
            """
        )
    ).fetchall()
    recs = [{"_raw_id": r[0], "_source_year": 2010, "_source_month": 1, **r[1]} for r in raw_rows]
    df = pd.DataFrame(recs)
    cleaned = clean_dataframe(df)
    lookup = build_region_lookup(e)
    mapped = map_beopjungri_codes(cleaned, lookup)
    cleaned["beopjungri_code"] = mapped["beopjungri_code"].values
    mapped_ok = cleaned["beopjungri_code"].astype(str).str.startswith("52").sum()
    print(f"\n2010 전라북 sample map to 52: {mapped_ok}/{len(cleaned)}")
    print("mapping notes:", mapped["mapping_notes"].value_counts().head().to_dict())
    if mapped_ok < len(cleaned):
        bad = cleaned[~cleaned["beopjungri_code"].astype(str).str.startswith("52")]
        print("bad addr sample:", bad["sigungu_name"].head(3).tolist())
