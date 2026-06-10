# -*- coding: utf-8 -*-
"""Check if bad CSV batches were ingested into land_transactions_raw."""
from sqlalchemy import text
from db_utils import get_engine

# source_year from filename, expected sido prefix in addresses
CHECKS = [
    (2014, "52", "전북", "전북특별자치도_토지_매매_2014.csv"),
    (2017, "46", "전남", "전라남도_토지_매매_2017.csv"),
    (2011, "48", "경남", "경상남도_토지_매매_2011.csv"),
    (2016, "52", "전북", "전북특별자치도_토지_매매_2016.csv"),
    (2020, "52", "전북", "전북특별자치도_토지_매매_2020.csv"),
]

e = get_engine()
with e.connect() as c:
    for sy, sido, label, fname in CHECKS:
        # raw batch for source_year with wrong-address pattern (apt: has 단지-like, not land)
        n = c.execute(
            text(
                """
                SELECT COUNT(1) FROM land_transactions_raw r
                WHERE r.source_year = :sy AND r.source_month = 6
                  AND (
                    r.raw_data ? 'apt_name'
                    OR r.raw_data->>'apt_name' IS NOT NULL
                    OR r.raw_data ? 'building_name'
                    OR (r.raw_data->>'sigungu_name' LIKE :jeonnam AND :sido = '52')
                    OR (r.raw_data->>'sigungu_name' LIKE :gyeonggi AND :sido = '46')
                  )
                """
            ),
            {
                "sy": sy,
                "sido": sido,
                "jeonnam": "전라남도%",
                "gyeonggi": "경기%",
            },
        ).scalar()
        total = c.execute(
            text(
                """
                SELECT COUNT(1) FROM land_transactions_raw
                WHERE source_year = :sy AND source_month = 6
                """
            ),
            {"sy": sy},
        ).scalar()
        # apt column in raw json from collect?
        sample = c.execute(
            text(
                """
                SELECT jsonb_object_keys(raw_data) AS k
                FROM land_transactions_raw
                WHERE source_year = :sy AND source_month = 6
                LIMIT 1
                """
            ),
            {"sy": sy},
        ).fetchall()
        keys = [r[0] for r in sample] if sample else []
        landish = "land_category" in keys or "zone_type" in keys
        aptish = "apt_name" in keys or "building_name" in keys or "floor" in keys
        print(f"{label} source_year={sy}: raw rows={total}, land_keys={landish}, apt_keys={aptish}, keys_sample={keys[:8]}")
