#!/usr/bin/env python3
"""
토지 월간 cycle — Molit CSV(12개월) 갱신, 중복 적재 방지, V2 사전통계.

기본 raw: raw/2607업데이트/토지_{from}_{to}/ 또는 raw/토지/{cycle_id}/

  py scripts/monthly/run_land_cycle_csv.py --cycle-id 202607
  py scripts/monthly/run_land_cycle_csv.py --cycle-id 202607 --dry-run
  py scripts/monthly/run_land_cycle_csv.py --cycle-id 202607 --skip-purge --skip-stats

순서:
  1) (선택) DDL 037·038
  2) 계약연월 구간 purge + 배치 raw 태그 purge
  3) collect (CSV) → clean → dedupe
  4) build_stats_v2 + build_upper_stats_v2
  5) 스냅샷 JSON
"""

from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from cycle_utils import (  # noqa: E402
    collection_yyyymm_range_from_cycle_id,
    stats_as_of_iso_from_cycle_id,
)

REPO = _SCRIPT_DIR.parents[1]
PIPELINE = REPO / "pipeline"
PY = sys.executable

log = logging.getLogger(__name__)


def _run(phase: str, cmd: list[str], *, cwd: Path | None = None) -> None:
    log.info("[%s] %s", phase, " ".join(cmd))
    t0 = time.perf_counter()
    kwargs: dict = {}
    if cwd:
        kwargs["cwd"] = str(cwd)
    subprocess.run(cmd, check=True, **kwargs)
    sec = time.perf_counter() - t0
    log.info("[%s] %.1fs (%.2f분)", phase, sec, sec / 60)


def _default_raw_dir(cycle_id: str, y_from: str, y_to: str) -> Path:
    candidates = [
        REPO / "raw" / "2607업데이트" / f"토지_{y_from}_{y_to}",
        REPO / "raw" / "토지" / cycle_id,
        REPO / "raw" / f"토지_{y_from}_{y_to}",
    ]
    for p in candidates:
        if p.is_dir() and list(p.glob("*.csv")):
            return p
    return candidates[0]


def _apply_ddl(*, dry_run: bool) -> None:
    names = ("037_land_jimok_group_map.sql", "038_land_transactions_resolved_jimok_group.sql")
    for name in names:
        ddl = REPO / "db" / name
        if not ddl.is_file():
            log.warning("DDL 없음: %s", ddl)
            continue
        if dry_run:
            log.info("[ddl-skip] %s", ddl.name)
            continue
        if str(PIPELINE) not in sys.path:
            sys.path.insert(0, str(PIPELINE))
        from db_utils import get_engine  # noqa: WPS433
        from sqlalchemy import text  # noqa: WPS433

        sql = ddl.read_text(encoding="utf-8")
        log.info("DDL 적용: %s", name)
        with get_engine().begin() as conn:
            conn.execute(text(sql))


def _write_manifest(cycle_id: str, raw_dir: Path) -> Path:
    out_dir = REPO / "clean_snapshots" / cycle_id
    out_dir.mkdir(parents=True, exist_ok=True)
    files = sorted(raw_dir.glob("*.csv"), key=lambda p: p.name.lower())
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "cycle_id": cycle_id,
        "raw_root": str(raw_dir),
        "csv_count": len(files),
        "csv_files": [f.name for f in files],
    }
    path = out_dir / "raw_manifest.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    p = argparse.ArgumentParser(description="토지 월간 CSV cycle (purge → ingest → V2)")
    p.add_argument("--cycle-id", required=True, help="YYYYMM (예: 202607)")
    p.add_argument("--raw-dir", type=Path, help="Molit CSV 폴더")
    p.add_argument("--dry-run", action="store_true", help="purge·DDL만 확인")
    p.add_argument("--skip-purge", action="store_true")
    p.add_argument("--skip-ddl", action="store_true")
    p.add_argument("--skip-dedupe", action="store_true")
    p.add_argument("--skip-stats", action="store_true")
    p.add_argument("--v2-as-of", help="build_stats_v2 --as-of (기본: cycle 매핑)")
    p.add_argument(
        "--source-year",
        type=int,
        default=0,
        help="collect raw 태그 연도 (기본: cycle 달력 연도)",
    )
    p.add_argument(
        "--source-month",
        type=int,
        default=0,
        help="collect raw 태그 월 (기본: cycle 월)",
    )
    args = p.parse_args()

    cycle = args.cycle_id.strip()
    y_from, y_to = collection_yyyymm_range_from_cycle_id(cycle)
    v2_as = (args.v2_as_of or "").strip() or stats_as_of_iso_from_cycle_id(cycle)
    raw_dir = (args.raw_dir or _default_raw_dir(cycle, y_from, y_to)).expanduser().resolve()

    cy = int(cycle[:4])
    cm = int(cycle[4:6])
    source_year = args.source_year if args.source_year > 0 else cy
    source_month = args.source_month if args.source_month > 0 else cm

    log.info(
        "cycle=%s contract=%s~%s v2-as-of=%s raw=%s",
        cycle,
        y_from,
        y_to,
        v2_as,
        raw_dir,
    )
    if not raw_dir.is_dir():
        raise SystemExit(f"raw 폴더 없음: {raw_dir}")
    csvs = list(raw_dir.glob("*.csv"))
    if len(csvs) < 1:
        raise SystemExit(f"CSV 없음: {raw_dir}")

    man = _write_manifest(cycle, raw_dir)
    log.info("manifest: %s (%d csv)", man, len(csvs))

    if args.dry_run:
        if not args.skip_ddl:
            _apply_ddl(dry_run=True)
        if not args.skip_purge:
            _run(
                "purge-dry-run",
                [
                    PY,
                    str(PIPELINE / "purge_land_contract_window.py"),
                    "--cycle-id",
                    cycle,
                    "--dry-run",
                    "--purge-batch-raw",
                    "--source-year",
                    str(source_year),
                    "--source-month",
                    str(source_month),
                ],
                cwd=PIPELINE,
            )
        log.info("dry-run 완료")
        return

    if not args.skip_ddl:
        _apply_ddl(dry_run=False)

    if not args.skip_purge:
        _run(
            "purge",
            [
                PY,
                "purge_land_contract_window.py",
                "--cycle-id",
                cycle,
                "--purge-batch-raw",
                "--source-year",
                str(source_year),
                "--source-month",
                str(source_month),
            ],
            cwd=PIPELINE,
        )

    _run(
        "collect",
        [
            PY,
            "collect.py",
            "--mode",
            "excel",
            "--directory",
            str(raw_dir),
            "--format",
            "csv",
            "--source-year",
            str(source_year),
            "--source-month",
            str(source_month),
        ],
        cwd=PIPELINE,
    )

    _run("clean", [PY, "clean.py"], cwd=PIPELINE)

    if not args.skip_dedupe:
        _run(
            "dedupe",
            [PY, "dedupe_land_transactions.py", "--execute", "--rehash"],
            cwd=PIPELINE,
        )

    if not args.skip_stats:
        _run(
            "build_stats_v2",
            [PY, "build_stats_v2.py", "--as-of", v2_as, "--windows", "3,5"],
            cwd=PIPELINE,
        )
        _run(
            "build_upper_stats_v2",
            [PY, "build_upper_stats_v2.py", "--as-of", v2_as, "--windows", "3,5"],
            cwd=PIPELINE,
        )

    snap_script = _SCRIPT_DIR / "snapshot_land_tx_counts.py"
    snap_out = REPO / "clean_snapshots" / cycle / "land_tx_counts_after.json"
    _run("snapshot_tx", [PY, str(snap_script), "--output", str(snap_out)])

    v2_snap = _SCRIPT_DIR / "snapshot_v2_stats.py"
    v2_out = REPO / "stats_snapshots" / cycle / "land_basic_stats_v2_summary.json"
    v2_out.parent.mkdir(parents=True, exist_ok=True)
    _run(
        "snapshot_v2",
        [PY, str(v2_snap), "--as-of", v2_as, "--output", str(v2_out)],
    )

    log.info("완료 — 다음: verify_monthly_integrity.py --as-of-month %s", v2_as[:8] + "01")


if __name__ == "__main__":
    main()
