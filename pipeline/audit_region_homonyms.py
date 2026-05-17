"""
region_codes 동명이인·약한 키 진단 (DB 읽기 전용).

  cd pipeline
  .\\.venv\\Scripts\\python.exe audit_region_homonyms.py
  .\\.venv\\Scripts\\python.exe audit_region_homonyms.py --names 대장동,신촌동,중동

출력: 시도·시군구·읍면동·법정명·코드, 동일 (sido_code, beopjungri_name) 다중 코드 요약.
"""

from __future__ import annotations

import argparse
import os

from sqlalchemy import text

from db_utils import get_engine

DEFAULT_NAMES = (
    "대장동",
    "신촌동",
    "중동",
    "본동",
    "장동",
    "덕은동",
)


def main() -> None:
    parser = argparse.ArgumentParser(description="region_codes 동명이인 점검")
    parser.add_argument(
        "--names",
        type=str,
        default=",".join(DEFAULT_NAMES),
        help="쉼표 구분 beopjungri_name 후보",
    )
    args = parser.parse_args()
    names = [n.strip() for n in args.names.split(",") if n.strip()]
    if not names:
        print("names 비어 있음")
        return

    eng = get_engine()
    with eng.connect() as conn:
        dup_sql = text(
            """
            SELECT sido_code::text AS sc,
                   beopjungri_name::text AS bn,
                   COUNT(DISTINCT beopjungri_code) AS n_codes,
                   COUNT(*) AS n_rows
            FROM region_codes
            WHERE COALESCE(is_active, TRUE)
            GROUP BY 1, 2
            HAVING COUNT(DISTINCT beopjungri_code) > 1
            ORDER BY n_codes DESC, sc, bn
            LIMIT 200
            """
        )
        print("=== (sido_code, beopjungri_name) 다중 법정코드 (상위 200) ===")
        for r in conn.execute(dup_sql).mappings():
            print(dict(r))

        print("\n=== 지정 동명 상세 (전국, is_active) ===")
        detail = text(
            """
            SELECT sido_code, sido_name, sigungu_name, eupmyeondong_name,
                   beopjungri_name, beopjungri_code::text AS bc
            FROM region_codes
            WHERE COALESCE(is_active, TRUE)
              AND beopjungri_name = ANY(:names)
            ORDER BY sido_code, sigungu_name, beopjungri_code
            """
        )
        for r in conn.execute(detail, {"names": names}).mappings():
            print(dict(r))


if __name__ == "__main__":
    if not os.environ.get("DATABASE_URL"):
        print("DATABASE_URL 필요 (pipeline/.env)")
    main()
