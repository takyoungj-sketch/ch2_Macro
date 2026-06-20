#!/usr/bin/env python3
"""비주거 집합(상가·공장) raw base → ingest 오케스트레이터.

주거 재구축(`rebuild_collective_residential.py`)과 동일 패턴.
장기 추세(2010~2020) annual mart + 2021~ cluster annual build 포함.
"""

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
    p = argparse.ArgumentParser(description="비주거 집합부동산 MOLIT raw base 재구축")
    p.add_argument("--as-of", default=AS_OF, help="mart as_of_month (2차: cluster mart 도입 시)")
    p.add_argument("--source", choices=("molit", "gukto"), default="molit", help="ingest 소스")
    p.add_argument("--skip-ingest", action="store_true")
    p.add_argument("--skip-meta", action="store_true")
    p.add_argument("--skip-marts", action="store_true")
    p.add_argument("--shop-only", action="store_true")
    p.add_argument("--factory-only", action="store_true")
    p.add_argument("--skip-long-term", action="store_true", help="2010~2020 annual mart ingest 생략")
    p.add_argument("--skip-annual", action="store_true", help="2021~ cluster annual build 생략")
    p.add_argument("--no-truncate", action="store_true", help="기존 commercial 테이블 유지(증분 테스트용)")
    args = p.parse_args()

    if not args.skip_ingest:
        ingest_cmd = [
            PY,
            "collective_commercial/import_refined.py",
            "--source",
            args.source,
        ]
        if args.shop_only:
            ingest_cmd.append("--shop-only")
        if args.factory_only:
            ingest_cmd.append("--factory-only")
        if not args.no_truncate:
            ingest_cmd.append("--truncate")
        _run(ingest_cmd)

    if not args.skip_meta:
        _run([PY, "build_region_sigungu_meta.py", "--collective"])

    if not args.skip_marts:
        _run([PY, "build_collective_cluster_stats.py", "--as-of", args.as_of, "--windows", "3,5"])
        _run([PY, "build_collective_cluster_rolling_stats.py", "--as-of", args.as_of, "--windows", "3,5"])

    if not args.skip_long_term:
        lt_cmd = [PY, "ingest_collective_commercial_long_term_annual.py"]
        if args.shop_only:
            lt_cmd.extend(["--asset-type", "collective_shop"])
        elif args.factory_only:
            lt_cmd.extend(["--asset-type", "collective_factory"])
        _run(lt_cmd)

    if not args.skip_annual:
        _run([PY, "build_collective_cluster_annual_stats.py", "--skip-ddl"])

    log.info("collective commercial rebuild pipeline complete (as_of=%s)", args.as_of)


if __name__ == "__main__":
    main()
