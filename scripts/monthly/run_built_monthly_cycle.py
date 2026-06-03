"""
복합부동산 월간 로컬 사이클(반자동):
  raw manifest → import_refined (region_codes refresh) → 건수 스냅샷

사전 조건: docs/BUILT_MONTHLY_UPDATE_SOP.md — **토지 월간 cycle 완료 후** 실행 권장.
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

from built_cycle_utils import (  # noqa: E402
    built_raw_root,
    collection_yyyymm_range_from_cycle_id,
    resolve_built_xlsx_paths,
)

log = logging.getLogger(__name__)


def _run_subprocess_timed(phase: str, cmd: list[str], *, cwd: Path | None = None) -> None:
    log.info("[%s]: %s", phase, " ".join(cmd))
    t0 = time.perf_counter()
    kwargs: dict[str, object] = {}
    if cwd is not None:
        kwargs["cwd"] = str(cwd.resolve())
    subprocess.run(cmd, check=True, **kwargs)
    sec = time.perf_counter() - t0
    log.info("[%s timing] %s 소요=%.1fs (%.2f분)", "built_monthly_cycle", phase, sec, sec / 60.0)


def _write_manifest(repo: Path, cycle_id: str, xlsx_paths: dict[str, Path]) -> Path:
    raw = built_raw_root(repo, cycle_id)
    y_from, y_to = collection_yyyymm_range_from_cycle_id(cycle_id)
    out_dir = repo / "clean_snapshots" / cycle_id / "built"
    out_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "cycle_id": cycle_id,
        "raw_root": str(raw),
        "collection_yyyymm_from": y_from,
        "collection_yyyymm_to": y_to,
        "asset_types": {
            asset: {
                "path": str(path),
                "path_relative": (
                    str(path.relative_to(raw))
                    if raw in path.parents or path.parent == raw
                    else str(path)
                ),
            }
            for asset, path in xlsx_paths.items()
        },
    }

    man_path = out_dir / "raw_manifest.json"
    man_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return man_path


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    p = argparse.ArgumentParser(description="월간 복합부동산 로컬 ingest (반자동)")
    p.add_argument("--cycle-id", required=True, help="작업 번들 ID (YYYYMM, 예: 202605)")
    p.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
        help="저장소 루트 (기본: ch2_Macro)",
    )
    p.add_argument(
        "--require-land-cycle",
        action="store_true",
        help="clean_snapshots/{cycle}/land_tx_counts_after.json 존재 시에만 진행",
    )
    p.add_argument("--manifest-only", action="store_true", help="manifest JSON 만 쓰고 종료")
    p.add_argument("--skip-ingest", action="store_true", help="manifest + 스냅샷만 (DB 변경 없음)")
    p.add_argument(
        "--no-refresh-region-codes",
        action="store_true",
        help="import 시 region_codes 덮어쓰기 생략 (기본: refresh)",
    )
    p.add_argument("--commercial-path", type=Path, help="정제 xlsx 직접 지정")
    p.add_argument("--factory-path", type=Path, help="정제 xlsx 직접 지정")
    p.add_argument("--detached-path", type=Path, help="정제 xlsx 직접 지정")
    p.add_argument("--commercial-only", action="store_true")
    p.add_argument("--factory-only", action="store_true")
    p.add_argument("--detached-only", action="store_true")
    p.add_argument(
        "--use-legacy-defaults",
        action="store_true",
        help="raw 폴더 없이 import_refined 기본 GUKTO 경로 사용 (전환기)",
    )
    args = p.parse_args()

    only_flags = sum([args.commercial_only, args.factory_only, args.detached_only])
    if only_flags > 1:
        raise SystemExit("--*-only flags are mutually exclusive")

    repo: Path = args.repo_root.expanduser().resolve()
    cycle = args.cycle_id.strip()

    if args.require_land_cycle:
        land_snap = repo / "clean_snapshots" / cycle / "land_tx_counts_after.json"
        if not land_snap.is_file():
            raise SystemExit(
                f"토지 월간 cycle 스냅샷이 없습니다: {land_snap}\n"
                "먼저 run_monthly_cycle.py 를 완료하거나 --require-land-cycle 를 끄세요."
            )
        log.info("land cycle snapshot OK: %s", land_snap)

    overrides = {
        "commercial": args.commercial_path,
        "factory": args.factory_path,
        "detached": args.detached_path,
    }

    if args.use_legacy_defaults:
        import importlib.util

        import_script = repo / "pipeline" / "built" / "import_refined.py"
        spec = importlib.util.spec_from_file_location("built_import_refined", import_script)
        if spec is None or spec.loader is None:
            raise SystemExit(f"cannot load {import_script}")
        ir = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(ir)
        xlsx_paths = {
            "commercial": ir.DEFAULT_COMMERCIAL,
            "factory": ir.DEFAULT_FACTORY,
            "detached": ir.DEFAULT_DETACHED,
        }
        log.warning("use-legacy-defaults: GUKTO 기본 경로 사용 (raw manifest 경로는 참고용)")
    else:
        xlsx_paths = resolve_built_xlsx_paths(repo, cycle, overrides=overrides)

    if only_flags:
        only_asset = (
            "commercial"
            if args.commercial_only
            else "factory"
            if args.factory_only
            else "detached"
        )
        xlsx_paths = {only_asset: xlsx_paths[only_asset]}

    man = _write_manifest(repo, cycle, xlsx_paths)
    log.info("manifest: %s", man)
    if args.manifest_only:
        return

    cycle_t0 = time.perf_counter()
    py = sys.executable
    import_script = repo / "pipeline" / "built" / "import_refined.py"

    if not args.skip_ingest:
        cmd = [py, str(import_script)]
        if not args.no_refresh_region_codes:
            cmd.append("--refresh-region-codes")
        for asset in xlsx_paths:
            cmd.extend([f"--{asset}", str(xlsx_paths[asset])])
        if args.commercial_only:
            cmd.append("--commercial-only")
        elif args.factory_only:
            cmd.append("--factory-only")
        elif args.detached_only:
            cmd.append("--detached-only")
        _run_subprocess_timed("import_refined", cmd, cwd=repo / "pipeline" / "built")
    else:
        log.info("skip-ingest: DB 변경 없음")

    snap_script = _SCRIPT_DIR / "snapshot_built_tx_counts.py"
    snap_out = repo / "clean_snapshots" / cycle / "built" / "built_tx_counts_after.json"
    _run_subprocess_timed(
        "snapshot_built_tx_counts",
        [py, str(snap_script), "--output", str(snap_out), "--cycle-id", cycle],
    )
    log.info("스냅샷: %s", snap_out)

    total_sec = time.perf_counter() - cycle_t0
    log.info(
        "[%s timing] built_monthly_cycle_total 소요=%.1fs (%.2f분)",
        "built_monthly_cycle",
        total_sec,
        total_sec / 60.0,
    )
    log.info(
        "다음: compare_built_count_snapshots / UI sanity check 후 built_stats promote (SOP §9)"
    )


if __name__ == "__main__":
    main()
