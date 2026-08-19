#!/usr/bin/env python3
"""트랙 A 본선(M0→M1-A→M2-A→M3-A) vs 진단 B/C — hold-out MAE/MAPE."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import text

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend"))
sys.path.insert(0, str(REPO / "pipeline"))

from collective.db_utils import get_collective_engine  # noqa: E402
from app.collective.new_apt.constants import SIDO_DAEJEON  # noqa: E402
from app.collective.new_apt.models import run_comparison  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--sido-code", default=SIDO_DAEJEON)
    p.add_argument(
        "--output",
        default=str(REPO / "pipeline" / "rent" / "_new_apt_a2_daejeon.json"),
    )
    args = p.parse_args()
    engine = get_collective_engine()
    df = pd.read_sql(
        text("SELECT * FROM new_apartment_complex_year WHERE sido_code = :sido"),
        engine,
        params={"sido": args.sido_code},
    )
    if df.empty:
        log.error("mart 없음 — build_new_apartment_dataset.py 먼저")
        sys.exit(1)
    result = run_comparison(df)
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("wrote %s  cells=%s holdout_bld=%s", path, result["n_cells_land"], result["n_holdout_buildings"])
    for row in result["table"]:
        log.info(
            "%s %s loc=%s %s n=%s adjR2=%s mape=%s land_b=%s",
            row.get("track"),
            row.get("product"),
            row.get("location"),
            row.get("sample"),
            row["n_train"],
            row["adj_r_squared"],
            row["holdout_mape"],
            row.get("land_coef"),
        )


if __name__ == "__main__":
    main()
