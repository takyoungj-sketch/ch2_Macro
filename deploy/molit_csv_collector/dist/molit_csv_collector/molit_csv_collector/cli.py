"""CLI 진입점 (GUI 없이 실행)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import DEFAULT_MAX_NEW_DOWNLOADS, DEFAULT_SIDO_LIST, get_property_type
from .downloader import DownloadJob, run_download


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="국토부 실거래 CSV 수집 (CLI)")
    p.add_argument("--property-type", default="apartment", help="apartment, land, …")
    p.add_argument(
        "--deal-type",
        default="sale",
        choices=["sale", "rent", "매매", "전월세"],
        help="거래 구분 (아파트·연립·단독·오피스텔만 전월세)",
    )
    p.add_argument("--start-year", type=int, default=2010)
    p.add_argument("--start-month", type=int, default=1)
    p.add_argument("--end-year", type=int, default=2020)
    p.add_argument("--end-month", type=int, default=12)
    p.add_argument("--output-dir", required=True, help="CSV 저장 폴더")
    p.add_argument(
        "--max-new-downloads",
        type=int,
        default=DEFAULT_MAX_NEW_DOWNLOADS,
        help="신규 다운로드 상한 (1~100)",
    )
    p.add_argument(
        "--regions",
        default="",
        help="시도 쉼표 구분 (비우면 전국 17개)",
    )
    p.add_argument("--headless", action="store_true")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    pt = get_property_type(args.property_type, deal_type=args.deal_type)
    regions = (
        [r.strip() for r in args.regions.split(",") if r.strip()]
        if args.regions.strip()
        else list(DEFAULT_SIDO_LIST)
    )
    job = DownloadJob(
        property_type=pt,
        start_year=args.start_year,
        start_month=args.start_month,
        end_year=args.end_year,
        end_month=args.end_month,
        output_dir=Path(args.output_dir),
        regions=regions,
        max_new_downloads=args.max_new_downloads,
        headless=args.headless,
    )

    def _log_level(level: str, msg: str) -> None:
        prefix = "[FAIL] " if level == "fail" else ""
        print(f"{prefix}{msg}")

    run_download(job, log_level=_log_level)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
