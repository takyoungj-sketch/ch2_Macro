"""Dump the local land_stats database for a monthly promote cycle."""
from __future__ import annotations

import argparse
from pathlib import Path

from cycle_utils import _validate_cycle_id
from dump_db_for_promote import dump_database

REPO_ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    parser = argparse.ArgumentParser(description="VPS 복원용 land_stats 전체 덤프")
    parser.add_argument(
        "--cycle-id", required=True, metavar="YYYYMM",
        help="월간 작업 ID. 기본 파일명에 쓰이며 덤프 범위는 land_stats 전체입니다.",
    )
    parser.add_argument("-o", "--output", type=Path, help="출력 .sql.gz 경로")
    args = parser.parse_args()
    try:
        _validate_cycle_id(args.cycle_id)
    except ValueError as exc:
        parser.error(str(exc))
    output = args.output or REPO_ROOT / "backups" / f"land_stats_promote_{args.cycle_id}.sql.gz"
    return dump_database("land_stats", output)


if __name__ == "__main__":
    raise SystemExit(main())
