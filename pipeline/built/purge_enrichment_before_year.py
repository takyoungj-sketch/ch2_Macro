# -*- coding: utf-8 -*-
"""2018년 이전 복합 보강 행 삭제 — D-050 범위 축소. CASCADE 없음.

동결의 재매칭이 아니라 보강 범위를 2019+로 줄인다. 2019+ 행은 건드리지 않는다.

  python -m built.purge_enrichment_before_year --min-year 2019
  python -m built.purge_enrichment_before_year --min-year 2019 --apply
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sqlalchemy import text

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "pipeline"))

from built.db_utils import get_built_engine  # noqa: E402

COUNT_SQL = """
SELECT COUNT(*) FROM built_transaction_enrichment e
JOIN built_transactions t ON t.transaction_hash = e.transaction_hash
WHERE t.contract_year IS NOT NULL AND t.contract_year < :min_year
"""

DELETE_SQL = """
DELETE FROM built_transaction_enrichment e
USING built_transactions t
WHERE e.transaction_hash = t.transaction_hash
  AND t.contract_year IS NOT NULL
  AND t.contract_year < :min_year
"""


def purge_enrichment_before_year(min_year: int, *, apply: bool) -> int:
    engine = get_built_engine()
    with engine.connect() as conn:
        n = int(conn.execute(text(COUNT_SQL), {"min_year": min_year}).scalar() or 0)
    print(f"enrichment contract_year < {min_year}: {n:,} rows")
    if not apply:
        print("dry-run (pass --apply to delete)")
        return n
    with engine.begin() as conn:
        deleted = conn.execute(text(DELETE_SQL), {"min_year": min_year}).rowcount or 0
        left = int(conn.execute(text(COUNT_SQL), {"min_year": min_year}).scalar() or 0)
    print(f"deleted: {deleted:,} · remaining < {min_year}: {left:,}")
    if left != 0:
        raise SystemExit(f"purge incomplete: {left} rows still below {min_year}")
    return int(deleted)


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    p = argparse.ArgumentParser(description="계약연도 미만 복합 enrichment DELETE (CASCADE 없음)")
    p.add_argument("--min-year", type=int, default=2019, help="이 연도 미만을 지움. 기본 2019")
    p.add_argument("--apply", action="store_true", help="실제 DELETE. 없으면 건수만")
    args = p.parse_args()
    purge_enrichment_before_year(args.min_year, apply=args.apply)


if __name__ == "__main__":
    main()
