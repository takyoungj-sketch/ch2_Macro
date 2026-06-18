"""
구 DB(land_stats) → 신 DB(land_stats_next) 장기추세 annual 마트 복사.

Phase 2b — 2010~2020 구간은 구 annual 재사용, 2021~ 는 build_annual_stats.py 로 재빌드.

예)
  python copy_annual_from_legacy.py --year-to 2020
  python copy_annual_from_legacy.py --dry-run
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

_LAS_COLS = """
    calendar_year, beopjungri_code, zone_type, land_category,
    transaction_count, mean_unit_price, median_unit_price,
    std_dev, ci95_low, ci95_high,
    p10, p25, p75, p90, min_price, max_price,
    period_start, period_end, batch_id, computed_at
""".strip()

_LAS_UPSERT = f"""
INSERT INTO land_annual_stats ({_LAS_COLS})
SELECT {_LAS_COLS}
FROM dblink(
    :conn_str,
    :remote_sql
) AS remote(
    calendar_year smallint,
    beopjungri_code char(10),
    zone_type varchar(20),
    land_category varchar(10),
    transaction_count integer,
    mean_unit_price numeric(14,2),
    median_unit_price numeric(14,2),
    std_dev numeric(14,2),
    ci95_low numeric(14,2),
    ci95_high numeric(14,2),
    p10 numeric(14,2),
    p25 numeric(14,2),
    p75 numeric(14,2),
    p90 numeric(14,2),
    min_price numeric(14,2),
    max_price numeric(14,2),
    period_start date,
    period_end date,
    batch_id text,
    computed_at timestamp
)
ON CONFLICT (calendar_year, beopjungri_code, zone_type, land_category)
DO UPDATE SET
    transaction_count = EXCLUDED.transaction_count,
    mean_unit_price = EXCLUDED.mean_unit_price,
    median_unit_price = EXCLUDED.median_unit_price,
    std_dev = EXCLUDED.std_dev,
    ci95_low = EXCLUDED.ci95_low,
    ci95_high = EXCLUDED.ci95_high,
    p10 = EXCLUDED.p10,
    p25 = EXCLUDED.p25,
    p75 = EXCLUDED.p75,
    p90 = EXCLUDED.p90,
    min_price = EXCLUDED.min_price,
    max_price = EXCLUDED.max_price,
    period_start = EXCLUDED.period_start,
    period_end = EXCLUDED.period_end,
    batch_id = EXCLUDED.batch_id,
    computed_at = EXCLUDED.computed_at
"""

_LAU_COLS = """
    calendar_year, region_level, region_code, zone_type, land_category,
    transaction_count, mean_unit_price, median_unit_price,
    std_dev, ci95_low, ci95_high,
    p10, p25, p75, p90, min_price, max_price,
    period_start, period_end, batch_id, computed_at
""".strip()

_LAU_UPSERT = f"""
INSERT INTO land_annual_upper_stats ({_LAU_COLS})
SELECT {_LAU_COLS}
FROM dblink(
    :conn_str,
    :remote_sql
) AS remote(
    calendar_year smallint,
    region_level varchar(20),
    region_code varchar(10),
    zone_type varchar(20),
    land_category varchar(10),
    transaction_count integer,
    mean_unit_price numeric(14,2),
    median_unit_price numeric(14,2),
    std_dev numeric(14,2),
    ci95_low numeric(14,2),
    ci95_high numeric(14,2),
    p10 numeric(14,2),
    p25 numeric(14,2),
    p75 numeric(14,2),
    p90 numeric(14,2),
    min_price numeric(14,2),
    max_price numeric(14,2),
    period_start date,
    period_end date,
    batch_id text,
    computed_at timestamp
)
ON CONFLICT (calendar_year, region_level, region_code, zone_type, land_category)
DO UPDATE SET
    transaction_count = EXCLUDED.transaction_count,
    mean_unit_price = EXCLUDED.mean_unit_price,
    median_unit_price = EXCLUDED.median_unit_price,
    std_dev = EXCLUDED.std_dev,
    ci95_low = EXCLUDED.ci95_low,
    ci95_high = EXCLUDED.ci95_high,
    p10 = EXCLUDED.p10,
    p25 = EXCLUDED.p25,
    p75 = EXCLUDED.p75,
    p90 = EXCLUDED.p90,
    min_price = EXCLUDED.min_price,
    max_price = EXCLUDED.max_price,
    period_start = EXCLUDED.period_start,
    period_end = EXCLUDED.period_end,
    batch_id = EXCLUDED.batch_id,
    computed_at = EXCLUDED.computed_at
"""


def _pg_conn_str(sqlalchemy_url: str) -> str:
    """dblink connection string (libpq format)."""
    from sqlalchemy.engine.url import make_url

    u = make_url(sqlalchemy_url.replace("+psycopg2", ""))
    host = u.host or "localhost"
    port = u.port or 5432
    user = u.username or "postgres"
    password = u.password or ""
    db = u.database or "land_stats"
    return f"host={host} port={port} dbname={db} user={user} password={password}"


def _count_source(engine, table: str, year_to: int) -> int:
    with engine.connect() as conn:
        return int(
            conn.execute(
                text(
                    f"SELECT COUNT(*) FROM {table} WHERE calendar_year <= :yto"
                ),
                {"yto": year_to},
            ).scalar()
            or 0
        )


def _copy_year_dblink(
    target_engine,
    *,
    table: str,
    upsert_sql: str,
    conn_str: str,
    year: int,
    dry_run: bool,
) -> int:
    remote_sql = (
        f"SELECT {_LAS_COLS if table == 'land_annual_stats' else _LAU_COLS} "
        f"FROM {table} WHERE calendar_year = {year}"
    )
    if dry_run:
        log.info("[dry-run] %s calendar_year=%d", table, year)
        return 0
    with target_engine.begin() as conn:
        conn.execute(
            text(upsert_sql),
            {"conn_str": conn_str, "remote_sql": remote_sql},
        )
    with target_engine.connect() as conn:
        n = conn.execute(
            text(f"SELECT COUNT(*) FROM {table} WHERE calendar_year = :y"),
            {"y": year},
        ).scalar()
    log.info("%s calendar_year=%d → target rows=%s", table, year, n)
    return int(n or 0)


def _copy_python_fallback(
    source_engine,
    target_engine,
    *,
    table: str,
    year_to: int,
    dry_run: bool,
) -> int:
    """dblink 불가 시 연도별 Python 배치 복사."""
    cols = _LAS_COLS if table == "land_annual_stats" else _LAU_COLS
    col_list = [c.strip() for c in cols.split(",")]
    placeholders = ", ".join(f":{c}" for c in col_list)
    if table == "land_annual_stats":
        conflict = """
        ON CONFLICT (calendar_year, beopjungri_code, zone_type, land_category)
        DO UPDATE SET transaction_count = EXCLUDED.transaction_count,
            mean_unit_price = EXCLUDED.mean_unit_price,
            median_unit_price = EXCLUDED.median_unit_price,
            std_dev = EXCLUDED.std_dev, ci95_low = EXCLUDED.ci95_low,
            ci95_high = EXCLUDED.ci95_high, p10 = EXCLUDED.p10, p25 = EXCLUDED.p25,
            p75 = EXCLUDED.p75, p90 = EXCLUDED.p90, min_price = EXCLUDED.min_price,
            max_price = EXCLUDED.max_price, period_start = EXCLUDED.period_start,
            period_end = EXCLUDED.period_end, batch_id = EXCLUDED.batch_id,
            computed_at = EXCLUDED.computed_at
        """
        order_by = "beopjungri_code, zone_type, land_category"
    else:
        conflict = """
        ON CONFLICT (calendar_year, region_level, region_code, zone_type, land_category)
        DO UPDATE SET transaction_count = EXCLUDED.transaction_count,
            mean_unit_price = EXCLUDED.mean_unit_price,
            median_unit_price = EXCLUDED.median_unit_price,
            std_dev = EXCLUDED.std_dev, ci95_low = EXCLUDED.ci95_low,
            ci95_high = EXCLUDED.ci95_high, p10 = EXCLUDED.p10, p25 = EXCLUDED.p25,
            p75 = EXCLUDED.p75, p90 = EXCLUDED.p90, min_price = EXCLUDED.min_price,
            max_price = EXCLUDED.max_price, period_start = EXCLUDED.period_start,
            period_end = EXCLUDED.period_end, batch_id = EXCLUDED.batch_id,
            computed_at = EXCLUDED.computed_at
        """
        order_by = "region_level, region_code, zone_type, land_category"
    insert_sql = text(
        f"INSERT INTO {table} ({cols}) VALUES ({placeholders}) {conflict}"
    )

    total = 0
    with source_engine.connect() as src:
        years = [
            int(r[0])
            for r in src.execute(
                text(
                    f"SELECT DISTINCT calendar_year FROM {table} "
                    f"WHERE calendar_year <= :yto ORDER BY 1"
                ),
                {"yto": year_to},
            ).fetchall()
        ]
        for year in years:
            log.info("%s calendar_year=%d Python 배치 복사…", table, year)
            if dry_run:
                continue
            offset = 0
            chunk = 5000
            while True:
                rows = (
                    src.execute(
                        text(
                            f"SELECT {cols} FROM {table} "
                            f"WHERE calendar_year = :y ORDER BY {order_by} "
                            f"LIMIT :lim OFFSET :off"
                        ),
                        {"y": year, "lim": chunk, "off": offset},
                    )
                    .mappings()
                    .all()
                )
                if not rows:
                    break
                records = [dict(r) for r in rows]
                with target_engine.begin() as tgt:
                    tgt.execute(insert_sql, records)
                total += len(records)
                offset += chunk
                if len(records) < chunk:
                    break
            log.info("%s calendar_year=%d 완료 (누적 %d행)", table, year, total)
    return total


def copy_table(
    source_url: str,
    target_url: str,
    *,
    table: str,
    year_to: int,
    dry_run: bool,
) -> int:
    source_engine = create_engine(source_url, pool_pre_ping=True)
    target_engine = create_engine(target_url, pool_pre_ping=True)
    n_src = _count_source(source_engine, table, year_to)
    log.info("%s source rows (≤%d): %s", table, year_to, f"{n_src:,}")

    if dry_run:
        return n_src

    conn_str = _pg_conn_str(source_url)
    try:
        with target_engine.begin() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS dblink"))
        with source_engine.connect() as conn:
            years = [
                int(r[0])
                for r in conn.execute(
                    text(
                        f"SELECT DISTINCT calendar_year FROM {table} "
                        f"WHERE calendar_year <= :yto ORDER BY 1"
                    ),
                    {"yto": year_to},
                ).fetchall()
            ]
        upsert = _LAS_UPSERT if table == "land_annual_stats" else _LAU_UPSERT
        for year in years:
            _copy_year_dblink(
                target_engine,
                table=table,
                upsert_sql=upsert,
                conn_str=conn_str,
                year=year,
                dry_run=False,
            )
        log.info("%s dblink 복사 완료", table)
        return n_src
    except Exception as exc:
        log.warning("dblink 복사 실패 (%s) — Python fallback", exc)
        return _copy_python_fallback(
            source_engine, target_engine, table=table, year_to=year_to, dry_run=dry_run
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="구 DB annual 마트 → land_stats_next 복사")
    parser.add_argument("--source-url", default=DEFAULT_SOURCE)
    parser.add_argument("--target-url", default=DEFAULT_TARGET)
    parser.add_argument("--year-to", type=int, default=2020, help="복사할 최대 calendar_year")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--tables",
        default="land_annual_stats,land_annual_upper_stats",
        help="쉼표 구분 테이블",
    )
    args = parser.parse_args()

    tables = [t.strip() for t in args.tables.split(",") if t.strip()]
    log.info(
        "copy_annual_from_legacy: year_to=%d source=%s target=%s",
        args.year_to,
        args.source_url.rsplit("/", 1)[-1],
        args.target_url.rsplit("/", 1)[-1],
    )
    for table in tables:
        copy_table(
            args.source_url,
            args.target_url,
            table=table,
            year_to=args.year_to,
            dry_run=args.dry_run,
        )


if __name__ == "__main__":
    main()
