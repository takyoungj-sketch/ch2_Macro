#!/usr/bin/env python3
"""
복합부동산 월간 cycle — 2607업데이트 CSV(12개월) UPSERT + stale purge + scope mart.

  py scripts/monthly/run_built_cycle_csv.py --cycle-id 202607
  py scripts/monthly/run_built_cycle_csv.py --cycle-id 202607 --dry-run

순서:
  1) import_molit UPSERT (--paths-file, region_codes refresh, --seen-hashes-file)
  2) 창에서 CSV에 없는 해시만 DELETE (purge --keep-hashes-file)
  3) build_scope_stats (--as-of cycle 매핑) — 원장만, 보강 컬럼 없음
  4) enrich: 기본 skip. --enrich 이면 미상 hash만 (ON CONFLICT DO NOTHING)
  5) 동결 검증 · 스냅샷 JSON
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
    resolve_csv_subdir,
    stats_as_of_iso_from_cycle_id,
)

REPO = _SCRIPT_DIR.parents[1]
PIPELINE = REPO / "pipeline"
PY = sys.executable

BUILT_RAW_DIRS = {
    "commercial": "상업업무",
    "factory": "공장창고",
    "detached": "단독다가구",
}

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


def _resolve_raw_dirs(cycle_id: str, y_from: str, y_to: str) -> dict[str, Path]:
    out: dict[str, Path] = {}
    for asset, folder in BUILT_RAW_DIRS.items():
        found = resolve_csv_subdir(
            REPO,
            cycle_id,
            folder,
            y_from,
            y_to,
            extra_candidates=[
                REPO / "raw" / "복합부동산" / cycle_id / folder,
                REPO / "raw" / "raw base" / f"{folder}_2021_2026",
            ],
        )
        if found is None:
            suffix = f"{y_from}_{y_to}"
            raise FileNotFoundError(
                f"{asset}: CSV 폴더 없음 — cycle={cycle_id}, suffix={suffix}"
            )
        out[asset] = found
    return out


def _collect_csv_paths(raw_dirs: dict[str, Path]) -> list[Path]:
    paths: list[Path] = []
    for folder in raw_dirs.values():
        paths.extend(sorted(folder.glob("*.csv"), key=lambda p: p.name.lower()))
    return paths


def _write_manifest(cycle_id: str, raw_dirs: dict[str, Path], csv_paths: list[Path]) -> Path:
    out_dir = REPO / "clean_snapshots" / cycle_id / "built"
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "cycle_id": cycle_id,
        "raw_dirs": {k: str(v) for k, v in raw_dirs.items()},
        "csv_count": len(csv_paths),
        "csv_files": [p.name for p in csv_paths],
    }
    path = out_dir / "raw_manifest.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="복합부동산 월간 CSV cycle (UPSERT → mart → skip-enrich)")
    p.add_argument("--cycle-id", required=True, help="YYYYMM (예: 202607)")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--skip-purge", action="store_true")
    p.add_argument("--skip-ingest", action="store_true")
    p.add_argument("--skip-stats", action="store_true")
    p.add_argument("--no-refresh-region-codes", action="store_true")
    p.add_argument("--skip-mapping-check", action="store_true")
    p.add_argument(
        "--skip-enrich",
        action="store_true",
        help="마트 뒤 enrich 생략. 플래그 없이도 기본은 skip",
    )
    p.add_argument(
        "--enrich",
        action="store_true",
        help="마트 뒤 미상 hash만 recover_from_parcel --apply-enrichment. D-051 전 운영 적재 금지",
    )
    p.add_argument(
        "--retry-unmatched",
        action="store_true",
        help="거절. 실거래 달에는 미상 재시도 없음. 대장 달은 recover_from_parcel 수동",
    )
    p.add_argument("--skip-freeze-check", action="store_true")
    return p


def should_run_enrich(*, enrich: bool, skip_enrich: bool) -> bool:
    if skip_enrich:
        return False
    return bool(enrich)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = build_parser().parse_args()
    if args.retry_unmatched:
        raise SystemExit(
            "실거래 달 러너는 --retry-unmatched 를 받지 않는다. "
            "대장 달: python -m built.recover_from_parcel --sido all --min-year 2019 --retry-unmatched"
        )

    cycle = args.cycle_id.strip()
    y_from, y_to = collection_yyyymm_range_from_cycle_id(cycle)
    as_of = stats_as_of_iso_from_cycle_id(cycle)
    raw_dirs = _resolve_raw_dirs(cycle, y_from, y_to)
    csv_paths = _collect_csv_paths(raw_dirs)
    paths_file = REPO / "logs" / f"built_cycle_{cycle}_paths.txt"
    paths_file.parent.mkdir(parents=True, exist_ok=True)
    paths_file.write_text("\n".join(str(p) for p in csv_paths) + "\n", encoding="utf-8")

    man = _write_manifest(cycle, raw_dirs, csv_paths)
    log.info("manifest: %s (%d CSV)", man, len(csv_paths))
    for asset, d in raw_dirs.items():
        log.info("  %s → %s", asset, d)

    hashes_file = REPO / "logs" / f"built_cycle_{cycle}_hashes.txt"

    if args.dry_run:
        log.info(
            "dry-run: ingest 후 stale purge. skip-enrich 기본. hashes → %s",
            hashes_file,
        )
        log.info("dry-run: ingest/stats/enrich 생략")
        return

    cycle_t0 = time.perf_counter()

    if not args.skip_ingest:
        ingest_cmd = [
            PY,
            str(PIPELINE / "built" / "import_molit.py"),
            "--paths-file",
            str(paths_file),
            "--year-from",
            "2021",
            "--year-to",
            "2026",
            "--seen-hashes-file",
            str(hashes_file),
        ]
        if not args.no_refresh_region_codes:
            ingest_cmd.append("--refresh-region-codes")
        _run("import_molit", ingest_cmd, cwd=PIPELINE)

        if not args.skip_purge:
            _run(
                "purge_built_stale",
                [
                    PY,
                    str(PIPELINE / "purge_built_contract_window.py"),
                    "--cycle-id",
                    cycle,
                    "--keep-hashes-file",
                    str(hashes_file),
                ],
                cwd=PIPELINE,
            )
    elif not args.skip_purge:
        log.warning("skip-ingest 이므로 stale purge 생략 (keep-hashes 없음, 창 전체 DELETE 금지)")

    if not args.skip_stats:
        _run(
            "build_scope_stats",
            [
                PY,
                str(PIPELINE / "built" / "build_scope_stats.py"),
                "--as-of",
                as_of,
                "--windows",
                "3,5,7",
            ],
            cwd=PIPELINE,
        )

    snap_dir = REPO / "clean_snapshots" / cycle / "built"
    freeze_before = snap_dir / "enrichment_before.jsonl"
    freeze_report = snap_dir / "enrichment_freeze.json"
    if not args.skip_freeze_check:
        _run(
            "enrichment_fingerprint_dump",
            [PY, str(_SCRIPT_DIR / "verify_built_enrichment_freeze.py"), "--dump", str(freeze_before)],
        )

    do_enrich = should_run_enrich(enrich=args.enrich, skip_enrich=args.skip_enrich)
    if do_enrich:
        _run(
            "recover_from_parcel enrich",
            [
                PY,
                "-m",
                "built.recover_from_parcel",
                "--sido",
                "all",
                "--min-year",
                "2019",
                "--apply-enrichment",
            ],
            cwd=PIPELINE,
        )
    else:
        log.info("skip-enrich: 마트는 원장만. 미상 INSERT 안 함 (D-051 전)")

    if not args.skip_freeze_check:
        _run(
            "verify_built_enrichment_freeze",
            [
                PY,
                str(_SCRIPT_DIR / "verify_built_enrichment_freeze.py"),
                "--before",
                str(freeze_before),
                "--output",
                str(freeze_report),
            ],
        )

    snap_out = REPO / "clean_snapshots" / cycle / "built" / "built_tx_counts_after.json"
    _run(
        "snapshot_built_tx_counts",
        [PY, str(_SCRIPT_DIR / "snapshot_built_tx_counts.py"), "--output", str(snap_out), "--cycle-id", cycle],
    )

    if not args.skip_mapping_check:
        _run(
            "verify_beopjungri_mapping",
            [PY, str(PIPELINE / "verify_beopjungri_mapping.py"), "--cycle-id", cycle],
            cwd=PIPELINE,
        )

    total = time.perf_counter() - cycle_t0
    log.info("built_cycle_csv 완료: %.1fs (%.2f분) as_of=%s", total, total / 60, as_of)
    log.info(
        "다음: compare_built_count_snapshots --before clean_snapshots/%s/built/built_tx_counts_before.json "
        "--after %s",
        cycle,
        snap_out,
    )


if __name__ == "__main__":
    main()
