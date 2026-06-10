# -*- coding: utf-8 -*-
"""Detect apt-like vs land-like raw rows for suspicious source_year batches."""
from sqlalchemy import text
from db_utils import get_engine

e = get_engine()
with e.connect() as c:
    for sy, desc in [(2014, "전북파일=전남아파트"), (2017, "전남파일=경기아파트")]:
        rows = c.execute(
            text(
                """
                SELECT
                  COUNT(1) FILTER (WHERE raw_data->>'sigungu_name' LIKE '전북%') AS jb,
                  COUNT(1) FILTER (WHERE raw_data->>'sigungu_name' LIKE '전라남도%') AS jn,
                  COUNT(1) FILTER (WHERE raw_data->>'sigungu_name' LIKE '경기%') AS gg,
                  COUNT(1) FILTER (WHERE raw_data ? 'land_category') AS has_land_cat,
                  COUNT(1) FILTER (WHERE raw_data ? 'zone_type') AS has_zone,
                  COUNT(1) FILTER (WHERE raw_data ? 'building_name' OR raw_data ? 'apt_name') AS has_apt,
                  COUNT(1) AS total
                FROM land_transactions_raw
                WHERE source_year = :sy AND source_month = 6
                """
            ),
            {"sy": sy},
        ).fetchone()
        print(f"source_year={sy} ({desc}): total={rows[6]}")
        print(f"  addr jb={rows[0]} jn={rows[1]} gg={rows[2]}")
        print(f"  keys land_cat={rows[3]} zone={rows[4]} apt={rows[5]}")

        sample = c.execute(
            text(
                """
                SELECT raw_data->>'sigungu_name' AS addr,
                       raw_data->>'deal_ymd' AS ymd,
                       LEFT(raw_data::text, 120) AS raw_snip
                FROM land_transactions_raw
                WHERE source_year = :sy AND source_month = 6
                  AND raw_data->>'sigungu_name' LIKE '전라남도%'
                LIMIT 2
                """
            ),
            {"sy": sy},
        ).fetchall()
        if sample:
            print("  sample 전라남도 addr:", sample)
