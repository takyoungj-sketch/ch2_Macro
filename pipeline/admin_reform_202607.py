"""
2026-07 행정개편(인천 구·군 조정, 전남광주 통합) 토지 파이프라인 오케스트레이션.

권장 순서:
  1. compare  — raw 신·구 CSV 검증 (선택)
  2. seed     — region_codes (260701 마스터)
  3. sync-raw — staging CSV → raw base / long term
  4. purge    — 영향 시도 land_transactions(+연결 raw) 삭제
  5. ingest   — collect + clean
  6. stats    — build_stats_v2 · build_upper_stats_v2 (영향 시도만)
  7. annual   — land_annual_stats · land_annual_upper_stats (영향 시도, 2010~)

사용법:
  cd pipeline
  py admin_reform_202607.py --dry-run --step all
  py admin_reform_202607.py --step seed
  py admin_reform_202607.py --step ingest --as-of 2025-12-01
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

from sqlalchemy import text

from db_utils import get_engine

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
PY = sys.executable

NEW_RAW_DIR = REPO / "raw" / "토지(인천,전남광주)_201001_202605"
LT_DIR = REPO / "raw" / "raw long term" / "토지_2010_2020" / "토지_2010_2020"
BASE_DIR = REPO / "raw" / "raw base" / "토지_2021_2026"
REGION_FILE = REPO / "data" / "region_codes" / "법정동코드 전체자료(260701).txt"

AFFECTED_SIDO = ("12", "28", "29", "46")
STATS_SIDO = ("12", "28")

OLD_LAND_PATTERNS = (
    "광주광역시_토지_매매_",
    "전라남도_토지_매매_",
)


def _run(cmd: list[str], *, dry_run: bool) -> None:
    line = " ".join(cmd)
    print(f"$ {line}")
    if dry_run:
        return
    subprocess.run(cmd, check=True, cwd=str(ROOT))


def step_compare(dry_run: bool) -> None:
    _run([PY, str(ROOT / "_compare_land_csv_regions.py")], dry_run=dry_run)


def step_seed(dry_run: bool, *, national: bool) -> None:
    if not REGION_FILE.is_file():
        raise FileNotFoundError(f"법정동 마스터 없음: {REGION_FILE}")

    base = [
        PY,
        str(ROOT / "seed_region_codes.py"),
        "--file",
        str(REGION_FILE),
        "--mark-abolished-inactive",
        "--retire-sido",
        "29,46",
    ]
    if dry_run:
        base.append("--dry-run")

    if national:
        _run(base, dry_run=dry_run)
        return

    for sido in ("전남광주통합특별시", "인천광역시"):
        cmd = [*base, "--sido", sido]
        _run(cmd, dry_run=dry_run)


def _year_from_name(name: str) -> int | None:
    m = re.search(r"_(\d{4})(?:\.csv|_\d{8}_\d{8}\.csv)$", name, re.I)
    if m:
        return int(m.group(1))
    m2 = re.search(r"_(\d{4})\d{4}_\d{8}\.csv$", name, re.I)
    return int(m2.group(1)) if m2 else None


def step_sync_raw(dry_run: bool) -> None:
    if not NEW_RAW_DIR.is_dir():
        raise FileNotFoundError(f"staging 폴더 없음: {NEW_RAW_DIR}")

    LT_DIR.mkdir(parents=True, exist_ok=True)
    BASE_DIR.mkdir(parents=True, exist_ok=True)

    copied = 0
    removed = 0

    for src in sorted(NEW_RAW_DIR.glob("*.csv")):
        year = _year_from_name(src.name)
        if year is None:
            print(f"  skip (연도 미상): {src.name}")
            continue
        dest_dir = LT_DIR if year <= 2020 else BASE_DIR
        dest = dest_dir / src.name
        print(f"  copy {src.name} → {dest_dir.name}/")
        if not dry_run:
            shutil.copy2(src, dest)
        copied += 1

    for dest_dir in (LT_DIR, BASE_DIR):
        for old in dest_dir.glob("*.csv"):
            if any(old.name.startswith(p) for p in OLD_LAND_PATTERNS):
                print(f"  remove legacy {old.name}")
                if not dry_run:
                    old.unlink()
                removed += 1

    print(f"sync-raw 완료: 복사 {copied}건, 레거시 삭제 {removed}건")


def step_purge(dry_run: bool) -> None:
    engine = get_engine()
    sido_list = list(AFFECTED_SIDO)
    with engine.connect() as conn:
        tx_count = conn.execute(
            text(
                """
                SELECT COUNT(*) FROM land_transactions
                WHERE btrim(sido_code::text) = ANY(:sidos)
                """
            ),
            {"sidos": sido_list},
        ).scalar() or 0
        raw_count = conn.execute(
            text(
                """
                SELECT COUNT(DISTINCT raw_id) FROM land_transactions
                WHERE btrim(sido_code::text) = ANY(:sidos)
                  AND raw_id IS NOT NULL
                """
            ),
            {"sidos": sido_list},
        ).scalar() or 0
    print(
        f"purge 대상: land_transactions {tx_count}건, "
        f"연결 raw {raw_count}건 (sido {', '.join(sido_list)})"
    )
    if dry_run:
        return

    with engine.begin() as conn:
        raw_ids = [
            r[0]
            for r in conn.execute(
                text(
                    """
                    SELECT DISTINCT raw_id
                    FROM land_transactions
                    WHERE btrim(sido_code::text) = ANY(:sidos)
                      AND raw_id IS NOT NULL
                    """
                ),
                {"sidos": sido_list},
            ).fetchall()
        ]
        tx = conn.execute(
            text(
                """
                DELETE FROM land_transactions
                WHERE btrim(sido_code::text) = ANY(:sidos)
                """
            ),
            {"sidos": sido_list},
        )
        raw_n = 0
        if raw_ids:
            raw_n = conn.execute(
                text("DELETE FROM land_transactions_raw WHERE id = ANY(:ids)"),
                {"ids": raw_ids},
            ).rowcount or 0
        print(f"purge 완료: transactions {tx.rowcount or 0}건, raw {raw_n}건")


def _collect_paths() -> list[Path]:
    paths: list[Path] = []
    for d in (LT_DIR, BASE_DIR):
        if not d.is_dir():
            continue
        for p in sorted(d.glob("*.csv")):
            if p.name.startswith("인천광역시_토지_") or p.name.startswith(
                "전남광주통합특별시_토지_"
            ):
                paths.append(p)
    return paths


def step_ingest(dry_run: bool) -> None:
    paths = _collect_paths()
    if not paths:
        raise FileNotFoundError("ingest 대상 CSV 없음 — sync-raw 먼저 실행")

    for path in paths:
        year = _year_from_name(path.name) or 2025
        _run(
            [
                PY,
                str(ROOT / "collect.py"),
                "--mode",
                "excel",
                "--file",
                str(path),
                "--format",
                "csv",
                "--source-year",
                str(year),
                "--source-month",
                "6",
            ],
            dry_run=dry_run,
        )

    _run([PY, str(ROOT / "clean.py")], dry_run=dry_run)


def step_stats(dry_run: bool, as_of: str, windows: str) -> None:
    for sido in STATS_SIDO:
        _run(
            [
                PY,
                str(ROOT / "build_stats_v2.py"),
                "--as-of",
                as_of,
                "--windows",
                windows,
                "--sido-code",
                sido,
            ],
            dry_run=dry_run,
        )
        _run(
            [
                PY,
                str(ROOT / "build_upper_stats_v2.py"),
                "--as-of",
                as_of,
                "--windows",
                windows,
                "--sido-code",
                sido,
            ],
            dry_run=dry_run,
        )


def step_annual(dry_run: bool) -> None:
    _run([PY, str(ROOT / "reform_annual_long_term.py")], dry_run=dry_run)


def main() -> None:
    parser = argparse.ArgumentParser(description="2026-07 행정개편 토지 파이프라인")
    parser.add_argument(
        "--step",
        choices=[
            "compare",
            "seed",
            "sync-raw",
            "purge",
            "ingest",
            "stats",
            "annual",
            "all",
        ],
        default="all",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--national-seed",
        action="store_true",
        help="region_codes 전국 시드(미지정 시 전남광주·인천만)",
    )
    parser.add_argument("--as-of", default="2025-12-01", help="stats 기준월 (YYYY-MM-DD)")
    parser.add_argument("--windows", default="3,5", help="stats window_years")
    args = parser.parse_args()

    steps = (
        ["compare", "seed", "sync-raw", "purge", "ingest", "stats", "annual"]
        if args.step == "all"
        else [args.step]
    )

    for step in steps:
        print(f"\n=== {step} ===")
        if step == "compare":
            step_compare(args.dry_run)
        elif step == "seed":
            step_seed(args.dry_run, national=args.national_seed)
        elif step == "sync-raw":
            step_sync_raw(args.dry_run)
        elif step == "purge":
            step_purge(args.dry_run)
        elif step == "ingest":
            step_ingest(args.dry_run)
        elif step == "stats":
            step_stats(args.dry_run, args.as_of, args.windows)
        elif step == "annual":
            step_annual(args.dry_run)


if __name__ == "__main__":
    main()
