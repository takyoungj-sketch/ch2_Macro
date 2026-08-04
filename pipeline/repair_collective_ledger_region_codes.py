#!/usr/bin/env python3
"""Backfill collective_transactions region codes when eup is NULL (구·읍 addr4 grain).

용인시 처인구·양지읍 등: ledger eupmyeondong_code NULL → market_stats·profile 집합 유형 누락.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))

from dotenv import load_dotenv

load_dotenv(ROOT / "backend" / ".env", override=True)
load_dotenv(ROOT / "pipeline" / ".env.collective")
load_dotenv()

from sqlalchemy import text

from collective.db_utils import get_collective_engine

_EUP_NAME = """
CASE
    WHEN btrim(COALESCE(t.addr4::text, '')) <> ''
         AND btrim(COALESCE(t.addr3::text, '')) LIKE '%구'
    THEN t.addr4
    ELSE t.addr3
END
"""

UPDATE_SQL = f"""
UPDATE collective_transactions t
SET
    beopjungri_code = COALESCE(NULLIF(btrim(t.beopjungri_code::text), ''), m.beopjungri_code),
    eupmyeondong_code = m.eupmyeondong_code,
    sigungu_code = m.sigungu_code,
    sido_code = m.sido_code
FROM (
    SELECT t2.transaction_hash,
           rc.eupmyeondong_code,
           rc.sigungu_code,
           rc.sido_code,
           rc.beopjungri_code
    FROM collective_transactions t2
    JOIN LATERAL (
        SELECT eupmyeondong_code, sigungu_code, sido_code, beopjungri_code
        FROM region_codes rc
        WHERE COALESCE(rc.is_active, TRUE)
          AND rc.sido_name = t2.addr1
          AND (
                rc.sigungu_name = t2.addr2
             OR rc.sigungu_name = t2.addr2 || ' ' || t2.addr3
          )
          AND rc.eupmyeondong_name = ({_EUP_NAME.replace("t.", "t2.")})
        LIMIT 1
    ) rc ON TRUE
    WHERE (t2.eupmyeondong_code IS NULL OR btrim(t2.eupmyeondong_code::text) = '')
      AND rc.eupmyeondong_code IS NOT NULL
      {{sido_clause}}
) m
WHERE t.transaction_hash = m.transaction_hash
"""


def main() -> None:
    p = argparse.ArgumentParser(description="collective_transactions region code backfill")
    p.add_argument("--sido-code", help="limit to sido prefix (e.g. 41)")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    sido_clause = ""
    dry_sido_clause = ""
    params: dict = {}
    if args.sido_code:
        sido_clause = "AND t2.addr1 IN (SELECT DISTINCT sido_name FROM region_codes WHERE sido_code = :sido)"
        dry_sido_clause = "AND t.addr1 IN (SELECT DISTINCT sido_name FROM region_codes WHERE sido_code = :sido)"
        params["sido"] = args.sido_code

    eng = get_collective_engine()
    sql = UPDATE_SQL.format(sido_clause=sido_clause)
    with eng.connect() as conn:
        if args.dry_run:
            count = conn.execute(
                text(
                    f"""
                    SELECT COUNT(*) FROM collective_transactions t
                    LEFT JOIN LATERAL (
                        SELECT eupmyeondong_code FROM region_codes rc
                        WHERE COALESCE(rc.is_active, TRUE)
                          AND rc.sido_name = t.addr1
                          AND (rc.sigungu_name = t.addr2 OR rc.sigungu_name = t.addr2 || ' ' || t.addr3)
                          AND rc.eupmyeondong_name = ({_EUP_NAME})
                        LIMIT 1
                    ) rc ON TRUE
                    WHERE (t.eupmyeondong_code IS NULL OR btrim(t.eupmyeondong_code::text) = '')
                      AND rc.eupmyeondong_code IS NOT NULL
                      {dry_sido_clause}
                    """
                ),
                params,
            ).scalar()
            print(f"dry-run: would update {count} rows")
            return
        with conn.begin():
            res = conn.execute(text(sql), params)
            print(f"updated {res.rowcount} rows")


if __name__ == "__main__":
    main()
