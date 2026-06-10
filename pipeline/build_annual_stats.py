"""
장기 추세용 연도별 사전 집계: land_transactions → land_annual_stats

설계: docs/LONG_TERM_TREND_DESIGN.md · db/014_land_annual_stats.sql

예)
  python build_annual_stats.py --years 2010-2020 --sido-code 43
  python build_annual_stats.py --years 2021-2025 --full
"""

from __future__ import annotations

import argparse
import logging
import math
import sys
import uuid
import warnings
from datetime import date
from pathlib import Path

import scipy.stats as st
from sqlalchemy import text

from db_utils import get_engine
from stats import PRICE_STAT_DECIMALS

warnings.filterwarnings("ignore", category=RuntimeWarning, module="scipy")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger(__name__)

_AGG_SQL = """
WITH filtered AS (
    SELECT
        EXTRACT(YEAR FROM lt.contract_date)::int AS calendar_year,
        btrim(lt.beopjungri_code::text) AS beopjungri_code,
        btrim(lt.zone_type::text) AS zone_type,
        btrim(lt.land_category::text) AS land_category,
        lt.unit_price_per_sqm::float8 AS price
    FROM land_transactions lt
    WHERE lt.is_valid = TRUE
      AND lt.is_cancelled = FALSE
      AND lt.unit_price_per_sqm IS NOT NULL
      AND lt.contract_date IS NOT NULL
      AND EXTRACT(YEAR FROM lt.contract_date)::int >= :y0
      AND EXTRACT(YEAR FROM lt.contract_date)::int <= :y1
      {sido_sql}
      AND btrim(lt.zone_type::text) <> ''
      AND btrim(lt.land_category::text) <> ''
)
SELECT
    calendar_year,
    beopjungri_code,
    COALESCE(zone_type, 'ALL') AS zone_type,
    COALESCE(land_category, 'ALL') AS land_category,
    COUNT(*)::int AS transaction_count,
    ROUND(AVG(price)::numeric, 1) AS mean_unit_price,
    ROUND((PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY price))::numeric, 1)
        AS median_unit_price,
    ROUND(STDDEV_SAMP(price)::numeric, 1) AS std_dev,
    ROUND(MIN(price)::numeric, 1) AS min_price,
    ROUND(MAX(price)::numeric, 1) AS max_price,
    ROUND((PERCENTILE_CONT(0.1) WITHIN GROUP (ORDER BY price))::numeric, 1) AS p10,
    ROUND((PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY price))::numeric, 1) AS p25,
    ROUND((PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY price))::numeric, 1) AS p75,
    ROUND((PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY price))::numeric, 1) AS p90
FROM filtered
GROUP BY calendar_year, beopjungri_code, GROUPING SETS (
    (zone_type, land_category),
    (zone_type),
    (land_category),
    ()
)
"""


def parse_year_range(s: str) -> tuple[int, int]:
    s = s.strip()
    if "-" in s:
        a, b = s.split("-", 1)
        return int(a.strip()), int(b.strip())
    y = int(s)
    return y, y


def calendar_year_bounds(y: int) -> tuple[date, date]:
    return date(y, 1, 1), date(y, 12, 31)


def _ci95(count: int, mean: float | None, std: float | None) -> tuple[float | None, float | None]:
    if count < 2 or mean is None or std is None or std <= 0:
        return None, None
    se = std / math.sqrt(count)
    if se <= 0 or not math.isfinite(se):
        return None, None
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        ci = st.t.interval(0.95, df=count - 1, loc=mean, scale=se)
    return round(float(ci[0]), PRICE_STAT_DECIMALS), round(float(ci[1]), PRICE_STAT_DECIMALS)


def _row_to_record(row: dict, *, batch_id: str) -> dict:
    cy = int(row["calendar_year"])
    ps, pe = calendar_year_bounds(cy)
    count = int(row["transaction_count"] or 0)
    mean = float(row["mean_unit_price"]) if row["mean_unit_price"] is not None else None
    std = float(row["std_dev"]) if row["std_dev"] is not None else None
    ci_low, ci_high = _ci95(count, mean, std)
    return {
        "calendar_year": cy,
        "beopjungri_code": str(row["beopjungri_code"]).strip(),
        "zone_type": str(row["zone_type"]).strip(),
        "land_category": str(row["land_category"]).strip(),
        "transaction_count": count,
        "mean_unit_price": mean,
        "median_unit_price": float(row["median_unit_price"])
        if row["median_unit_price"] is not None
        else None,
        "std_dev": std,
        "ci95_low": ci_low,
        "ci95_high": ci_high,
        "p10": float(row["p10"]) if row["p10"] is not None else None,
        "p25": float(row["p25"]) if row["p25"] is not None else None,
        "p75": float(row["p75"]) if row["p75"] is not None else None,
        "p90": float(row["p90"]) if row["p90"] is not None else None,
        "min_price": float(row["min_price"]) if row["min_price"] is not None else None,
        "max_price": float(row["max_price"]) if row["max_price"] is not None else None,
        "period_start": ps,
        "period_end": pe,
        "batch_id": batch_id,
    }


def list_sido_codes() -> list[str]:
    engine = get_engine()
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT DISTINCT LEFT(beopjungri_code, 2) AS sc "
                "FROM land_transactions "
                "WHERE beopjungri_code IS NOT NULL AND btrim(beopjungri_code) <> '' "
                "ORDER BY sc"
            )
        ).fetchall()
    return [str(r[0]).zfill(2) for r in rows if r[0]]


def upsert_annual_stats(records: list[dict], *, chunk_size: int = 400) -> int:
    if not records:
        return 0
    engine = get_engine()
    sql = text(
        """
        INSERT INTO land_annual_stats (
            calendar_year, beopjungri_code, zone_type, land_category,
            transaction_count, mean_unit_price, median_unit_price,
            std_dev, ci95_low, ci95_high,
            p10, p25, p75, p90, min_price, max_price,
            period_start, period_end, batch_id, computed_at
        ) VALUES (
            :calendar_year, :beopjungri_code, :zone_type, :land_category,
            :transaction_count, :mean_unit_price, :median_unit_price,
            :std_dev, :ci95_low, :ci95_high,
            :p10, :p25, :p75, :p90, :min_price, :max_price,
            :period_start, :period_end, :batch_id, NOW()
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
            computed_at = NOW()
        """
    )
    n = 0
    with engine.begin() as conn:
        for i in range(0, len(records), chunk_size):
            chunk = records[i : i + chunk_size]
            conn.execute(sql, chunk)
            n += len(chunk)
    return n


def build_for_sido(
    *,
    year_from: int,
    year_to: int,
    sido_code: str,
    batch_id: str,
) -> int:
    params: dict = {"y0": year_from, "y1": year_to, "sido": str(sido_code).zfill(2)[:2]}
    sql = text(_AGG_SQL.format(sido_sql="AND lt.sido_code = :sido"))

    log.info("시도 %s: SQL 집계 중 (years=%d~%d)", sido_code, year_from, year_to)
    engine = get_engine()
    with engine.connect() as conn:
        rows = conn.execute(sql, params).mappings().all()

    if not rows:
        log.warning("시도 %s: 거래 없음", sido_code)
        return 0

    records = [_row_to_record(dict(r), batch_id=batch_id) for r in rows if int(r["transaction_count"] or 0) > 0]
    log.info("시도 %s: 집계 레코드 %d개 UPSERT 중", sido_code, len(records))
    n = upsert_annual_stats(records)
    log.info("시도 %s: land_annual_stats %d행 UPSERT", sido_code, n)
    return n


def ensure_table() -> None:
    ddl_path = Path(__file__).resolve().parents[1] / "db" / "014_land_annual_stats.sql"
    if not ddl_path.is_file():
        return
    engine = get_engine()
    sql_text = ddl_path.read_text(encoding="utf-8")
    with engine.begin() as conn:
        conn.execute(text(sql_text))


def main() -> None:
    parser = argparse.ArgumentParser(description="land_annual_stats 연도별 사전 집계")
    parser.add_argument("--years", default="2010-2020", help="연도 범위 (예: 2010-2020)")
    parser.add_argument("--sido-code", action="append", default=[], help="시도 2자리 (반복 가능)")
    parser.add_argument(
        "--full",
        action="store_true",
        help="DB에 있는 모든 시도 코드에 대해 실행",
    )
    parser.add_argument(
        "--with-upper",
        action="store_true",
        help="land_annual_upper_stats 도 함께 빌드",
    )
    args = parser.parse_args()

    year_from, year_to = parse_year_range(args.years)
    batch_id = f"annual_{year_from}_{year_to}_{uuid.uuid4().hex[:8]}"

    ensure_table()

    sidos: list[str]
    if args.full:
        sidos = list_sido_codes()
    elif args.sido_code:
        sidos = [str(s).zfill(2)[:2] for s in args.sido_code]
    else:
        sidos = list_sido_codes()

    log.info(
        "build_annual_stats: years=%d~%d sidos=%d batch_id=%s",
        year_from,
        year_to,
        len(sidos),
        batch_id,
    )

    total = 0
    for sc in sidos:
        total += build_for_sido(
            year_from=year_from,
            year_to=year_to,
            sido_code=sc,
            batch_id=batch_id,
        )
    log.info("완료: 총 UPSERT %d행", total)

    if args.with_upper:
        import subprocess

        upper_cmd = [
            sys.executable,
            str(Path(__file__).resolve().parent / "build_annual_upper_stats.py"),
            "--years",
            args.years,
        ]
        if args.full:
            upper_cmd.append("--full")
        else:
            for sc in sidos:
                upper_cmd.extend(["--sido-code", sc])
        log.info("상위 행정 연도 마트 빌드 시작")
        subprocess.run(upper_cmd, check=True)


if __name__ == "__main__":
    main()
