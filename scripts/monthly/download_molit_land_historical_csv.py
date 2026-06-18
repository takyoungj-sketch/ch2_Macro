#!/usr/bin/env python3
"""
국토교통부 실거래가 CSV 수집 (토지 매매 · 2010~2020 등 장기 backfill용).

기본 출력: `<repo>/raw/토지_2010_2020/<시도>_토지_매매_<연도>.csv`

수집 코어: molit_csv_download_core. docs/MOLIT_CSV_COLLECTOR_WARNINGS.md
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from land_historical_csv_status import write_manifest  # noqa: E402
from molit_csv_download_core import CollectSpec, run_molit_csv_collect  # noqa: E402

DEFAULT_OUTPUT_DIR = REPO_ROOT / "raw" / "토지_2010_2020"

DEFAULT_SIDO_LIST = [
    "서울특별시", "부산광역시", "대구광역시", "인천광역시", "광주광역시",
    "대전광역시", "울산광역시", "세종특별자치시", "경기도", "강원특별자치도",
    "충청북도", "충청남도", "전북특별자치도", "전라남도", "경상북도", "경상남도",
    "제주특별자치도",
]


def resolve_regions(args: argparse.Namespace) -> list[str]:
    if args.regions.strip():
        return [r.strip() for r in args.regions.split(",") if r.strip()]
    out = list(DEFAULT_SIDO_LIST)
    if args.limit_regions and args.limit_regions > 0:
        out = out[: args.limit_regions]
    return out


def resolve_years(args: argparse.Namespace) -> list[int]:
    if args.years.strip():
        return [int(y.strip()) for y in args.years.split(",") if y.strip()]
    return list(range(args.start_year, args.end_year + 1))


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Molit 토지 CSV backfill")
    p.add_argument("--output-dir", default="")
    p.add_argument("--start-year", type=int, default=2010)
    p.add_argument("--end-year", type=int, default=2020)
    p.add_argument("--years", default="")
    p.add_argument("--regions", default="")
    p.add_argument("--limit-regions", type=int, default=0)
    p.add_argument("--headless", action="store_true")
    p.add_argument("--max-new-downloads", type=int, default=100)
    return p


def main() -> None:
    args = build_parser().parse_args()
    regions = resolve_regions(args)
    years = resolve_years(args)
    if not regions or not years:
        sys.exit(1)

    download_dir = (
        Path(args.output_dir.strip()).expanduser().resolve()
        if args.output_dir.strip()
        else DEFAULT_OUTPUT_DIR.resolve()
    )
    if years != list(range(min(years), max(years) + 1)):
        print("비연속 --years 는 연도별로 나눠 실행하세요.")
        sys.exit(1)

    spec = CollectSpec(
        tab_id=7,
        type_label_ko="토지",
        deal_type="매매",
        output_dir=download_dir,
        start_year=min(years),
        end_year=max(years),
        regions=regions,
        max_new_downloads=args.max_new_downloads,
        headless=args.headless,
    )
    result = run_molit_csv_collect(spec, log=print)
    write_manifest(
        download_dir,
        regions=regions,
        stats={
            "done": result.done,
            "skipped": result.skipped,
            "failed": result.failed,
            "revalidated_bad": result.revalidated_bad,
        },
        stopped_reason=result.stopped_reason,
    )


if __name__ == "__main__":
    main()
