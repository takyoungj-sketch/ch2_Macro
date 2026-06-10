#!/usr/bin/env python3
"""
raw/토지_2010_2020/*.csv → collect → clean → (선택) build_annual_stats

예)
  py scripts/monthly/ingest_land_historical_csv.py
  py scripts/monthly/ingest_land_historical_csv.py --sido-code 43,44 --build-annual
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PIPELINE = REPO_ROOT / "pipeline"
DEFAULT_RAW = REPO_ROOT / "raw" / "토지_2010_2020"
PY = sys.executable


def run(cmd: list[str], *, cwd: Path = PIPELINE) -> None:
    print(">", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True, cwd=str(cwd))


def main() -> None:
    p = argparse.ArgumentParser(description="토지 historical CSV ingest (collect → clean → annual)")
    p.add_argument(
        "--directory",
        default=str(DEFAULT_RAW),
        help=f"CSV 폴더 (기본 {DEFAULT_RAW})",
    )
    p.add_argument(
        "--skip-collect",
        action="store_true",
        help="collect 생략 (이미 raw 적재됨)",
    )
    p.add_argument(
        "--skip-clean",
        action="store_true",
        help="clean 생략",
    )
    p.add_argument(
        "--build-annual",
        action="store_true",
        help="clean 후 build_annual_stats.py 실행",
    )
    p.add_argument(
        "--years",
        default="2010-2026",
        help="build_annual_stats --years (예: 2010-2026)",
    )
    p.add_argument(
        "--with-upper",
        action="store_true",
        help="build_annual_stats 에 --with-upper 전달 (상위 행정 연도 마트)",
    )
    p.add_argument(
        "--sido-code",
        default="",
        help="build_annual_stats --sido-code (쉼표 구분, 예: 43,44)",
    )
    args = p.parse_args()

    raw_dir = Path(args.directory).expanduser().resolve()
    if not raw_dir.is_dir():
        print(f"폴더 없음: {raw_dir}", file=sys.stderr)
        sys.exit(1)

    if not args.skip_collect:
        run(
            [
                PY,
                "collect.py",
                "--mode",
                "excel",
                "--directory",
                str(raw_dir),
                "--format",
                "csv",
            ]
        )

    if not args.skip_clean:
        run([PY, "clean.py"])

    if args.build_annual:
        annual_cmd = [PY, "build_annual_stats.py", "--years", args.years]
        if args.with_upper:
            annual_cmd.append("--with-upper")
        if args.sido_code.strip():
            for sc in args.sido_code.split(","):
                sc = sc.strip()
                if sc:
                    annual_cmd.extend(["--sido-code", sc])
        run(annual_cmd)


if __name__ == "__main__":
    main()
