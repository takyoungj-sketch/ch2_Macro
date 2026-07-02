"""
2026-07 행정개편 — 집합부동산(주거 4유형 + 비주거 집합상가·공장) 부분 재적재.

  py admin_reform_collective_202607.py
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from sqlalchemy import text

from build_stats_v2 import default_as_of_month
from reform_paths_202607 import (
    AFFECTED_SIDO,
    COLLECTIVE_COMMERCIAL_DIRS,
    COLLECTIVE_RESIDENTIAL_DIRS,
    list_reform_csvs,
)

ROOT = Path(__file__).resolve().parent
PY = sys.executable
SIDO_PURGE = ",".join(AFFECTED_SIDO)


def _run(cmd: list[str], *, dry_run: bool) -> None:
    print("$", " ".join(cmd))
    if dry_run:
        return
    subprocess.run(cmd, check=True, cwd=str(ROOT))


def _collect_all_paths() -> list[Path]:
    paths: list[Path] = []
    for d in COLLECTIVE_RESIDENTIAL_DIRS.values():
        paths.extend(list_reform_csvs(d))
    for d in COLLECTIVE_COMMERCIAL_DIRS.values():
        paths.extend(list_reform_csvs(d))
    return paths


def step_purge(dry_run: bool) -> None:
    from collective.db_utils import get_collective_engine

    eng = get_collective_engine()
    codes = list(AFFECTED_SIDO)
    with eng.connect() as conn:
        n_res = conn.execute(
            text(
                """
                SELECT COUNT(*) FROM collective_transactions
                WHERE btrim(sido_code::text) = ANY(:s)
                """
            ),
            {"s": codes},
        ).scalar()
        n_com = conn.execute(
            text(
                """
                SELECT COUNT(*) FROM collective_commercial_transactions
                WHERE btrim(sido_code::text) = ANY(:s)
                """
            ),
            {"s": codes},
        ).scalar()
    print(f"purge 대상 residential={n_res}, commercial={n_com}")
    if dry_run:
        return
    with eng.begin() as conn:
        conn.execute(
            text(
                """
                DELETE FROM collective_transactions
                WHERE btrim(sido_code::text) = ANY(:s)
                """
            ),
            {"s": codes},
        )
        conn.execute(
            text(
                """
                DELETE FROM collective_commercial_transactions
                WHERE btrim(sido_code::text) = ANY(:s)
                """
            ),
            {"s": codes},
        )
        conn.execute(
            text(
                """
                DELETE FROM commercial_clusters
                WHERE btrim(sido_code::text) = ANY(:s)
                """
            ),
            {"s": codes},
        )


def step_ingest(dry_run: bool) -> None:
    paths = _collect_all_paths()
    if not paths:
        raise FileNotFoundError("reform staging CSV 없음")
    print(f"ingest 대상 CSV {len(paths)}개")
    log_dir = ROOT.parent / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    paths_file = log_dir / "_reform_collective_paths.txt"
    if not dry_run:
        paths_file.write_text("\n".join(str(p) for p in paths) + "\n", encoding="utf-8")

    _run(
        [
            PY,
            str(ROOT / "collective" / "import_refined.py"),
            "--refresh-region-codes",
            "--paths-file",
            str(paths_file),
            "--purge-sido",
            SIDO_PURGE,
        ],
        dry_run=dry_run,
    )
    _run(
        [
            PY,
            str(ROOT / "collective_commercial" / "import_refined.py"),
            "--refresh-region-codes",
            "--paths-file",
            str(paths_file),
            "--purge-sido",
            SIDO_PURGE,
            "--year-from",
            "2010",
            "--year-to",
            "2026",
        ],
        dry_run=dry_run,
    )


def step_marts(dry_run: bool, as_of: str) -> None:
    _run([PY, str(ROOT / "build_region_sigungu_meta.py"), "--collective"], dry_run=dry_run)
    _run(
        [
            PY,
            str(ROOT / "build_collective_building_stats.py"),
            "--as-of",
            as_of,
            "--windows",
            "3,5",
        ],
        dry_run=dry_run,
    )
    _run(
        [
            PY,
            str(ROOT / "build_collective_building_rolling_stats.py"),
            "--as-of",
            as_of,
            "--windows",
            "3,5",
        ],
        dry_run=dry_run,
    )
    _run(
        [
            PY,
            str(ROOT / "build_collective_market_stats.py"),
            "--as-of",
            as_of,
            "--windows",
            "3,5",
        ],
        dry_run=dry_run,
    )
    _run(
        [PY, str(ROOT / "build_collective_commercial_cluster_stats.py")],
        dry_run=dry_run,
    )


def step_long_term(dry_run: bool) -> None:
    _run([PY, str(ROOT / "reform_collective_annual_long_term.py")], dry_run=dry_run)


def main() -> None:
    parser = argparse.ArgumentParser(description="집합부동산 행정개편 재적재")
    parser.add_argument(
        "--step",
        choices=["purge", "ingest", "marts", "long-term", "all"],
        default="all",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--as-of",
        default=None,
        help="mart 기준월 YYYY-MM-01 (기본: 직전 월말 스냅샷)",
    )
    args = parser.parse_args()
    as_of = args.as_of or default_as_of_month().isoformat()

    steps = ["purge", "ingest", "marts", "long-term"] if args.step == "all" else [args.step]
    for step in steps:
        print(f"\n=== {step} ===")
        if step == "purge":
            step_purge(args.dry_run)
        elif step == "ingest":
            if args.step in ("all", "ingest"):
                step_purge(args.dry_run)
            step_ingest(args.dry_run)
        elif step == "marts":
            step_marts(args.dry_run, as_of)
        elif step == "long-term":
            step_long_term(args.dry_run)


if __name__ == "__main__":
    main()
