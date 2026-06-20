#!/usr/bin/env python3
"""collective_stats_next 생성 + 집합 Phase A DDL 적용."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from sqlalchemy import create_engine, text

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

REPO = Path(__file__).resolve().parents[1]
DB_DIR = REPO / "db"

COLLECTIVE_REBUILD_DDL = (
    "016_collective_transactions.sql",
    "017_collective_tx_row_identity.sql",
    "018_collective_land_area.sql",
    "019_collective_commercial.sql",
    "020_collective_commercial_road_width.sql",
    "022_region_rebuild.sql",
    "023_collective_building_stats.sql",
    "024_market_stats.sql",
    "025_regional_profile.sql",
    "026_regional_profile_data_product_patch.sql",
)

ADMIN_URL = "postgresql+psycopg2://postgres:8972@localhost:5432/postgres"
TARGET_DB = "collective_stats_next"


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
    p.add_argument(
        "--ddl-only",
        action="store_true",
        help="mart/profile DDL만 기존 DB에 적용 (023~025)",
    )
    args = p.parse_args()

    base = args.admin_url.rsplit("/", 1)[0]

    if args.ddl_only:
        db_url = f"{base}/{args.dbname}"
        _apply_ddl(
            db_url,
            (
                "023_collective_building_stats.sql",
                "024_market_stats.sql",
                "025_regional_profile.sql",
            ),
        )
        log.info("ddl-only complete: %s", db_url)
        return

    if not args.skip_create:
        _ensure_database(args.admin_url, args.dbname)

    db_url = f"{base}/{args.dbname}"
    _apply_ddl(db_url, COLLECTIVE_REBUILD_DDL)
    log.info("bootstrap complete: %s", db_url)


if __name__ == "__main__":
    main()
