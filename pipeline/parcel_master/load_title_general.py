"""표제부 「일반」 3스냅샷 → parcel_master.building. 기존 집합 행은 유지.

수요 필지만 parcel 로 파생한다(빈 필지 39M 없음). 집합 건수가 바뀌면 중단.

  cd pipeline
  python -m parcel_master.load_title_general --sido 43
  python -m parcel_master.load_title_general
"""

from __future__ import annotations

import argparse
import time

from parcel_master.load_title_pilot import run
from parcel_master.paths import ALL_SIDO
from parcel_master import setup_db


def main() -> None:
    p = argparse.ArgumentParser(description="표제부 「일반」 적재. 집합 행 보존")
    p.add_argument("--refresh", action="store_true")
    p.add_argument("--sido", nargs="+", default=list(ALL_SIDO))
    p.add_argument("--skip-ledger", action="store_true")
    p.add_argument(
        "--keep-indexes",
        action="store_true",
        help="secondary index를 유지 (기본은 적재 중 DROP)",
    )
    args = p.parse_args()
    setup_db.main()
    t0 = time.time()
    stats = run(
        tuple(args.sido),
        args.refresh,
        args.skip_ledger,
        "일반",
        drop_indexes=not args.keep_indexes,
    )
    elapsed = time.time() - t0
    print(f"[P1.2] elapsed={elapsed / 60:.1f}min {stats}", flush=True)


if __name__ == "__main__":
    main()
