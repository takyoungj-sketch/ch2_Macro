"""
집합부동산 월간 로컬 사이클(반자동):
  manifest → import_refined → 건수 스냅샷

사전 조건: docs/COLLECTIVE_MONTHLY_UPDATE_SOP.md — 토지 cycle 완료 후 권장.
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

from collective_cycle_utils import (  # noqa: E402
    collection_yyyymm_range_from_cycle_id,
    resolve_collective_xlsx_paths,
)

log = logging.getLogger(__name__)


def _run(phase: str, cmd: list[str], *, cwd: Path | None = None) -> None:
    log.info("[%s] %s", phase, " ".join(cmd))
    t0 = time.perf_counter()
    kw = {"cwd": str(cwd.resolve())} if cwd else {}
    subprocess.run(cmd, check=True, **kw)
    log.info("[%s] %.1fs", phase, time.perf_counter() - t0)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    p = argparse.ArgumentParser(description="월간 집합부동산 ingest")
    p.add_argument("--cycle-id", required=True)
    p.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[2])
    p.add_argument("--require-land-cycle", action="store_true")
    p.add_argument("--use-legacy-defaults", action="store_true")
    p.add_argument("--manifest-only", action="store_true")
    p.add_argument("--skip-ingest", action="store_true")
    p.add_argument("--no-refresh-region-codes", action="store_true")
    args = p.parse_args()

    repo = args.repo_root.resolve()
    cycle_id = args.cycle_id.strip()

    if args.require_land_cycle:
        land_snap = repo / "clean_snapshots" / cycle_id / "land_tx_counts_after.json"
        if not land_snap.is_file():
            raise SystemExit(f"land cycle snapshot missing: {land_snap}")

    paths = resolve_collective_xlsx_paths(repo, cycle_id, use_legacy=args.use_legacy_defaults)
    y_from, y_to = collection_yyyymm_range_from_cycle_id(cycle_id)
    out_dir = repo / "clean_snapshots" / cycle_id / "collective"
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "cycle_id": cycle_id,
        "collection_yyyymm_from": y_from,
        "collection_yyyymm_to": y_to,
        "paths": {k: str(v) for k, v in paths.items()},
    }
    (out_dir / "raw_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    log.info("manifest written: %s", out_dir / "raw_manifest.json")

    if args.manifest_only:
        return

    if args.skip_ingest:
        _run("snapshot", [sys.executable, str(_SCRIPT_DIR / "snapshot_collective_tx_counts.py"), "--cycle-id", cycle_id])
        return

    collective_dir = repo / "pipeline" / "collective"
    cmd = [sys.executable, "import_refined.py"]
    if not args.no_refresh_region_codes:
        cmd.append("--refresh-region-codes")
    if args.use_legacy_defaults:
        apt_dir = paths.get("apartment_dir")
        if isinstance(apt_dir, Path):
            cmd.extend(["--apartment-dir", str(apt_dir)])
        cmd.extend(["--rowhouse", str(paths["rowhouse"]), "--officetel", str(paths["officetel"])])
    _run("import_refined", cmd, cwd=collective_dir)

    _run(
        "snapshot",
        [sys.executable, str(_SCRIPT_DIR / "snapshot_collective_tx_counts.py"), "--cycle-id", cycle_id],
    )
    log.info("collective monthly cycle done: %s", cycle_id)


if __name__ == "__main__":
    main()
