#!/usr/bin/env python3
"""주거 집합 4유형 raw base → ingest → mart 오케스트레이터."""

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
AS_OF = "2026-05-01"


def _run(cmd: list[str], *, cwd: Path = PIPE) -> None:
    log.info("RUN %s", " ".join(cmd))
    subprocess.run(cmd, cwd=str(cwd), check=True)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--as-of", default=AS_OF)
    p.add_argument("--skip-ingest", action="store_true")
    p.add_argument("--skip-marts", action="store_true")
    p.add_argument("--skip-long-term", action="store_true")
    p.add_argument("--skip-meta", action="store_true")
    p.add_argument(
        "--resume-from",
        metavar="FILENAME",
        help="ingest 재개: 해당 아파트 CSV부터 (--truncate-residential 사용 안 함)",
    )
    args = p.parse_args()

    if not args.skip_ingest:
        ingest_cmd = [PY, "collective/import_refined.py"]
        if args.resume_from:
            ingest_cmd.extend(["--resume-from", args.resume_from])
        else:
            ingest_cmd.append("--truncate-residential")
        _run(ingest_cmd)

    if not args.skip_meta:
        _run([PY, "build_region_sigungu_meta.py", "--collective"])

    if not args.skip_marts:
        _run([PY, "build_collective_building_stats.py", "--as-of", args.as_of, "--windows", "3,5"])
        _run([PY, "build_collective_building_rolling_stats.py", "--as-of", args.as_of, "--windows", "3,5"])
        _run([PY, "build_collective_market_stats.py", "--as-of", args.as_of, "--windows", "3,5"])

    if not args.skip_long_term:
        _run([PY, "ingest_collective_long_term_annual.py"])

    log.info("collective residential rebuild pipeline complete")


if __name__ == "__main__":
    main()
