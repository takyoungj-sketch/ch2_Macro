#!/usr/bin/env python3
"""복합부동산 일반 3유형 — MOLIT raw base 원장 재구축 오케스트레이터 (Phase A)."""

from __future__ import annotations

import argparse
import logging
import subprocess
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

REPO = Path(__file__).resolve().parents[1]
PIPE = REPO / "pipeline"
PY = sys.executable


def _run(cmd: list[str], *, cwd: Path = PIPE) -> None:
    log.info("RUN %s", " ".join(cmd))
    subprocess.run(cmd, cwd=str(cwd), check=True)


def main() -> None:
    p = argparse.ArgumentParser(description="built_stats 원장 Phase A/B 재구축")
    p.add_argument("--smoke", action="store_true", help="서울 2021 CSV smoke")
    p.add_argument("--skip-ingest", action="store_true")
    p.add_argument("--skip-scope-stats", action="store_true", help="Phase B mart 생략")
    p.add_argument("--no-truncate", action="store_true", help="기본 TRUNCATE 생략 (smoke append)")
    p.add_argument("--refresh-region-codes", action="store_true")
    p.add_argument("--commercial-only", action="store_true")
    p.add_argument("--factory-only", action="store_true")
    p.add_argument("--detached-only", action="store_true")
    args = p.parse_args()

    if not args.skip_ingest:
        cmd = [PY, "built/import_molit.py", "--refresh-region-codes" if args.refresh_region_codes else ""]
        cmd = [c for c in cmd if c]
        if args.smoke:
            cmd.append("--smoke")
        elif not args.no_truncate:
            cmd.append("--truncate")
        if args.commercial_only:
            cmd.append("--commercial-only")
        if args.factory_only:
            cmd.append("--factory-only")
        if args.detached_only:
            cmd.append("--detached-only")
        _run(cmd)

    if not args.skip_scope_stats:
        _run([PY, "built/build_scope_stats.py"])

    log.info("built ledger rebuild complete")


if __name__ == "__main__":
    main()
