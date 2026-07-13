# -*- coding: utf-8 -*-
"""면↔읍 승격으로 region_codes 표기와 거래 원장 표기가 어긋난 건을 수리한다.

- region_codes: 거래에 쓰인 읍/면 표기로 이름 갱신 (코드는 유지)
- built_transactions: NULL 행정코드를 마스터에서 백필
- land_stats.region_codes 도 동일 이름 갱신 (있으면)

Usage:
  cd backend && python ../pipeline/repair_eup_myeon_promotion.py
  python ../pipeline/repair_eup_myeon_promotion.py --dry-run
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "pipeline"))


def _engines():
    from app.config import settings

    built = create_engine(settings.built_database_url)
    land = create_engine(settings.database_url)
    return built, land


def find_mismatches(conn):
    return conn.execute(
        text(
            """
            WITH tx AS (
              SELECT addr1, addr2,
                     COALESCE(NULLIF(btrim(addr4),''), NULLIF(btrim(addr3),'')) AS leaf,
                     COUNT(*) AS n
              FROM built_transactions
              WHERE is_valid
                AND (eupmyeondong_code IS NULL OR btrim(eupmyeondong_code::text) = '')
                AND COALESCE(NULLIF(btrim(addr4),''), NULLIF(btrim(addr3),'')) ~ '[읍면]$'
              GROUP BY 1, 2, 3
            )
            SELECT t.addr1, t.addr2, t.leaf, t.n,
                   rc.eupmyeondong_code, rc.eupmyeondong_name,
                   rc.sido_code, rc.sigungu_code
            FROM tx t
            JOIN LATERAL (
              SELECT DISTINCT ON (eupmyeondong_code)
                     eupmyeondong_code, eupmyeondong_name, sido_code, sigungu_code
              FROM region_codes
              WHERE COALESCE(is_active, true)
                AND sido_name = t.addr1
                AND sigungu_name = t.addr2
                AND right(t.leaf, 1) IN ('읍', '면')
                AND left(eupmyeondong_name, greatest(length(t.leaf) - 1, 0))
                    = left(t.leaf, greatest(length(t.leaf) - 1, 0))
                AND right(eupmyeondong_name, 1) IN ('읍', '면')
                AND right(eupmyeondong_name, 1) <> right(t.leaf, 1)
              ORDER BY eupmyeondong_code
            ) rc ON true
            ORDER BY t.n DESC
            """
        )
    ).mappings().all()


def rename_region_codes(conn, *, addr1: str, addr2: str, old_name: str, new_name: str, dry: bool) -> int:
    """마스터 읍면동 이름을 거래 표기에 맞춤."""
    sql = text(
        """
        UPDATE region_codes
        SET eupmyeondong_name = :new_name,
            updated_at = NOW()
        WHERE COALESCE(is_active, true)
          AND sido_name = :a1
          AND sigungu_name = :a2
          AND eupmyeondong_name = :old_name
        """
    )
    if dry:
        n = conn.execute(
            text(
                """
                SELECT COUNT(*) FROM region_codes
                WHERE COALESCE(is_active, true)
                  AND sido_name = :a1 AND sigungu_name = :a2
                  AND eupmyeondong_name = :old_name
                """
            ),
            {"a1": addr1, "a2": addr2, "old_name": old_name},
        ).scalar()
        return int(n or 0)
    return int(
        conn.execute(
            sql,
            {"a1": addr1, "a2": addr2, "old_name": old_name, "new_name": new_name},
        ).rowcount
        or 0
    )


def backfill_tx(conn, row, *, dry: bool) -> int:
    params = {
        "a1": row["addr1"],
        "a2": row["addr2"],
        "leaf": row["leaf"],
        "emd": row["eupmyeondong_code"],
        "sido": str(row["sido_code"] or "")[:2],
        "sig": str(row["sigungu_code"] or "")[:5],
    }
    if dry:
        n = conn.execute(
            text(
                """
                SELECT COUNT(*) FROM built_transactions
                WHERE is_valid
                  AND addr1 = :a1 AND addr2 = :a2
                  AND (addr3 = :leaf OR addr4 = :leaf)
                  AND (eupmyeondong_code IS NULL OR btrim(eupmyeondong_code::text) = '')
                """
            ),
            params,
        ).scalar()
        return int(n or 0)
    return int(
        conn.execute(
            text(
                """
                UPDATE built_transactions
                SET eupmyeondong_code = :emd,
                    sido_code = COALESCE(NULLIF(btrim(sido_code::text), ''), :sido),
                    sigungu_code = COALESCE(NULLIF(btrim(sigungu_code::text), ''), :sig)
                WHERE is_valid
                  AND addr1 = :a1 AND addr2 = :a2
                  AND (addr3 = :leaf OR addr4 = :leaf)
                  AND (eupmyeondong_code IS NULL OR btrim(eupmyeondong_code::text) = '')
                """
            ),
            params,
        ).rowcount
        or 0
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    built_eng, land_eng = _engines()

    with built_eng.begin() as conn:
        rows = find_mismatches(conn)
        print(f"mismatches={len(rows)}")
        total_rc = total_tx = 0
        for r in rows:
            old = r["eupmyeondong_name"]
            new = r["leaf"]
            print(
                f"  {r['addr1']} {r['addr2']}: {old} → {new} "
                f"code={r['eupmyeondong_code']} tx_null={r['n']}"
            )
            n_rc = rename_region_codes(
                conn,
                addr1=r["addr1"],
                addr2=r["addr2"],
                old_name=old,
                new_name=new,
                dry=args.dry_run,
            )
            n_tx = backfill_tx(conn, r, dry=args.dry_run)
            total_rc += n_rc
            total_tx += n_tx
            print(f"    region_codes rows={n_rc}  tx backfill={n_tx}")

        if args.dry_run:
            conn.rollback()
        print(f"built region_codes updated~={total_rc}  tx backfilled~={total_tx}")

    # land_stats master 이름 동기
    try:
        with land_eng.begin() as conn:
            # land may not have built_transactions; only rename known pairs from built scan
            with built_eng.connect() as bconn:
                # re-read current names after built update
                pairs = bconn.execute(
                    text(
                        """
                        SELECT DISTINCT sido_name, sigungu_name, eupmyeondong_name, eupmyeondong_code
                        FROM region_codes
                        WHERE eupmyeondong_code = ANY(:codes)
                        """
                    ),
                    {"codes": [r["eupmyeondong_code"] for r in rows] or ["__none__"]},
                ).mappings().all()
            n_land = 0
            for p in pairs:
                # if land still has 면 while built now has 읍 (or vice versa), sync land to built name
                n = conn.execute(
                    text(
                        """
                        UPDATE region_codes
                        SET eupmyeondong_name = :new_name,
                            updated_at = NOW()
                        WHERE COALESCE(is_active, true)
                          AND eupmyeondong_code = :code
                          AND eupmyeondong_name <> :new_name
                          AND right(eupmyeondong_name, 1) IN ('읍','면')
                          AND left(eupmyeondong_name, greatest(length(:new_name)-1, 0))
                              = left(:new_name, greatest(length(:new_name)-1, 0))
                        """
                    ),
                    {
                        "code": p["eupmyeondong_code"],
                        "new_name": p["eupmyeondong_name"],
                    },
                ).rowcount
                n_land += int(n or 0)
            if args.dry_run:
                conn.rollback()
            print(f"land region_codes name sync~={n_land}")
    except Exception as e:
        print(f"land sync skipped: {e}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
