"""
장기 추세용 상위 행정구역 연도별 사전 집계: land_transactions → land_annual_upper_stats

레벨: sido · sigungu · eupmyeondong · city (land_upper_stats_v2 와 동일)

예)
  python build_annual_upper_stats.py --years 2010-2026 --sido-code 43
  python build_annual_upper_stats.py --years 2010-2026 --full
"""

from __future__ import annotations

import argparse
import logging
import sys
import uuid
from pathlib import Path

from build_annual_stats import (
    _ci95,
    calendar_year_bounds,
    list_sido_codes,
    parse_year_range,
)
from sqlalchemy import text

from db_utils import get_engine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger(__name__)

_BASE_FILTER = """
    lt.is_valid = TRUE
    AND lt.is_cancelled = FALSE
    AND lt.unit_price_per_sqm IS NOT NULL
    AND lt.contract_date IS NOT NULL
    AND EXTRACT(YEAR FROM lt.contract_date)::int >= :y0
    AND EXTRACT(YEAR FROM lt.contract_date)::int <= :y1
    {sido_sql}
    AND btrim(lt.zone_type::text) <> ''
    AND btrim(lt.land_category::text) <> ''
    AND btrim(COALESCE(lt.beopjungri_code::text, '')) <> ''
"""

_AGG_FOR_LEVEL = """
WITH joined AS (
    SELECT
        EXTRACT(YEAR FROM lt.contract_date)::int AS calendar_year,
        btrim(lt.sido_code::text) AS sido_code,
        btrim(lt.sigungu_code::text) AS sigungu_code,
        btrim(r.eupmyeondong_code::text) AS eupmyeondong_code,
        LPAD(
            (FLOOR(btrim(lt.sigungu_code::text)::numeric / 10) * 10)::int::text,
            5,
            '0'
        ) AS city_code,
        btrim(lt.zone_type::text) AS zone_type,
        btrim(lt.land_category::text) AS land_category,
        lt.unit_price_per_sqm::float8 AS price
    FROM land_transactions lt
    INNER JOIN region_codes r
        ON btrim(r.beopjungri_code::text) = btrim(lt.beopjungri_code::text)
       AND COALESCE(r.is_active, TRUE)
    WHERE {base_filter}
),
filtered AS (
    SELECT
        calendar_year,
        {region_expr} AS region_code,
        zone_type,
        land_category,
        price
    FROM joined
    WHERE btrim({region_expr}) <> ''
)
SELECT
    calendar_year,
    :region_level AS region_level,
    region_code,
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
GROUP BY calendar_year, region_code, GROUPING SETS (
    (zone_type, land_category),
    (zone_type),
    (land_category),
    ()
)
"""

_LEVEL_EXPR: dict[str, str] = {
    "sido": "sido_code",
    "sigungu": "sigungu_code",
    "eupmyeondong": "eupmyeondong_code",
    "city": "city_code",
}


def _row_to_upper_record(row: dict, *, batch_id: str) -> dict:
    cy = int(row["calendar_year"])
    ps, pe = calendar_year_bounds(cy)
    count = int(row["transaction_count"] or 0)
    mean = float(row["mean_unit_price"]) if row["mean_unit_price"] is not None else None
    std = float(row["std_dev"]) if row["std_dev"] is not None else None
    ci_low, ci_high = _ci95(count, mean, std)
    return {
        "calendar_year": cy,
        "region_level": str(row["region_level"]).strip(),
        "region_code": str(row["region_code"]).strip(),
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


def upsert_upper_annual_stats(records: list[dict], *, chunk_size: int = 400) -> int:
    if not records:
        return 0
    engine = get_engine()
    sql = text(
        """
        INSERT INTO land_annual_upper_stats (
            calendar_year, region_level, region_code, zone_type, land_category,
            transaction_count, mean_unit_price, median_unit_price,
            std_dev, ci95_low, ci95_high,
            p10, p25, p75, p90, min_price, max_price,
            period_start, period_end, batch_id, computed_at
        ) VALUES (
            :calendar_year, :region_level, :region_code, :zone_type, :land_category,
            :transaction_count, :mean_unit_price, :median_unit_price,
            :std_dev, :ci95_low, :ci95_high,
            :p10, :p25, :p75, :p90, :min_price, :max_price,
            :period_start, :period_end, :batch_id, NOW()
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


def build_level_for_sido(
    *,
    level: str,
    year_from: int,
    year_to: int,
    sido_code: str,
    batch_id: str,
) -> int:
    region_expr = _LEVEL_EXPR[level]
    base_filter = _BASE_FILTER.format(sido_sql="AND lt.sido_code = :sido")
    sql = text(
        _AGG_FOR_LEVEL.format(base_filter=base_filter, region_expr=region_expr)
    )
    params = {
        "y0": year_from,
        "y1": year_to,
        "sido": str(sido_code).zfill(2)[:2],
        "region_level": level,
    }
    log.info("시도 %s level=%s: SQL 집계 (years=%d~%d)", sido_code, level, year_from, year_to)
    engine = get_engine()
    with engine.connect() as conn:
        rows = conn.execute(sql, params).mappings().all()
    if not rows:
        log.warning("시도 %s level=%s: 거래 없음", sido_code, level)
        return 0
    records = [
        _row_to_upper_record(dict(r), batch_id=batch_id)
        for r in rows
        if int(r["transaction_count"] or 0) > 0
    ]
    log.info("시도 %s level=%s: %d 레코드 UPSERT", sido_code, level, len(records))
    return upsert_upper_annual_stats(records)


def build_for_sido(
    *,
    year_from: int,
    year_to: int,
    sido_code: str,
    batch_id: str,
    levels: list[str],
) -> int:
    total = 0
    for level in levels:
        total += build_level_for_sido(
            level=level,
            year_from=year_from,
            year_to=year_to,
            sido_code=sido_code,
            batch_id=batch_id,
        )
    return total


def ensure_table() -> None:
    ddl_path = Path(__file__).resolve().parents[1] / "db" / "021_land_annual_upper_stats.sql"
    if not ddl_path.is_file():
        return
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text(ddl_path.read_text(encoding="utf-8")))


def main() -> None:
    parser = argparse.ArgumentParser(description="land_annual_upper_stats 연도별 상위 집계")
    parser.add_argument("--years", default="2010-2026", help="연도 범위 (예: 2010-2026)")
    parser.add_argument("--sido-code", action="append", default=[], help="시도 2자리 (반복 가능)")
    parser.add_argument("--full", action="store_true", help="DB의 모든 시도")
    parser.add_argument(
        "--levels",
        default="sido,sigungu,eupmyeondong,city",
        help="집계 레벨 (쉼표 구분)",
    )
    args = parser.parse_args()

    year_from, year_to = parse_year_range(args.years)
    levels = [x.strip() for x in args.levels.split(",") if x.strip()]
    for lv in levels:
        if lv not in _LEVEL_EXPR:
            raise SystemExit(f"unknown level: {lv}")

    batch_id = f"annual_upper_{year_from}_{year_to}_{uuid.uuid4().hex[:8]}"
    ensure_table()

    if args.full:
        sidos = list_sido_codes()
    elif args.sido_code:
        sidos = [str(s).zfill(2)[:2] for s in args.sido_code]
    else:
        sidos = list_sido_codes()

    log.info(
        "build_annual_upper_stats: years=%d~%d sidos=%d levels=%s batch_id=%s",
        year_from,
        year_to,
        len(sidos),
        levels,
        batch_id,
    )

    total = 0
    for sc in sidos:
        total += build_for_sido(
            year_from=year_from,
            year_to=year_to,
            sido_code=sc,
            batch_id=batch_id,
            levels=levels,
        )
    log.info("완료: 총 UPSERT %d행", total)


if __name__ == "__main__":
    main()
