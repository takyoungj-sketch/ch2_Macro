"""
구 DB(land_stats) → 신 DB(land_stats_next) population_stats 복사.

region_codes 가 동일하므로 annual 과 같이 구 마트 재사용.
추가 CSV 적재는 seed_population_csv.py 로 연도별 갱신.

예)
  python copy_population_from_legacy.py
  python copy_population_from_legacy.py --dry-run
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv(Path(__file__).resolve().parent / ".env.rebuild")
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger(__name__)

DEFAULT_SOURCE = "postgresql+psycopg2://postgres:8972@localhost:5432/land_stats"
DEFAULT_TARGET = os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg2://postgres:8972@localhost:5432/land_stats_next",
)

_COPY_COLS = """
    stats_year, stats_month, admin_code, admin_level,
    total_population, household_count, pop_change_rate, density_per_km2,
    source, loaded_at
""".strip()


def _pg_conn_str(sqlalchemy_url: str) -> str:
    from sqlalchemy.engine.url import make_url

    u = make_url(sqlalchemy_url.replace("+psycopg2", ""))
    host = u.host or "localhost"
    port = u.port or 5432
    user = u.username or "postgres"
    password = u.password or ""
    db = u.database or "land_stats"
    return f"host={host} port={port} dbname={db} user={user} password={password}"


def copy_population(
    source_url: str,
    target_url: str,
    *,
    dry_run: bool,
) -> int:
    source_engine = create_engine(source_url, pool_pre_ping=True)
    target_engine = create_engine(target_url, pool_pre_ping=True)

    with source_engine.connect() as conn:
        n_src = int(conn.execute(text("SELECT COUNT(*) FROM population_stats")).scalar() or 0)
        breakdown = conn.execute(
            text(
                """
                SELECT stats_year, stats_month, COUNT(*)::bigint
                FROM population_stats
                GROUP BY 1, 2 ORDER BY 1, 2
                """
            )
        ).fetchall()

    log.info("source population_stats rows: %s", f"{n_src:,}")
    for y, m, c in breakdown:
        log.info("  %d-%02d: %s rows", int(y), int(m or 0), f"{int(c):,}")

    if dry_run:
        return n_src

    conn_str = _pg_conn_str(source_url)
    remote_sql = f"SELECT {_COPY_COLS} FROM population_stats"

    with target_engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS dblink"))
        deleted = conn.execute(text("DELETE FROM population_stats")).rowcount
        log.info("target cleared: %s rows deleted", deleted)
        conn.execute(
            text(
                f"""
                INSERT INTO population_stats ({_COPY_COLS})
                SELECT {_COPY_COLS}
                FROM dblink(:conn_str, :remote_sql) AS remote(
                    stats_year smallint,
                    stats_month smallint,
                    admin_code varchar(10),
                    admin_level varchar(20),
                    total_population integer,
                    household_count integer,
                    pop_change_rate numeric(8,4),
                    density_per_km2 numeric(14,4),
                    source varchar(80),
                    loaded_at timestamp
                )
                """
            ),
            {"conn_str": conn_str, "remote_sql": remote_sql},
        )

    with target_engine.connect() as conn:
        n_tgt = int(conn.execute(text("SELECT COUNT(*) FROM population_stats")).scalar() or 0)
    log.info("copy complete: target rows=%s", f"{n_tgt:,}")
    if n_tgt != n_src:
        log.warning("row count mismatch source=%s target=%s", n_src, n_tgt)
    return n_tgt


def main() -> None:
    parser = argparse.ArgumentParser(description="구 DB population_stats → land_stats_next")
    parser.add_argument("--source-url", default=DEFAULT_SOURCE)
    parser.add_argument("--target-url", default=DEFAULT_TARGET)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    log.info(
        "copy_population_from_legacy: source=%s target=%s",
        args.source_url.rsplit("/", 1)[-1],
        args.target_url.rsplit("/", 1)[-1],
    )
    copy_population(args.source_url, args.target_url, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
