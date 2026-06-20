#!/usr/bin/env python3
"""
충북 Regional Profile 파일럿 — land market → (집합 market) → profile.

예:
  cd pipeline
  python rebuild_regional_profile_chungbuk.py
  python rebuild_regional_profile_chungbuk.py --skip-collective
"""

from __future__ import annotations

import argparse
import logging
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PIPE = REPO / "pipeline"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


def _run(cmd: list[str]) -> None:
    log.info("run: %s", " ".join(cmd))
    subprocess.run(cmd, cwd=PIPE, check=True)


def main() -> None:
    p = argparse.ArgumentParser(description="충북 regional profile 파일럿 rebuild")
    p.add_argument("--as-of", type=str, default=None)
    p.add_argument("--windows", type=str, default="3,5")
    p.add_argument("--window-years", type=int, default=5, help="profile 창 (기본 5)")
    p.add_argument("--profile-version", type=str, default="v1.0-chungbuk")
    p.add_argument("--skip-collective", action="store_true", help="집합 market_stats 생략")
    p.add_argument("--skip-land", action="store_true")
    p.add_argument("--skip-profile", action="store_true")
    p.add_argument("--include-extended-land", action="store_true")
    args = p.parse_args()

    py = sys.executable
    as_of_args = ["--as-of", args.as_of] if args.as_of else []

    if not args.skip_land:
        cmd = [
            py,
            "build_land_market_stats.py",
            "--sido-code",
            "43",
            "--windows",
            args.windows,
            *as_of_args,
        ]
        if args.include_extended_land:
            cmd.append("--include-extended")
        _run(cmd)

    if not args.skip_collective:
        cmd = [
            py,
            "build_collective_market_stats.py",
            "--addr1",
            "충청북도",
            "--windows",
            args.windows,
            *as_of_args,
        ]
        _run(cmd)

    if not args.skip_profile:
        cmd = [
            py,
            "build_regional_profile.py",
            "--sido-code",
            "43",
            "--profile-version",
            args.profile_version,
            "--window-years",
            str(args.window_years),
            *as_of_args,
        ]
        _run(cmd)

    log.info("충북 regional profile rebuild 완료")


if __name__ == "__main__":
    main()
