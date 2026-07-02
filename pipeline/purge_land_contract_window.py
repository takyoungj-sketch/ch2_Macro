"""
계약연월 구간의 land_transactions(+연결 raw) 삭제 — 월간 12개월 갱신 시 중복·잔존 방지.

월간 cycle에서 동일 구간 CSV를 재적재하기 전에 호출한다.
  1) 해당 계약연월 거래 삭제
  2) 연결 raw_id 삭제
  3) (선택) 이번 배치 source_year/month 태그 raw 추가 삭제

사용:
  py purge_land_contract_window.py --from-yyyymm 202507 --to-yyyymm 202606
  py purge_land_contract_window.py --cycle-id 202607 --dry-run
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sqlalchemy import text

from db_utils import get_engine

_SCRIPT_DIR = Path(__file__).resolve().parent
_MONTHLY = _SCRIPT_DIR.parent / "scripts" / "monthly"
if str(_MONTHLY) not in sys.path:
    sys.path.insert(0, str(_MONTHLY))

from cycle_utils import collection_yyyymm_range_from_cycle_id  # noqa: E402


def _ym_bounds(from_yyyymm: str, to_yyyymm: str) -> tuple[int, int]:
    fy, fm = int(from_yyyymm[:4]), int(from_yyyymm[4:6])
    ty, tm = int(to_yyyymm[:4]), int(to_yyyymm[4:6])
    lo = fy * 100 + fm
    hi = ty * 100 + tm
    if lo > hi:
        raise ValueError(f"from-yyyymm({from_yyyymm}) > to-yyyymm({to_yyyymm})")
    return lo, hi


def purge_contract_window(
    from_yyyymm: str,
    to_yyyymm: str,
    *,
    dry_run: bool = False,
    purge_batch_raw: tuple[int, int] | None = None,
) -> dict[str, int]:
    lo, hi = _ym_bounds(from_yyyymm, to_yyyymm)
    engine = get_engine()

    with engine.connect() as conn:
        tx_count = conn.execute(
            text(
                """
                SELECT COUNT(*) FROM land_transactions
                WHERE (contract_year * 100 + contract_month) BETWEEN :lo AND :hi
                """
            ),
            {"lo": lo, "hi": hi},
        ).scalar() or 0
        raw_linked = conn.execute(
            text(
                """
                SELECT COUNT(DISTINCT raw_id) FROM land_transactions
                WHERE (contract_year * 100 + contract_month) BETWEEN :lo AND :hi
                  AND raw_id IS NOT NULL
                """
            ),
            {"lo": lo, "hi": hi},
        ).scalar() or 0
        batch_raw = 0
        if purge_batch_raw:
            sy, sm = purge_batch_raw
            batch_raw = conn.execute(
                text(
                    """
                    SELECT COUNT(*) FROM land_transactions_raw
                    WHERE source_year = :sy AND source_month = :sm
                    """
                ),
                {"sy": sy, "sm": sm},
            ).scalar() or 0

    print(
        f"purge target contract {from_yyyymm}~{to_yyyymm}: "
        f"transactions {tx_count}, linked raw {raw_linked}"
    )
    if purge_batch_raw:
        print(
            f"  batch raw tag source_year={purge_batch_raw[0]}, "
            f"source_month={purge_batch_raw[1]}: {batch_raw}"
        )
    if dry_run:
        return {
            "transactions": int(tx_count),
            "raw_linked": int(raw_linked),
            "batch_raw": int(batch_raw),
        }

    deleted_tx = 0
    deleted_raw = 0
    deleted_batch = 0
    with engine.begin() as conn:
        raw_ids = [
            r[0]
            for r in conn.execute(
                text(
                    """
                    SELECT DISTINCT raw_id
                    FROM land_transactions
                    WHERE (contract_year * 100 + contract_month) BETWEEN :lo AND :hi
                      AND raw_id IS NOT NULL
                    """
                ),
                {"lo": lo, "hi": hi},
            ).fetchall()
        ]
        res = conn.execute(
            text(
                """
                DELETE FROM land_transactions
                WHERE (contract_year * 100 + contract_month) BETWEEN :lo AND :hi
                """
            ),
            {"lo": lo, "hi": hi},
        )
        deleted_tx = res.rowcount or 0
        if raw_ids:
            res_raw = conn.execute(
                text("DELETE FROM land_transactions_raw WHERE id = ANY(:ids)"),
                {"ids": raw_ids},
            )
            deleted_raw = res_raw.rowcount or 0
        if purge_batch_raw:
            sy, sm = purge_batch_raw
            res_batch = conn.execute(
                text(
                    """
                    DELETE FROM land_transactions_raw
                    WHERE source_year = :sy AND source_month = :sm
                    """
                ),
                {"sy": sy, "sm": sm},
            )
            deleted_batch = res_batch.rowcount or 0

    print(
        f"purge done transactions {deleted_tx}, "
        f"raw(linked) {deleted_raw}, raw(batch-tag) {deleted_batch}"
    )
    return {
        "transactions": deleted_tx,
        "raw_linked": deleted_raw,
        "batch_raw": deleted_batch,
    }


def main() -> None:
    p = argparse.ArgumentParser(description="토지 계약연월 구간 purge")
    p.add_argument("--cycle-id", help="YYYYMM — from/to 자동 (직전 12개월)")
    p.add_argument("--from-yyyymm", help="시작 계약연월 YYYYMM")
    p.add_argument("--to-yyyymm", help="종료 계약연월 YYYYMM")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument(
        "--purge-batch-raw",
        action="store_true",
        help="collect --source-year/month 태그 raw 도 삭제 (월간 CSV 배치용)",
    )
    p.add_argument("--source-year", type=int, default=0, help="배치 raw 태그 연도")
    p.add_argument("--source-month", type=int, default=0, help="배치 raw 태그 월")
    args = p.parse_args()

    if args.cycle_id:
        y_from, y_to = collection_yyyymm_range_from_cycle_id(args.cycle_id.strip())
    elif args.from_yyyymm and args.to_yyyymm:
        y_from, y_to = args.from_yyyymm.strip(), args.to_yyyymm.strip()
    else:
        p.error("--cycle-id 또는 --from-yyyymm/--to-yyyymm 필요")

    batch_tag: tuple[int, int] | None = None
    if args.purge_batch_raw:
        if args.source_year < 1 or not (1 <= args.source_month <= 12):
            p.error("--purge-batch-raw 시 --source-year/--source-month 필요")
        batch_tag = (args.source_year, args.source_month)

    purge_contract_window(y_from, y_to, dry_run=args.dry_run, purge_batch_raw=batch_tag)


if __name__ == "__main__":
    main()
