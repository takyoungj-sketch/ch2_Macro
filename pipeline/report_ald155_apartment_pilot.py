#!/usr/bin/env python3
"""AL_D155 아파트 exact join 파일럿 — 대전·충북 커버리지 JSON."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend"))
sys.path.insert(0, str(REPO / "pipeline"))

from build_stats_v2 import default_as_of_month, parse_as_of_month  # noqa: E402
from collective.db_utils import get_collective_engine, get_land_engine_for_region_copy  # noqa: E402
from app.collective.hedonic.enrichment import run_ald155_pilot  # noqa: E402


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--as-of", dest="as_of", default=None)
    p.add_argument("--windows", type=int, default=5)
    p.add_argument("--raw-root", default=str(REPO / "raw"))
    p.add_argument("--output", default=str(REPO / "pipeline" / "rent" / "_ald155_apartment_pilot.json"))
    args = p.parse_args()
    as_of = parse_as_of_month(args.as_of) if args.as_of else default_as_of_month()
    report = run_ald155_pilot(
        get_collective_engine(),
        Path(args.raw_root),
        land_engine=get_land_engine_for_region_copy(),
        as_of_month=as_of,
        window_years=args.windows,
        output_json=Path(args.output),
    )
    print(report.to_dict())


if __name__ == "__main__":
    main()
