#!/usr/bin/env python3
"""대전 vs 충북 M2 + 대전 hold-out 고정 전이."""

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
from app.collective.new_apt.constants import SIDO_CHUNGBUK, SIDO_DAEJEON  # noqa: E402
from app.collective.new_apt.regional import run_region_compare  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--output",
        default=str(REPO / "pipeline" / "rent" / "_new_apt_region_compare.json"),
    )
    args = p.parse_args()
    engine = get_collective_engine()
    dj = pd.read_sql(
        text("SELECT * FROM new_apartment_complex_year WHERE sido_code = :sido"),
        engine,
        params={"sido": SIDO_DAEJEON},
    )
    cb = pd.read_sql(
        text("SELECT * FROM new_apartment_complex_year WHERE sido_code = :sido"),
        engine,
        params={"sido": SIDO_CHUNGBUK},
    )
    if dj.empty or cb.empty:
        log.error("마트 부족 — daejeon=%s chungbuk=%s", len(dj), len(cb))
        sys.exit(1)
    result = run_region_compare(dj, cb)
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("wrote %s", path)
    for row in result["models"]:
        log.info(
            "%s %s n=%s adjR2=%s mape=%s land=%s hh=%s floor=%s park=%s hold=%s",
            row["id"],
            row["region"],
            row["n_train"],
            row.get("adj_r_squared"),
            row.get("holdout_mape"),
            row.get("land_coef"),
            row.get("households_coef"),
            row.get("floor_coef"),
            row.get("parking_coef"),
            row.get("hold_scope"),
        )
    verdict = result["transfer"]["verdict"]
    log.info("transfer delta=%s code=%s adopt=%s", verdict.get("delta_mape"), verdict.get("code"), result["adopt_pooled"])
    log.info("%s", verdict.get("summary"))


if __name__ == "__main__":
    main()
