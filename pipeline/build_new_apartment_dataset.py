#!/usr/bin/env python3
"""
신규아파트 회귀 트랙 A — 대전 단지×연도 마트 + Phase 0 리포트.

  py pipeline/build_new_apartment_dataset.py --sido-code 30 --replace
  py pipeline/build_new_apartment_dataset.py --sido-code 43 --replace --report pipeline/rent/_new_apt_phase0_chungbuk.json
  py pipeline/run_new_apartment_regression.py --sido-code 30
  py pipeline/run_new_apartment_region_compare.py
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend"))
sys.path.insert(0, str(REPO / "pipeline"))

from collective.db_utils import get_collective_engine, get_land_engine_for_region_copy  # noqa: E402
from rent.db_utils import get_rent_engine  # noqa: E402
from app.collective.new_apt.constants import SIDO_DAEJEON  # noqa: E402
from app.collective.new_apt.dataset import build_complex_year_frame, persist_complex_year, write_report  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


def apply_ddl(engine) -> None:
    ddl = (REPO / "db" / "064_new_apartment_regression.sql").read_text(encoding="utf-8")
    with engine.begin() as conn:
        conn.exec_driver_sql(ddl)


def main() -> None:
    p = argparse.ArgumentParser(description="신규아파트 단지×연도 마트")
    p.add_argument("--sido-code", default=SIDO_DAEJEON)
    p.add_argument("--raw-root", default=str(REPO / "raw"))
    p.add_argument(
        "--report",
        default=str(REPO / "pipeline" / "rent" / "_new_apt_phase0_daejeon.json"),
    )
    p.add_argument("--replace", action="store_true")
    p.add_argument("--skip-ddl", action="store_true")
    args = p.parse_args()

    coll = get_collective_engine()
    land = get_land_engine_for_region_copy()
    try:
        rent = get_rent_engine()
    except Exception as exc:  # noqa: BLE001
        log.warning("rent engine 없음: %s", exc)
        rent = None

    if not args.skip_ddl:
        apply_ddl(coll)

    df, report = build_complex_year_frame(
        coll, land, rent, sido=args.sido_code, raw_root=Path(args.raw_root)
    )
    write_report(Path(args.report), report)
    log.info("phase0: %s", {k: report[k] for k in ("n_buildings", "n_cells", "n_buildings_abc", "builders_ge_30", "land_join_pct")})
    n = persist_complex_year(coll, df, sido=args.sido_code, replace=args.replace)
    log.info("mart rows=%s", n)


if __name__ == "__main__":
    main()
