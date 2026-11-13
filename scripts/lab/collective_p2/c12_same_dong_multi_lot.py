"""Phase C-12 (범위 밖 규모 측정) — 한 단지 키 안, 같은 법정동인데 지번이 다른 거래 묶음이 2개 이상인 키.

이름 키(sha256(유형|시도|시군구|읍면동|이름))는 같은 동 안 동명 다른 건물을 한 키로 묶는다(이번 분할은 동이 다를 때만).
리허설 DB(collective_stats_p2r) 읽기 전용, 쿼리 제한 30분. 유효 거래·지번 있는 행만.
- 느슨: 같은 (키, 유형, 법정동 10자리) 안 지번 2개 이상
- 엄격: 그중 거래 3건 이상인 지번이 2개 이상(지번 오기·드문 행 제외)
출력: 표준출력(markdown, 지번 없음) + logs/collective_p2/c12_same_dong_multi_lot_sample.csv (표본 20, 지번 포함, gitignore)
"""
from __future__ import annotations

import pandas as pd
from sqlalchemy import text

from _db import OUT, engine_db, md_table

SQL = """
WITH g AS (
    SELECT building_key, asset_type, beopjungri_code, lot_number, count(*) AS n
    FROM collective_transactions
    WHERE is_valid AND beopjungri_code IS NOT NULL AND COALESCE(btrim(lot_number), '') <> ''
    GROUP BY 1, 2, 3, 4
), d AS (
    SELECT building_key, asset_type, beopjungri_code,
           count(*) AS lots, count(*) FILTER (WHERE n >= 3) AS lots3, sum(n) AS tx
    FROM g GROUP BY 1, 2, 3
)
SELECT asset_type,
       count(DISTINCT building_key) FILTER (WHERE lots >= 2)  AS keys_loose,
       sum(tx) FILTER (WHERE lots >= 2)                        AS tx_loose,
       count(DISTINCT building_key) FILTER (WHERE lots3 >= 2) AS keys_strict,
       sum(tx) FILTER (WHERE lots3 >= 2)                       AS tx_strict,
       count(DISTINCT building_key)                            AS keys_all,
       sum(tx)                                                 AS tx_all
FROM d GROUP BY 1 ORDER BY 1
"""

SAMPLE = """
WITH g AS (
    SELECT building_key, asset_type, beopjungri_code, lot_number, count(*) AS n, max(display_name) AS name
    FROM collective_transactions
    WHERE is_valid AND beopjungri_code IS NOT NULL AND COALESCE(btrim(lot_number), '') <> ''
    GROUP BY 1, 2, 3, 4
), d AS (
    SELECT building_key, asset_type, beopjungri_code, max(name) AS name,
           string_agg(lot_number || ':' || n, ' / ' ORDER BY n DESC) AS lots, count(*) AS n_lots, sum(n) AS tx
    FROM g WHERE n >= 3 GROUP BY 1, 2, 3 HAVING count(*) >= 2
)
SELECT * FROM d ORDER BY md5(building_key || '20261113') LIMIT 20
"""


def main():
    eng = engine_db("collective_stats_p2r", timeout_ms=1_800_000)
    with eng.connect() as c:
        assert c.execute(text("select current_database()")).scalar() == "collective_stats_p2r"
        df = pd.read_sql(text(SQL), c)
        sample = pd.read_sql(text(SAMPLE), c)
    sample.to_csv(OUT / "c12_same_dong_multi_lot_sample.csv", index=False, encoding="utf-8-sig")
    tot = df.drop(columns="asset_type").sum()
    rows = [tuple(int(v) if pd.notna(v) else 0 for v in r[1:]) for r in df.itertuples(index=False)]
    rows = [(a, *r) for a, r in zip(df["asset_type"], rows)] + [("합계", *(int(v) for v in tot.values))]
    print(md_table(rows, ["유형", "키(느슨)", "거래(느슨)", "키(엄격)", "거래(엄격)", "전체 키", "전체 거래"]))
    print(f"\n표본 {len(sample)}건 → logs/collective_p2/c12_same_dong_multi_lot_sample.csv")


if __name__ == "__main__":
    main()
