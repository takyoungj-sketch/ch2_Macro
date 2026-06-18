#!/usr/bin/env python3
"""land_stats_next 생성 + 토지 재구축용 DDL 적용."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from sqlalchemy import create_engine, text

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

REPO = Path(__file__).resolve().parents[1]
DB_DIR = REPO / "db"

# 토지 원장·사전통계 재구축에 필요한 DDL (순서 유지)
LAND_REBUILD_DDL = (
    "001_init.sql",
    "002_indexes.sql",
    "003_legacy_patch.sql",
    "006_land_tx_raw_id_index.sql",
    "007_land_basic_stats_v2.sql",
    "008_land_transactions_v2_batch_index.sql",
    "009_land_transactions_mapping_review.sql",
    "011_land_transactions_display_columns.sql",
    "010_land_upper_stats_v2.sql",
    "012_twin_region_neighbor_mvp.sql",
    "013_twin_eupmyeondong_neighbor_mvp.sql",
    "014_land_annual_stats.sql",
    "021_land_annual_upper_stats.sql",
)

ADMIN_URL = "postgresql+psycopg2://postgres:8972@localhost:5432/postgres"
TARGET_DB = "land_stats_next"


def _ensure_database(admin_url: str, dbname: str) -> None:
    eng = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with eng.connect() as conn:
        exists = conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :n"),
            {"n": dbname},
        ).scalar()
        if exists:
            log.info("database %s already exists", dbname)
            return
        conn.execute(text(f'CREATE DATABASE "{dbname}"'))
        log.info("created database %s", dbname)


def _apply_ddl(db_url: str, files: tuple[str, ...]) -> None:
    eng = create_engine(db_url)
    for name in files:
        path = DB_DIR / name
        if not path.is_file():
            raise FileNotFoundError(path)
        sql = path.read_text(encoding="utf-8")
        log.info("apply %s", name)
        with eng.begin() as conn:
            conn.execute(text(sql))


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--admin-url", default=ADMIN_URL)
    p.add_argument("--dbname", default=TARGET_DB)
    p.add_argument("--skip-create", action="store_true")
    args = p.parse_args()

    if not args.skip_create:
        _ensure_database(args.admin_url, args.dbname)

    base = args.admin_url.rsplit("/", 1)[0]
    db_url = f"{base}/{args.dbname}"
    _apply_ddl(db_url, LAND_REBUILD_DDL)
    log.info("bootstrap complete: %s", db_url)


if __name__ == "__main__":
    main()
