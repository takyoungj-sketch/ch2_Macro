#!/usr/bin/env python3
"""
전국 Regional Profile + Profile 기반 Twin — Phase 1 orchestrator.

순서:
  1. land_upper_stats_v2 → market_stats (land_* domain, 전국)
  2. collective_transactions → market_stats (apartment/rowhouse/officetel/presale, 전국)
  3. built_transactions → market_stats + built_annual_stats (commercial/factory/detached, D-027)
  4. collective_commercial_transactions → market_stats + region_annual_stats (집합상가·공장, D-027)
  5. market_stats + population + composition + jimok_group + yearly_mix → regional_profile
  6. regional_profile → profile-native Twin (build_twin_profile.py, algo 21)

예:
  cd pipeline
  python rebuild_regional_profile_national.py --dry-run
  python rebuild_regional_profile_national.py --skip-collective --skip-twin
  python rebuild_regional_profile_national.py --profile-version v2.1-national
  python verify_profile_twin_smoke.py
  # market_stats는 3·5 유지, Profile 적재는 3만 (기본)
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

DEFAULT_PROFILE_VERSION = "v2.1-national"
DEFAULT_MARKET_WINDOWS = "3,5"
DEFAULT_PROFILE_WINDOWS = "3"  # D-029: 지역프로필 제품 창 = 3년만


def _run(cmd: list[str], *, dry_run: bool) -> None:
    log.info("run: %s", " ".join(cmd))
    if dry_run:
        return
    subprocess.run(cmd, cwd=PIPE, check=True)


def _parse_windows(raw: str) -> list[int]:
    return [int(x.strip()) for x in raw.split(",") if x.strip()]


def main() -> None:
    p = argparse.ArgumentParser(description="전국 regional profile + twin rebuild")
    p.add_argument("--as-of", type=str, default=None)
    p.add_argument(
        "--windows",
        type=str,
        default=DEFAULT_MARKET_WINDOWS,
        help="market_stats 롤링 창 (토지·집합 분석용, 기본 3,5)",
    )
    p.add_argument(
        "--profile-windows",
        type=str,
        default=DEFAULT_PROFILE_WINDOWS,
        help="regional_profile 적재 창 (제품 SSOT, 기본 3만)",
    )
    p.add_argument("--profile-version", type=str, default=DEFAULT_PROFILE_VERSION)
    p.add_argument("--skip-land", action="store_true")
    p.add_argument("--skip-collective", action="store_true", help="집합 market_stats 생략")
    p.add_argument("--skip-built", action="store_true", help="상업업무/공장창고/단독다가구 market_stats 생략 (D-027)")
    p.add_argument("--skip-collective-commercial", action="store_true", help="집합상가/집합공장 market_stats 생략 (D-027)")
    p.add_argument("--skip-profile", action="store_true")
    p.add_argument("--skip-twin", action="store_true")
    p.add_argument(
        "--twin-mode",
        choices=("catalog", "legacy", "both"),
        default="catalog",
        help="catalog=build_twin_profile(v21), legacy=hybrid v6, both",
    )
    p.add_argument("--include-extended-land", action="store_true")
    p.add_argument("--collective-rolling-only", action="store_true")
    p.add_argument("--twin-top-k", type=int, default=20)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    py = sys.executable
    as_of_args = ["--as-of", args.as_of] if args.as_of else []
    market_windows = args.windows
    profile_windows = _parse_windows(args.profile_windows)

    if not args.skip_land:
        cmd = [py, "build_land_market_stats.py", "--windows", market_windows, *as_of_args]
        if args.include_extended_land:
            cmd.append("--include-extended")
        _run(cmd, dry_run=args.dry_run)

    if not args.skip_collective:
        cmd = [py, "build_collective_market_stats.py", "--windows", market_windows, *as_of_args]
        if args.collective_rolling_only:
            cmd.append("--rolling-only")
        _run(cmd, dry_run=args.dry_run)

    if not args.skip_built:
        cmd = [py, "build_built_market_stats.py", "--windows", market_windows, *as_of_args]
        _run(cmd, dry_run=args.dry_run)

    if not args.skip_collective_commercial:
        cmd = [py, "build_collective_commercial_market_stats.py", "--windows", market_windows, *as_of_args]
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
        twin_levels = ("eupmyeondong", "sigungu", "beopjungri")
        for wy in profile_windows:
            if args.twin_mode in ("catalog", "both"):
                for level in twin_levels:
                    cmd = [
                        py,
                        "build_twin_profile.py",
                        "--profile-version",
                        args.profile_version,
                        "--window-years",
                        str(wy),
                        "--region-level",
                        level,
                        "--top-k",
                        str(args.twin_top_k),
                        *as_of_args,
                    ]
                    _run(cmd, dry_run=args.dry_run)
            if args.twin_mode in ("legacy", "both"):
                for script in ("build_twin_from_profile.py", "build_twin_hybrid.py"):
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
        "전국 regional profile rebuild %s (version=%s market_windows=%s profile_windows=%s)",
        "dry-run 완료" if args.dry_run else "완료",
        args.profile_version,
        market_windows,
        profile_windows,
    )


if __name__ == "__main__":
    main()
