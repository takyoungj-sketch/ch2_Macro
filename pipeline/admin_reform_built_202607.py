"""
2026-07 행정개편 — 복합부동산(상업·공장·단독) 부분 재적재.

  py admin_reform_built_202607.py
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

from sqlalchemy import text

from reform_paths_202607 import AFFECTED_SIDO, BUILT_TYPE_DIRS, list_reform_csvs

ROOT = Path(__file__).resolve().parent
PY = sys.executable
ASSET_TYPES = ("commercial", "factory", "detached")


def _run(cmd: list[str], *, dry_run: bool) -> None:
    print("$", " ".join(cmd))
    if dry_run:
        return
    subprocess.run(cmd, check=True, cwd=str(ROOT))


def _sync_region_codes(dry_run: bool) -> None:
    if dry_run:
        print("sync region_codes land → built")
        return
    from built.db_utils import get_built_engine, get_land_engine_for_region_copy
    from built.import_refined import sync_region_codes_from_land

    sync_region_codes_from_land(
        get_built_engine(), get_land_engine_for_region_copy(), force=True
    )


def step_purge(dry_run: bool) -> None:
    from built.db_utils import get_built_engine

    engine = get_built_engine()
    codes = list(AFFECTED_SIDO)
    with engine.connect() as conn:
        n = conn.execute(
            text(
                """
                SELECT COUNT(*) FROM built_transactions
                WHERE btrim(sido_code::text) = ANY(:s)
                """
            ),
            {"s": codes},
        ).scalar()
    print(f"purge 대상 built_transactions: {n}건 (sido {', '.join(codes)})")
    if dry_run:
        return
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                DELETE FROM built_transactions
                WHERE btrim(sido_code::text) = ANY(:s)
                """
            ),
            {"s": codes},
        )


def step_ingest(dry_run: bool) -> None:
    all_paths: list[Path] = []
    for t in ASSET_TYPES:
        part = list_reform_csvs(BUILT_TYPE_DIRS[t])
        print(f"  {t}: {len(part)} CSV")
        all_paths.extend(part)
    if not all_paths:
        raise FileNotFoundError("reform staging CSV 없음 — raw/*201001_202605 확인")

    _sync_region_codes(dry_run)

    log_dir = ROOT.parent / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    paths_file = log_dir / "_reform_built_paths.txt"
    if not dry_run:
        paths_file.write_text(
            "\n".join(str(p) for p in all_paths) + "\n", encoding="utf-8"
        )

    for asset in ASSET_TYPES:
        _run(
            [
                PY,
                str(ROOT / "built" / "import_molit.py"),
                f"--{asset}-only",
                "--paths-file",
                str(paths_file),
                "--year-from",
                "2010",
                "--year-to",
                "2026",
            ],
            dry_run=dry_run,
        )


def step_stats(dry_run: bool, as_of: str) -> None:
    _run(
        [
            PY,
            str(ROOT / "built" / "build_scope_stats.py"),
            "--as-of",
            as_of,
            "--windows",
            "3,5",
        ],
        dry_run=dry_run,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="복합부동산 행정개편 재적재")
    parser.add_argument(
        "--step", choices=["purge", "ingest", "stats", "all"], default="all"
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--as-of", default="2025-12-01")
    args = parser.parse_args()

    steps = ["purge", "ingest", "stats"] if args.step == "all" else [args.step]
    for step in steps:
        print(f"\n=== {step} ===")
        if step == "purge":
            step_purge(args.dry_run)
        elif step == "ingest":
            step_ingest(args.dry_run)
        elif step == "stats":
            step_stats(args.dry_run, args.as_of)


if __name__ == "__main__":
    main()
