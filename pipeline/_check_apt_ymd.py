# -*- coding: utf-8 -*-
from sqlalchemy import text
from db_utils import get_engine

e = get_engine()
with e.connect() as c:
    for sy in (2014, 2016, 2017, 2020):
        r = c.execute(
            text(
                """
                SELECT
                  COUNT(1) FILTER (WHERE raw_data->>'deal_ymd' LIKE '2026%') AS y2026,
                  COUNT(1) FILTER (WHERE raw_data->>'deal_ymd' LIKE '2024%') AS y2024,
                  COUNT(1) FILTER (WHERE raw_data->>'deal_ymd' ~ '^[0-9]{6}$'
                                   AND LEFT(raw_data->>'deal_ymd',4)::int = :sy) AS y_match,
                  COUNT(1) AS total
                FROM land_transactions_raw
                WHERE source_year = :sy AND source_month = 6
                """
            ),
            {"sy": sy},
        ).one()
        print(f"source {sy}: total={r[3]} deal_yr_match={r[2]} y2026={r[0]} y2024={r[1]}")
