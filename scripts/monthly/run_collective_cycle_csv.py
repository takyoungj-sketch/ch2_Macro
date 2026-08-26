#!/usr/bin/env python3
"""
집합부동산 월간 cycle — 2607업데이트 CSV(12개월) purge + ingest + mart.

주거 4유형(아파트·연립·오피스텔·분양) + 집합상가·집합공장(상업업무·공장창고 CSV).

  py scripts/monthly/run_collective_cycle_csv.py --cycle-id 202607
  py scripts/monthly/run_collective_cycle_csv.py --cycle-id 202607 --dry-run
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

RESIDENTIAL_DIRS = {
    "apartment": "아파트",
    "rowhouse": "연립다세대",
    "officetel": "오피스텔",
    "presale": "분양입주권",
}
COMMERCIAL_DIR_NAMES = ("상업업무", "공장창고")

log = logging.getLogger(__name__)


def _run(phase: str, cmd: list[str], *, cwd: Path | None = None) -> None:
    log.info("[%s] %s", phase, " ".join(cmd))
    t0 = time.perf_counter()
    kw = {"cwd": str(cwd)} if cwd else {}
    subprocess.run(cmd, check=True, **kw)
    log.info("[%s] %.1fs (%.2f분)", phase, time.perf_counter() - t0, (time.perf_counter() - t0) / 60)


def _resolve_folder(name: str, cycle_id: str, y_from: str, y_to: str) -> Path:
    found = resolve_csv_subdir(
        REPO,
        cycle_id,
        name,
        y_from,
        y_to,
        extra_candidates=[
            REPO / "raw" / "집합부동산" / cycle_id / name,
            REPO / "raw" / "raw base" / f"{name}_2021_2026",
        ],
    )
    if found is None:
        suffix = f"{y_from}_{y_to}"
        raise FileNotFoundError(f"{name}: CSV 폴더 없음 — cycle={cycle_id}, suffix={suffix}")
    return found


def _collect_csv_paths(folders: list[Path]) -> list[Path]:
    paths: list[Path] = []
    for folder in folders:
        paths.extend(sorted(folder.glob("*.csv"), key=lambda p: p.name.lower()))
    return paths


def _write_manifest(cycle_id: str, dirs: dict[str, Path], csv_paths: list[Path]) -> Path:
    out_dir = REPO / "clean_snapshots" / cycle_id / "collective"
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "cycle_id": cycle_id,
        "raw_dirs": {k: str(v) for k, v in dirs.items()},
        "csv_count": len(csv_paths),
        "csv_files": [p.name for p in csv_paths],
    }
    path = out_dir / "raw_manifest.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="집합부동산 월간 CSV cycle")
    p.add_argument("--cycle-id", required=True, help="YYYYMM (예: 202607)")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--skip-purge", action="store_true")
    p.add_argument("--skip-ingest", action="store_true")
    p.add_argument("--skip-commercial", action="store_true", help="집합상가·공장 ingest 생략")
    p.add_argument("--skip-stats", action="store_true")
    p.add_argument("--no-refresh-region-codes", action="store_true")
    p.add_argument("--skip-mapping-check", action="store_true")
    p.add_argument(
        "--skip-enrich",
        action="store_true",
        help="마트 뒤 신규 키 조인 생략. 플래그 없이도 기본은 skip",
    )
    p.add_argument(
        "--enrich-new-keys",
        action="store_true",
        help="속성 없는 building_key만 INSERT. A·B·C 안 덮음",
    )
    p.add_argument(
        "--refresh-title-t",
        action="store_true",
        help="거절. 대장 달: python -m parcel_master.apply_title_fill --refresh-t",
    )
    p.add_argument(
        "--refresh-land-price",
        action="store_true",
        help="거절. 공부 달: python -m collective.import_assessed_land_price --from-parcel-master",
    )
    return p


def should_run_enrich(*, enrich_new_keys: bool, skip_enrich: bool) -> bool:
    if skip_enrich:
        return False
    return bool(enrich_new_keys)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = build_parser().parse_args()
    if args.refresh_title_t:
        raise SystemExit(
            "실거래 달 러너는 --refresh-title-t 를 받지 않는다. "
            "대장 달: python -m parcel_master.apply_title_fill --refresh-t"
        )
    if args.refresh_land_price:
        raise SystemExit(
            "실거래 달 러너는 --refresh-land-price 를 받지 않는다. "
            "공부 달: python -m collective.import_assessed_land_price --from-parcel-master"
        )

    cycle = args.cycle_id.strip()
    y_from, y_to = collection_yyyymm_range_from_cycle_id(cycle)
    as_of = stats_as_of_iso_from_cycle_id(cycle)

    res_dirs = {k: _resolve_folder(v, cycle, y_from, y_to) for k, v in RESIDENTIAL_DIRS.items()}
    com_dirs = {n: _resolve_folder(n, cycle, y_from, y_to) for n in COMMERCIAL_DIR_NAMES}
    all_dirs = {**res_dirs, **{f"commercial_{k}": v for k, v in com_dirs.items()}}
    csv_paths = _collect_csv_paths(list(res_dirs.values()) + list(com_dirs.values()))

    paths_file = REPO / "logs" / f"collective_cycle_{cycle}_paths.txt"
    paths_file.parent.mkdir(parents=True, exist_ok=True)
    paths_file.write_text("\n".join(str(p) for p in csv_paths) + "\n", encoding="utf-8")

    man = _write_manifest(cycle, all_dirs, csv_paths)
    log.info("manifest: %s (%d CSV)", man, len(csv_paths))
    for k, d in all_dirs.items():
        log.info("  %s → %s", k, d)

    if args.dry_run:
        if not args.skip_purge:
            _run(
                "purge_collective_contract_window (dry-run)",
                [PY, str(PIPELINE / "purge_collective_contract_window.py"), "--cycle-id", cycle, "--dry-run"],
                cwd=PIPELINE,
            )
        log.info("dry-run: ingest/stats 생략. skip-enrich 기본")
        return

    t0 = time.perf_counter()

    if not args.skip_purge:
        _run(
            "purge_collective_contract_window",
            [PY, str(PIPELINE / "purge_collective_contract_window.py"), "--cycle-id", cycle],
            cwd=PIPELINE,
        )

    if not args.skip_ingest:
        res_cmd = [
            PY,
            str(PIPELINE / "collective" / "import_refined.py"),
            "--paths-file",
            str(paths_file),
            "--apartment-dir",
            str(res_dirs["apartment"]),
            "--rowhouse-dir",
            str(res_dirs["rowhouse"]),
            "--officetel-dir",
            str(res_dirs["officetel"]),
            "--presale-dir",
            str(res_dirs["presale"]),
        ]
        if not args.no_refresh_region_codes:
            res_cmd.append("--refresh-region-codes")
        _run("import_refined (residential)", res_cmd, cwd=PIPELINE)

        if not args.skip_commercial:
            com_cmd = [
                PY,
                str(PIPELINE / "collective_commercial" / "import_refined.py"),
                "--paths-file",
                str(paths_file),
                "--year-from",
                "2021",
                "--year-to",
                "2026",
            ]
            if not args.no_refresh_region_codes:
                com_cmd.append("--refresh-region-codes")
            _run("import_refined (commercial)", com_cmd, cwd=PIPELINE)

    if not args.skip_stats:
        _run("build_region_sigungu_meta", [PY, str(PIPELINE / "build_region_sigungu_meta.py"), "--collective"], cwd=PIPELINE)
        for script in (
            "build_collective_building_stats.py",
            "build_collective_building_rolling_stats.py",
            "build_collective_market_stats.py",
            "build_collective_presale_lifetime_stats.py",
        ):
            cmd = [PY, str(PIPELINE / script), "--as-of", as_of]
            if script != "build_collective_presale_lifetime_stats.py":
                cmd.extend(["--windows", "3,5,7"])
            else:
                cmd.append("--replace")
            _run(
                script.replace(".py", ""),
                cmd,
                cwd=PIPELINE,
            )
        if not args.skip_commercial:
            _run(
                "build_collective_commercial_cluster_stats",
                [PY, str(PIPELINE / "build_collective_commercial_cluster_stats.py"), "--as-of", as_of, "--windows", "3,5,7"],
                cwd=PIPELINE,
            )

    if should_run_enrich(enrich_new_keys=args.enrich_new_keys, skip_enrich=args.skip_enrich):
        _run(
            "enrich_new_keys",
            [PY, "-m", "collective.enrich_new_keys"],
            cwd=PIPELINE,
        )
    else:
        log.info("skip-enrich: 신규 키 조인 안 함. A·B·C 유지. 비주거 집합은 속성 테이블 없음")

    snap_out = REPO / "clean_snapshots" / cycle / "collective" / "collective_tx_counts_after.json"
    _run(
        "snapshot_collective_tx_counts",
        [
            PY,
            str(_SCRIPT_DIR / "snapshot_collective_tx_counts.py"),
            "--cycle-id",
            cycle,
            "--output",
            str(snap_out),
        ],
    )

    if not args.skip_mapping_check:
        _run(
            "verify_beopjungri_mapping",
            [PY, str(PIPELINE / "verify_beopjungri_mapping.py"), "--cycle-id", cycle],
            cwd=PIPELINE,
        )

    log.info("collective_cycle_csv 완료: %.1fs (%.2f분) as_of=%s", time.perf_counter() - t0, (time.perf_counter() - t0) / 60, as_of)
    log.info(
        "다음: compare_collective_count_snapshots --before clean_snapshots/%s/collective/collective_tx_counts_before.json "
        "--after %s",
        cycle,
        snap_out,
    )


if __name__ == "__main__":
    main()
