#!/usr/bin/env python3
"""
집합부동산 월간 cycle — 2607업데이트 CSV(12개월) purge + ingest + mart.

주거 4유형(아파트·연립·오피스텔·분양) + 집합상가·집합공장(상업업무·공장창고 CSV).

  py scripts/monthly/run_collective_cycle_csv.py --cycle-id YYYYMM --attr-snapshot-ym 202607 --kapt-file K-apt.xlsx
  py scripts/monthly/run_collective_cycle_csv.py --cycle-id YYYYMM --attr-snapshot-ym 202607 --kapt-file K-apt.xlsx --dry-run

속성 판은 --attr-snapshot-ym 만 쓴다. cycle-id 와 K-apt 파일 이름으로 판을 정하지 않는다.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from ledger_supply_step import ledger_step  # noqa: E402

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
        help="마트 뒤 주거 집합 신규 키 공시지가 공급 생략",
    )
    p.add_argument(
        "--enrich-new-keys",
        action="store_true",
        help="주거 집합 신규 키의 대표필지 공시지가 공급 (기본값)",
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
    p.add_argument(
        "--attr-snapshot-ym",
        default=None,
        help="단지 속성 판 YYYYMM. 파일 이름·cycle-id·최신 판으로 정하지 않는다. 지금 판은 202607",
    )
    p.add_argument(
        "--kapt-file",
        default=None,
        help="K-apt 단지 기본정보 xlsx. 속성 단계에 --attr-snapshot-ym 과 함께 필요",
    )
    p.add_argument(
        "--skip-attributes",
        action="store_true",
        help="속성 없는 키의 K-apt·title_fill 생략. 실거래만 다시 돌릴 때",
    )
    return p


_SNAPSHOT_YM = re.compile(r"^20\d{2}(?:0[1-9]|1[0-2])$")

ATTRIBUTE_GAP_SQL = """
SELECT t.building_key
FROM collective_transactions t
WHERE t.is_valid = true
  AND t.asset_type IN ('apartment', 'rowhouse', 'officetel')
  AND t.building_key IS NOT NULL
  AND BTRIM(t.building_key) <> ''
  AND NOT EXISTS (
    SELECT 1
    FROM collective_building_attributes a
    WHERE a.snapshot_ym = :ym
      AND a.asset_type = t.asset_type
      AND a.building_key = t.building_key
  )
GROUP BY t.building_key
ORDER BY t.building_key
"""


def should_run_enrich(*, enrich_new_keys: bool, skip_enrich: bool) -> bool:
    if skip_enrich:
        return False
    return True


def require_attribute_args(
    *,
    skip: bool,
    snapshot_ym: str | None,
    kapt_file: str | None,
) -> tuple[str, Path] | None:
    """속성 단계 인자. 판은 호출자가 적은 YYYYMM 만 받는다."""
    if skip:
        return None
    if not snapshot_ym or not kapt_file:
        raise SystemExit(
            "속성 단계는 --attr-snapshot-ym YYYYMM 과 --kapt-file 이 둘 다 필요하다. "
            "판은 파일 이름·cycle-id·최신 판으로 정하지 않는다. "
            "실거래만 다시 돌리려면 --skip-attributes."
        )
    ym = snapshot_ym.strip()
    if not _SNAPSHOT_YM.fullmatch(ym):
        raise SystemExit(f"속성 판은 YYYYMM 이어야 한다: {snapshot_ym}")
    path = Path(kapt_file)
    if not path.is_file():
        raise SystemExit(f"K-apt 파일이 없다: {path}")
    return ym, path


def guard_existing_snapshot(row_count: int, snapshot_ym: str) -> None:
    """빈 판이면 모든 단지가 새 키가 되어 판 전체가 생긴다."""
    if row_count <= 0:
        raise SystemExit(
            f"속성 판 {snapshot_ym} 에 기존 행이 없다. "
            "빈 판은 만들지 않는다. 파일 이름이나 cycle-id 로 새 판을 열지 않는다."
        )


def format_gap_key_file(snapshot_ym: str, keys: list[str]) -> str:
    lines = [f"# snapshot_ym={snapshot_ym} 속성 행이 없는 키"]
    lines.extend(keys)
    return "\n".join(lines) + "\n"


def attribute_fill_commands(
    *,
    py: str,
    pipeline: Path,
    snapshot_ym: str,
    kapt_file: Path,
    keys_file: Path,
) -> list[tuple[str, list[str], Path]]:
    """속성 없는 키만 추가한다. --replace 와 대장 달 갱신은 넣지 않는다."""
    if not _SNAPSHOT_YM.fullmatch(snapshot_ym):
        raise SystemExit(f"속성 판은 YYYYMM 이어야 한다: {snapshot_ym}")
    kapt_cmd = [
        py,
        str(pipeline / "build_collective_building_attributes.py"),
        "--snapshot-ym",
        snapshot_ym,
        "--kapt-file",
        str(kapt_file),
        "--asset-type",
        "apartment",
        "--new-keys-only",
        "--keys-file",
        str(keys_file),
    ]
    title_cmd = [
        py,
        "-m",
        "parcel_master.apply_title_fill",
        "--snapshot-ym",
        snapshot_ym,
        "--new-keys-only",
        "--keys-file",
        str(keys_file),
    ]
    for cmd in (kapt_cmd, title_cmd):
        if "--replace" in cmd or "--refresh-t" in cmd:
            raise SystemExit("속성 단계는 판 전체를 다시 쓰지 않는다")
    return [
        ("kapt_new_keys", kapt_cmd, pipeline),
        ("title_fill_new_keys", title_cmd, pipeline),
    ]


def attribute_commands_for_gap(
    *,
    py: str,
    pipeline: Path,
    snapshot_ym: str,
    kapt_file: Path,
    keys_file: Path,
    keys: list[str],
) -> list[tuple[str, list[str], Path]]:
    if not keys:
        return []
    return attribute_fill_commands(
        py=py,
        pipeline=pipeline,
        snapshot_ym=snapshot_ym,
        kapt_file=kapt_file,
        keys_file=keys_file,
    )


def _collective_engine():
    if str(PIPELINE) not in sys.path:
        sys.path.insert(0, str(PIPELINE))
    from build_collective_building_attributes import db_url
    from sqlalchemy import create_engine

    return create_engine(db_url(), pool_pre_ping=True)


def run_attribute_step(*, cycle: str, attr: tuple[str, Path] | None, dry_run: bool) -> None:
    if attr is None:
        log.info("속성 단계 생략 (--skip-attributes)")
        return
    snapshot_ym, kapt_file = attr
    from sqlalchemy import text

    engine = _collective_engine()
    with engine.connect() as conn:
        row_count = conn.execute(
            text("SELECT COUNT(*) FROM collective_building_attributes WHERE snapshot_ym = :ym"),
            {"ym": snapshot_ym},
        ).scalar()
        guard_existing_snapshot(int(row_count or 0), snapshot_ym)
        found = conn.execute(text(ATTRIBUTE_GAP_SQL), {"ym": snapshot_ym}).fetchall()
    keys = [str(row[0]).strip() for row in found if row[0] and str(row[0]).strip()]
    keys_path = REPO / "logs" / f"collective_cycle_{cycle}_attribute_gap_keys.txt"
    keys_path.parent.mkdir(parents=True, exist_ok=True)
    keys_path.write_text(format_gap_key_file(snapshot_ym, keys), encoding="utf-8")
    log.info("속성 없는 키 %s곳 → %s (판 %s)", len(keys), keys_path, snapshot_ym)
    commands = attribute_commands_for_gap(
        py=PY,
        pipeline=PIPELINE,
        snapshot_ym=snapshot_ym,
        kapt_file=kapt_file,
        keys_file=keys_path,
        keys=keys,
    )
    if not commands:
        log.info("속성 없는 키가 없어 K-apt·title_fill 을 호출하지 않는다")
        return
    if dry_run:
        for phase, cmd, _cwd in commands:
            log.info("[dry-run %s] %s", phase, " ".join(cmd))
        log.info("dry-run: 속성 단계는 실행하지 않는다")
        return
    for phase, cmd, cwd in commands:
        _run(phase, cmd, cwd=cwd)


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
    attr = require_attribute_args(
        skip=args.skip_attributes,
        snapshot_ym=args.attr_snapshot_ym,
        kapt_file=args.kapt_file,
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
        log.info("dry-run: ingest/stats 및 신규 키 공급 생략")
        run_attribute_step(cycle=cycle, attr=attr, dry_run=True)
        return

    t0 = time.perf_counter()
    do_enrich = should_run_enrich(enrich_new_keys=args.enrich_new_keys, skip_enrich=args.skip_enrich)
    supply_ready = do_enrich and ledger_step(REPO, PY, log, "collective", "capture", cycle, y_from, y_to)

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

    if supply_ready:
        ledger_step(REPO, PY, log, "collective", "apply", cycle, y_from, y_to)

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

    run_attribute_step(cycle=cycle, attr=attr, dry_run=False)

    log.info("collective_cycle_csv 완료: %.1fs (%.2f분) as_of=%s", time.perf_counter() - t0, (time.perf_counter() - t0) / 60, as_of)
    log.info(
        "다음: compare_collective_count_snapshots --before clean_snapshots/%s/collective/collective_tx_counts_before.json "
        "--after %s",
        cycle,
        snap_out,
    )


if __name__ == "__main__":
    main()
