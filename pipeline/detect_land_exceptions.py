#!/usr/bin/env python3
"""
토지 거래 예외 탐지 → land_exception_queue 적재

탐지 항목:
  E-1 zone_type 충돌: 같은 (법정동, 계약일, 면적, 금액) 에 zone_type이 2가지 이상
  E-2 land_category 충돌: 같은 키에 land_category가 2가지 이상

원칙:
  - land_transactions(Master)는 수정하지 않는다.
  - 이미 queue에 있는 그룹(pending/resolved)은 재등록하지 않는다.
  - dismissed 된 그룹은 재등록하지 않는다.

사용:
  cd pipeline
  python detect_land_exceptions.py --dry-run          # 탐지만, DB 미변경
  python detect_land_exceptions.py --execute           # queue 적재
  python detect_land_exceptions.py --execute --since 2021-01-01   # 날짜 하한

이후:
  land_exception_queue 에서 pending 행을 검토 →
  land_correction_rules 에 Rule 등록 →
  status = 'resolved' 로 갱신
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date, datetime, timezone

from sqlalchemy import text

from db_utils import get_engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

DEFAULT_SINCE = date(2021, 1, 1)


# ---------------------------------------------------------------------------
# SQL
# ---------------------------------------------------------------------------

_ZONE_CONFLICT_SQL = """
SELECT
    lt.beopjungri_code,
    lt.contract_date,
    lt.area_sqm,
    lt.total_price_10k,
    array_agg(DISTINCT lt.zone_type ORDER BY lt.zone_type)  AS zones,
    array_agg(lt.id              ORDER BY lt.id)            AS tx_ids,
    array_agg(lt.raw_id          ORDER BY lt.id)            AS raw_ids,
    array_agg(lt.lot_display     ORDER BY lt.id)            AS lot_displays,
    COUNT(*)                                                 AS cnt
FROM land_transactions lt
WHERE lt.is_valid = TRUE
  AND lt.contract_date >= :since
GROUP BY
    lt.beopjungri_code,
    lt.contract_date,
    lt.area_sqm,
    lt.total_price_10k
HAVING COUNT(DISTINCT lt.zone_type) > 1
ORDER BY lt.beopjungri_code, lt.contract_date
"""

_LAND_CAT_CONFLICT_SQL = """
SELECT
    lt.beopjungri_code,
    lt.contract_date,
    lt.area_sqm,
    lt.total_price_10k,
    array_agg(DISTINCT lt.land_category ORDER BY lt.land_category) AS cats,
    array_agg(lt.id                     ORDER BY lt.id)            AS tx_ids,
    array_agg(lt.raw_id                 ORDER BY lt.id)            AS raw_ids,
    array_agg(lt.lot_display            ORDER BY lt.id)            AS lot_displays,
    COUNT(*)                                                        AS cnt
FROM land_transactions lt
WHERE lt.is_valid = TRUE
  AND lt.contract_date >= :since
GROUP BY
    lt.beopjungri_code,
    lt.contract_date,
    lt.area_sqm,
    lt.total_price_10k
HAVING COUNT(DISTINCT lt.land_category) > 1
ORDER BY lt.beopjungri_code, lt.contract_date
"""

_EXISTING_KEYS_SQL = """
SELECT beopjungri_code, contract_date, area_sqm::text, total_price_10k::text, conflict_type
FROM land_exception_queue
WHERE status != 'dismissed'
"""

_INSERT_EXCEPTION_SQL = """
INSERT INTO land_exception_queue (
    tx_ids, raw_ids,
    beopjungri_code, contract_date, area_sqm, total_price_10k, lot_display,
    conflict_type, conflict_values,
    status, detected_at, detect_batch
) VALUES (
    :tx_ids, :raw_ids,
    :beopjungri_code, :contract_date, :area_sqm, :total_price_10k, :lot_display,
    :conflict_type, :conflict_values,
    'pending', NOW(), :batch_id
)
ON CONFLICT (beopjungri_code, contract_date, area_sqm, total_price_10k, conflict_type)
    WHERE status != 'dismissed'
DO NOTHING
"""


# ---------------------------------------------------------------------------
# 탐지 함수
# ---------------------------------------------------------------------------

def _existing_keys(conn) -> set[tuple]:
    rows = conn.execute(text(_EXISTING_KEYS_SQL)).fetchall()
    return {
        (r.beopjungri_code, str(r.contract_date), str(r.area_sqm), str(r.total_price_10k), r.conflict_type)
        for r in rows
    }


def _detect_zone_conflicts(conn, since: date, existing: set[tuple]) -> list[dict]:
    rows = conn.execute(text(_ZONE_CONFLICT_SQL), {"since": since}).fetchall()
    new: list[dict] = []
    for r in rows:
        key = (r.beopjungri_code, str(r.contract_date), str(r.area_sqm), str(r.total_price_10k), "zone_type")
        if key in existing:
            continue
        lot_displays = [ld for ld in (r.lot_displays or []) if ld]
        lot = lot_displays[0] if lot_displays else None
        new.append({
            "tx_ids": list(r.tx_ids),
            "raw_ids": [rid for rid in (r.raw_ids or []) if rid is not None],
            "beopjungri_code": r.beopjungri_code,
            "contract_date": r.contract_date,
            "area_sqm": float(r.area_sqm),
            "total_price_10k": float(r.total_price_10k),
            "lot_display": lot,
            "conflict_type": "zone_type",
            "conflict_values": json.dumps({"zone_type": list(r.zones), "tx_ids": list(r.tx_ids)}, ensure_ascii=False),
        })
    return new


def _detect_land_cat_conflicts(conn, since: date, existing: set[tuple]) -> list[dict]:
    rows = conn.execute(text(_LAND_CAT_CONFLICT_SQL), {"since": since}).fetchall()
    new: list[dict] = []
    for r in rows:
        key = (r.beopjungri_code, str(r.contract_date), str(r.area_sqm), str(r.total_price_10k), "land_category")
        if key in existing:
            continue
        lot_displays = [ld for ld in (r.lot_displays or []) if ld]
        lot = lot_displays[0] if lot_displays else None
        new.append({
            "tx_ids": list(r.tx_ids),
            "raw_ids": [rid for rid in (r.raw_ids or []) if rid is not None],
            "beopjungri_code": r.beopjungri_code,
            "contract_date": r.contract_date,
            "area_sqm": float(r.area_sqm),
            "total_price_10k": float(r.total_price_10k),
            "lot_display": lot,
            "conflict_type": "land_category",
            "conflict_values": json.dumps({"land_category": list(r.cats), "tx_ids": list(r.tx_ids)}, ensure_ascii=False),
        })
    return new


# ---------------------------------------------------------------------------
# 적재
# ---------------------------------------------------------------------------

def _insert_exceptions(conn, records: list[dict], batch_id: str) -> int:
    inserted = 0
    for rec in records:
        result = conn.execute(
            text(_INSERT_EXCEPTION_SQL),
            {
                "tx_ids": rec["tx_ids"],
                "raw_ids": rec["raw_ids"] or None,
                "beopjungri_code": rec["beopjungri_code"],
                "contract_date": rec["contract_date"],
                "area_sqm": rec["area_sqm"],
                "total_price_10k": rec["total_price_10k"],
                "lot_display": rec.get("lot_display"),
                "conflict_type": rec["conflict_type"],
                "conflict_values": rec["conflict_values"],
                "batch_id": batch_id,
            },
        )
        inserted += result.rowcount
    return inserted


# ---------------------------------------------------------------------------
# 요약 리포트
# ---------------------------------------------------------------------------

def _summary(conn) -> dict:
    rows = conn.execute(
        text("""
            SELECT conflict_type, status, COUNT(*) as cnt
            FROM land_exception_queue
            GROUP BY conflict_type, status
            ORDER BY conflict_type, status
        """)
    ).fetchall()
    total_pending = conn.execute(
        text("SELECT COUNT(*) FROM land_exception_queue WHERE status='pending'")
    ).scalar()
    return {
        "total_pending": int(total_pending or 0),
        "by_type_status": [dict(r._mapping) for r in rows],
    }


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="토지 거래 예외 탐지 → land_exception_queue")
    parser.add_argument("--dry-run",  action="store_true", help="탐지만, DB 미변경")
    parser.add_argument("--execute",  action="store_true", help="queue에 INSERT")
    parser.add_argument(
        "--since",
        default=str(DEFAULT_SINCE),
        help=f"계약일 하한 (기본: {DEFAULT_SINCE})",
    )
    args = parser.parse_args()

    if not args.dry_run and not args.execute:
        parser.error("--dry-run 또는 --execute 를 지정하세요.")

    since = date.fromisoformat(args.since)
    batch_id = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    engine = get_engine()

    with engine.connect() as conn:
        existing = _existing_keys(conn)
        log.info("기존 queue 항목: %d건", len(existing))

        zone_new    = _detect_zone_conflicts(conn, since, existing)
        land_new    = _detect_land_cat_conflicts(conn, since, existing)
        all_new     = zone_new + land_new

        log.info(
            "신규 충돌 탐지: zone_type=%d건, land_category=%d건 (합계=%d건)",
            len(zone_new), len(land_new), len(all_new),
        )

        if args.dry_run:
            log.info("[DRY-RUN] zone_type 충돌 샘플 (최대 5건):")
            for rec in zone_new[:5]:
                log.info("  %s %s %.2f㎡ %.0f만 → %s",
                    rec["beopjungri_code"], rec["contract_date"],
                    rec["area_sqm"], rec["total_price_10k"],
                    rec["conflict_values"])
            if land_new:
                log.info("[DRY-RUN] land_category 충돌 샘플 (최대 5건):")
                for rec in land_new[:5]:
                    log.info("  %s %s %.2f㎡ %.0f만 → %s",
                        rec["beopjungri_code"], rec["contract_date"],
                        rec["area_sqm"], rec["total_price_10k"],
                        rec["conflict_values"])
            log.info("[DRY-RUN] 완료 — DB 미변경.")
            return

    # --execute
    with engine.begin() as conn:
        inserted = _insert_exceptions(conn, all_new, batch_id)
        log.info("queue INSERT: %d건 (batch=%s)", inserted, batch_id)

    # 최종 요약
    with engine.connect() as conn:
        summary = _summary(conn)
    log.info("queue 현황: pending=%d건", summary["total_pending"])
    for row in summary["by_type_status"]:
        log.info("  %-15s %-10s %d건", row["conflict_type"], row["status"], row["cnt"])

    log.info(
        "\n다음 단계:\n"
        "  1) SELECT * FROM land_exception_queue WHERE status='pending' ORDER BY conflict_type, contract_date;\n"
        "  2) 각 건을 확인 후 land_correction_rules 에 Rule 등록\n"
        "  3) UPDATE land_exception_queue SET status='resolved', resolved_value=..., resolved_by=..., resolved_at=NOW() WHERE id=...\n"
        "  4) 또는 확인 후 정상이면: UPDATE ... SET status='dismissed'"
    )


if __name__ == "__main__":
    main()
