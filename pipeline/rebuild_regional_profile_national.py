#!/usr/bin/env python3
"""
전국 Regional Profile + Profile 기반 Twin — Phase 1 orchestrator.

순서:
  1. land_upper_stats_v2 → market_stats (land_* domain, 전국)
  2. collective_transactions → market_stats (apartment/rowhouse/officetel, 전국)
  3. market_stats + population + composition → regional_profile (v1.1-national)
  4. regional_profile → twin_eupmyeondong_neighbor_mvp (Profile 소비)

예:
  cd pipeline
  python rebuild_regional_profile_national.py --dry-run
  python rebuild_regional_profile_national.py --skip-collective --skip-twin
  python rebuild_regional_profile_national.py --windows 5
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

DEFAULT_PROFILE_VERSION = "v1.1-national"


def _run(cmd: list[str], *, dry_run: bool) -> None:
    log.info("run: %s", " ".join(cmd))
    if dry_run:
        return
    subprocess.run(cmd, cwd=PIPE, check=True)


def main() -> None:
    p = argparse.ArgumentParser(description="전국 regional profile + twin rebuild")
    p.add_argument("--as-of", type=str, default=None)
    p.add_argument("--windows", type=str, default="3,5")
    p.add_argument("--profile-version", type=str, default=DEFAULT_PROFILE_VERSION)
    p.add_argument("--skip-land", action="store_true")
    p.add_argument("--skip-collective", action="store_true", help="집합 market_stats 생략")
    p.add_argument("--skip-profile", action="store_true")
    p.add_argument("--skip-twin", action="store_true")
    p.add_argument(
        "--twin-mode",
        choices=("profile", "hybrid", "both"),
        default="hybrid",
        help="profile=v5 only, hybrid=v6 (default), both",
    )
    p.add_argument("--include-extended-land", action="store_true")
    p.add_argument("--collective-rolling-only", action="store_true")
    p.add_argument("--twin-top-k", type=int, default=20)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    py = sys.executable
    as_of_args = ["--as-of", args.as_of] if args.as_of else []
    profile_windows = [int(x.strip()) for x in args.windows.split(",") if x.strip()]

    if not args.skip_land:
        cmd = [py, "build_land_market_stats.py", "--windows", args.windows, *as_of_args]
        if args.include_extended_land:
            cmd.append("--include-extended")
        _run(cmd, dry_run=args.dry_run)

    if not args.skip_collective:
        cmd = [py, "build_collective_market_stats.py", "--windows", args.windows, *as_of_args]
        if args.collective_rolling_only:
            cmd.append("--rolling-only")
        _run(cmd, dry_run=args.dry_run)

    if not args.skip_profile:
        for wy in profile_windows:
            cmd = [
                py,
                "build_regional_profile.py",
                "--profile-version",
                args.profile_version,
                "--window-years",
                str(wy),
                *as_of_args,
            ]
            _run(cmd, dry_run=args.dry_run)

    if not args.skip_twin:
        twin_builders: list[tuple[str, str]] = []
        if args.twin_mode in ("profile", "both"):
            twin_builders.append(("build_twin_from_profile.py", "profile"))
        if args.twin_mode in ("hybrid", "both"):
            twin_builders.append(("build_twin_hybrid.py", "hybrid"))
        for wy in profile_windows:
            for script, _label in twin_builders:
                cmd = [
                    py,
                    script,
                    "--profile-version",
                    args.profile_version,
                    "--window-years",
                    str(wy),
                    "--top-k",
                    str(args.twin_top_k),
                    *as_of_args,
                ]
                _run(cmd, dry_run=args.dry_run)

    log.info(
        "전국 regional profile rebuild %s (version=%s windows=%s)",
        "dry-run 완료" if args.dry_run else "완료",
        args.profile_version,
        profile_windows,
    )


if __name__ == "__main__":
    main()
