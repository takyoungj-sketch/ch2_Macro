#!/usr/bin/env python3
"""
land_transactions 중복 행 제거 + (선택) transaction_hash 재계산.

배경: 2026-05 이전 hash 에 Excel 순번/raw_id 가 포함되어 동일 거래가
여러 번 INSERT 된 상태. 2026-06 월간 갱신 전 로컬 DB 에 1회 실행.

사용 (로컬, DATABASE_URL 필수):
    cd pipeline
    python dedupe_land_transactions.py --dry-run
    python dedupe_land_transactions.py --execute
    python dedupe_land_transactions.py --execute --rehash

이후: build_stats_v2 / upper / twin 재집계 → pg_dump Promote.
"""

from __future__ import annotations

import argparse
import logging
import sys

from sqlalchemy import text

from db_utils import get_engine
from transaction_hash import hash_from_series, make_transaction_hash, transaction_hash_key

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

# 회귀 샘플 — 청주 비하동 보녹·답 (엑셀 2건)
SAMPLE_BIHA_SQL = """
SELECT COUNT(*) FROM land_transactions lt
JOIN region_codes rc ON rc.beopjungri_code = lt.beopjungri_code
WHERE rc.beopjungri_code = '4311313800'
  AND lt.zone_type = '보녹' AND lt.land_category = '답'
  AND lt.is_valid = TRUE
"""

DEDUPE_STATS_SQL = """
SELECT COUNT(*) AS dup_groups,
       COALESCE(SUM(cnt - 1), 0)::bigint AS extra_rows
FROM (
  SELECT COUNT(*) AS cnt
  FROM land_transactions
  WHERE is_valid = TRUE
  GROUP BY beopjungri_code, contract_date, area_sqm, total_price_10k,
           COALESCE(land_category, ''), COALESCE(zone_type, ''), is_cancelled
  HAVING COUNT(*) > 1
) s
"""

DELETE_DUPES_SQL = """
DELETE FROM land_transactions lt
WHERE lt.id IN (
  SELECT id FROM (
    SELECT id,
           ROW_NUMBER() OVER (
             PARTITION BY beopjungri_code, contract_date, area_sqm, total_price_10k,
                          COALESCE(land_category, ''), COALESCE(zone_type, ''), is_cancelled
             ORDER BY id ASC
           ) AS rn
    FROM land_transactions
    WHERE is_valid = TRUE
  ) ranked
  WHERE rn > 1
)
"""


def _count(conn, sql: str) -> int:
    return int(conn.execute(text(sql)).scalar() or 0)


def _dup_stats(conn) -> tuple[int, int]:
    row = conn.execute(text(DEDUPE_STATS_SQL)).one()
    return int(row.dup_groups or 0), int(row.extra_rows or 0)


def _report(conn, label: str) -> None:
    total = _count(conn, "SELECT COUNT(*) FROM land_transactions")
    biha = _count(conn, SAMPLE_BIHA_SQL)
    groups, extra = _dup_stats(conn)
    log.info(
        "%s: land_transactions=%s, biha_borok_dap_valid=%s, dup_groups=%s, extra_rows=%s",
        label,
        f"{total:,}",
        biha,
        f"{groups:,}",
        f"{extra:,}",
    )


def _rehash_all(conn, *, batch: int = 5000) -> int:
    """남은 행의 transaction_hash 를 신규 공식으로 UPDATE."""
    has_lot_display = conn.execute(
        text(
            """
            SELECT EXISTS (
              SELECT 1 FROM information_schema.columns
              WHERE table_name = 'land_transactions' AND column_name = 'lot_display'
            )
            """
        )
    ).scalar()

    lot_col = "lot_display" if has_lot_display else "NULL::varchar"

    offset = 0
    updated = 0
    while True:
        rows = conn.execute(
            text(
                f"""
                SELECT id, beopjungri_code, sigungu_code,
                       contract_year, contract_month, contract_date,
                       {lot_col} AS lot_display,
                       area_sqm, total_price_10k, is_cancelled, transaction_hash
                FROM land_transactions
                ORDER BY id
                LIMIT :lim OFFSET :off
                """
            ),
            {"lim": batch, "off": offset},
        ).all()
        if not rows:
            break
        for r in rows:
            day = r.contract_date.day if r.contract_date else ""
            key = transaction_hash_key(
                beopjungri_code=r.beopjungri_code,
                sigungu_code=r.sigungu_code,
                contract_year=r.contract_year,
                contract_month=r.contract_month,
                contract_day=day,
                lot_display=getattr(r, "lot_display", None),
                area_sqm=r.area_sqm,
                total_price_10k=r.total_price_10k,
                is_cancelled=bool(r.is_cancelled),
            )
            new_hash = make_transaction_hash(key)
            if new_hash == r.transaction_hash:
                continue
            existing_id = conn.execute(
                text(
                    "SELECT id FROM land_transactions WHERE transaction_hash = :h LIMIT 1"
                ),
                {"h": new_hash},
            ).scalar()
            if existing_id is not None and int(existing_id) != int(r.id):
                conn.execute(
                    text("DELETE FROM land_transactions WHERE id = :id"),
                    {"id": int(r.id)},
                )
                updated += 1
                continue
            conn.execute(
                text("UPDATE land_transactions SET transaction_hash = :h WHERE id = :id"),
                {"h": new_hash, "id": int(r.id)},
            )
            updated += 1
        offset += batch
        log.info("rehash progress: scanned %s rows, updated %s", f"{offset:,}", f"{updated:,}")
    return updated


def main() -> int:
    parser = argparse.ArgumentParser(description="land_transactions 중복 제거")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="삭제·UPDATE 없이 통계만 (기본)",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="중복 DELETE 실행",
    )
    parser.add_argument(
        "--rehash",
        action="store_true",
        help="--execute 와 함께: 남은 행 transaction_hash 재계산",
    )
    args = parser.parse_args()
    if not args.execute:
        args.dry_run = True

    engine = get_engine()
    with engine.begin() as conn:
        _report(conn, "before")
        if args.dry_run and not args.execute:
            log.info("dry-run — 변경 없음. 실행: python dedupe_land_transactions.py --execute [--rehash]")
            return 0

        deleted = conn.execute(text(DELETE_DUPES_SQL)).rowcount
        log.info("deleted duplicate rows: %s", deleted if deleted is not None else "?")
        _report(conn, "after dedupe")

        if args.rehash:
            n = _rehash_all(conn)
            log.info("rehash updated rows: %s", f"{n:,}")
            _report(conn, "after rehash")

        biha = _count(conn, SAMPLE_BIHA_SQL)
        if biha != 2:
            log.warning(
                "회귀 샘플 비하동 보녹·답 valid=%s (기대 2). 수동 확인 필요.", biha
            )
        else:
            log.info("회귀 샘플 OK: 비하동 보녹·답 = 2건")

    log.info(
        "다음: build_stats_v2 / build_upper_stats_v2 / twin 배치 재실행 → Promote. "
        "docs/TRANSACTION_HASH_DEDUPE.md 참고."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
