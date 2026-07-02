"""
계약연월 구간 built_transactions 삭제 — 월간 12개월 CSV 재적재 전 중복·잔존 방지.

  py purge_built_contract_window.py --cycle-id 202607
  py purge_built_contract_window.py --from-yyyymm 202507 --to-yyyymm 202606 --dry-run
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sqlalchemy import text

_SCRIPT_DIR = Path(__file__).resolve().parent
_MONTHLY = _SCRIPT_DIR.parent / "scripts" / "monthly"
if str(_MONTHLY) not in sys.path:
    sys.path.insert(0, str(_MONTHLY))

from cycle_utils import collection_yyyymm_range_from_cycle_id  # noqa: E402

sys.path.insert(0, str(_SCRIPT_DIR / "built"))
from db_utils import get_built_engine  # noqa: E402


def _ym_bounds(from_yyyymm: str, to_yyyymm: str) -> tuple[int, int]:
    fy, fm = int(from_yyyymm[:4]), int(from_yyyymm[4:6])
    ty, tm = int(to_yyyymm[:4]), int(to_yyyymm[4:6])
    lo = fy * 100 + fm
    hi = ty * 100 + tm
    if lo > hi:
        raise ValueError(f"from-yyyymm({from_yyyymm}) > to-yyyymm({to_yyyymm})")
    return lo, hi


def purge_built_contract_window(
    from_yyyymm: str,
    to_yyyymm: str,
    *,
    dry_run: bool = False,
) -> int:
    lo, hi = _ym_bounds(from_yyyymm, to_yyyymm)
    engine = get_built_engine()

    with engine.connect() as conn:
        n = conn.execute(
            text(
                """
                SELECT COUNT(*) FROM built_transactions
                WHERE contract_year IS NOT NULL AND contract_month IS NOT NULL
                  AND (contract_year * 100 + contract_month) BETWEEN :lo AND :hi
                """
            ),
            {"lo": lo, "hi": hi},
        ).scalar() or 0

    print(f"purge target built contract {from_yyyymm}~{to_yyyymm}: {n} rows")
    if dry_run:
        return int(n)

    with engine.begin() as conn:
        res = conn.execute(
            text(
                """
                DELETE FROM built_transactions
                WHERE contract_year IS NOT NULL AND contract_month IS NOT NULL
                  AND (contract_year * 100 + contract_month) BETWEEN :lo AND :hi
                """
            ),
            {"lo": lo, "hi": hi},
        )
        deleted = res.rowcount or 0
    print(f"deleted: {deleted}")
    return int(deleted)


def main() -> None:
    p = argparse.ArgumentParser(description="built_transactions 계약연월 구간 purge")
    p.add_argument("--cycle-id", help="YYYYMM (예: 202607)")
    p.add_argument("--from-yyyymm")
    p.add_argument("--to-yyyymm")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    if args.cycle_id:
        y_from, y_to = collection_yyyymm_range_from_cycle_id(args.cycle_id.strip())
    elif args.from_yyyymm and args.to_yyyymm:
        y_from, y_to = args.from_yyyymm, args.to_yyyymm
    else:
        raise SystemExit("--cycle-id 또는 --from-yyyymm/--to-yyyymm 필요")

    purge_built_contract_window(y_from, y_to, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
