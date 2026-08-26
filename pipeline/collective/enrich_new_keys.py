"""실거래 달 집합 enrich — 속성 없는 building_key만 INSERT.

기존 A·B·C·T는 덮지 않는다. 대장 달 T 갱신은 apply_title_fill --refresh-t.
비주거 집합은 속성 테이블이 없어 이 경로를 타지 않는다(마트만).

  python -m collective.enrich_new_keys
  python -m collective.enrich_new_keys --dry-run --skip-kapt
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

_PIPELINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_PIPELINE))

from parcel_master.apply_title_fill import run as title_fill_run  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


def _run_kapt_new_keys(*, dry_run: bool) -> None:
    from build_collective_building_attributes import default_kapt_path

    try:
        default_kapt_path()
    except FileNotFoundError:
        log.warning("K-apt xlsx 없음 — 아파트 신규 키 K-apt 생략")
        return
    argv = ["--new-keys-only"]
    if dry_run:
        argv.append("--dry-run")
    old = sys.argv
    try:
        sys.argv = ["build_collective_building_attributes.py", *argv]
        from build_collective_building_attributes import main as kapt_main

        kapt_main()
    finally:
        sys.argv = old


def run(*, dry_run: bool = False, skip_kapt: bool = False, skip_title: bool = False) -> None:
    if not skip_kapt:
        _run_kapt_new_keys(dry_run=dry_run)
    if not skip_title:
        title_fill_run(dry_run=dry_run, new_keys_only=True)


def main() -> None:
    p = argparse.ArgumentParser(description="집합 신규 building_key만 속성 INSERT")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--skip-kapt", action="store_true")
    p.add_argument("--skip-title", action="store_true")
    args = p.parse_args()
    run(dry_run=args.dry_run, skip_kapt=args.skip_kapt, skip_title=args.skip_title)


if __name__ == "__main__":
    main()
