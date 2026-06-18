#!/usr/bin/env python3
"""
collective_transactions → market_stats (+ market_annual_stats).

설계: docs/REGIONAL_PROFILE_ARCHITECTURE.md Phase B
"""

from __future__ import annotations

import argparse
import gc
import logging
import sys
import uuid
import warnings
from datetime import date
from pathlib import Path

import pandas as pd
from sqlalchemy import text
from tqdm import tqdm

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "pipeline"))

from build_stats_v2 import (  # noqa: E402
    default_as_of_month,
    parse_as_of_month,
    period_bounds_for_window,
)
from collective.db_utils import get_collective_engine  # noqa: E402
from stats import compute_stats  # noqa: E402

warnings.filterwarnings("ignore", category=RuntimeWarning, module="scipy")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger(__name__)

ASSET_DOMAINS: dict[str, str] = {
    "apartment": "apartment_market",
    "rowhouse": "rowhouse_market",
    "officetel": "officetel_market",
    "presale": "presale_market",
}

ROLLING_SQL = """
SELECT
    btrim(COALESCE(
        NULLIF(t.eupmyeondong_code::text, ''),
        NULLIF(rc.eupmyeondong_code::text, ''),
        substring(btrim(COALESCE(t.beopjungri_code, rc.beopjungri_code)::text) from 1 for 8)
    )) AS bcode8,
    btrim(COALESCE(
        NULLIF(t.sigungu_code::text, ''),
        NULLIF(rc.sigungu_code::text, ''),
        substring(btrim(COALESCE(t.beopjungri_code, rc.beopjungri_code)::text) from 1 for 5)
    )) AS sigungu,
    btrim(COALESCE(
        NULLIF(t.sido_code::text, ''),
        NULLIF(rc.sido_code::text, ''),
        substring(btrim(COALESCE(t.beopjungri_code, rc.beopjungri_code)::text) from 1 for 2)
    )) AS sido,
    t.asset_type,
    array_agg(t.unit_price ORDER BY t.unit_price) AS prices
FROM collective_transactions t
LEFT JOIN LATERAL (
    SELECT eupmyeondong_code, sigungu_code, sido_code, beopjungri_code
    FROM region_codes rc
    WHERE COALESCE(rc.is_active, TRUE)
      AND (
            (t.beopjungri_code IS NOT NULL AND btrim(rc.beopjungri_code::text) = btrim(t.beopjungri_code::text))
         OR (
            rc.sido_name = t.addr1
            AND (t.addr2 IS NULL OR btrim(t.addr2::text) = '' OR rc.sigungu_name = t.addr2)
            AND rc.eupmyeondong_name = t.addr3
         )
      )
    LIMIT 1
) rc ON TRUE
WHERE t.is_valid = true
  AND t.unit_price IS NOT NULL
  AND t.unit_price > 0
  AND t.contract_date IS NOT NULL
  AND t.contract_date >= :p_start
  AND t.contract_date <= :p_end
  {addr1_clause}
GROUP BY 1, 2, 3, 4
"""

ANNUAL_SQL = """
SELECT
    btrim(COALESCE(
        NULLIF(t.eupmyeondong_code::text, ''),
        NULLIF(rc.eupmyeondong_code::text, ''),
        substring(btrim(COALESCE(t.beopjungri_code, rc.beopjungri_code)::text) from 1 for 8)
    )) AS bcode8,
    btrim(COALESCE(
        NULLIF(t.sigungu_code::text, ''),
        NULLIF(rc.sigungu_code::text, ''),
        substring(btrim(COALESCE(t.beopjungri_code, rc.beopjungri_code)::text) from 1 for 5)
    )) AS sigungu,
    btrim(COALESCE(
        NULLIF(t.sido_code::text, ''),
        NULLIF(rc.sido_code::text, ''),
        substring(btrim(COALESCE(t.beopjungri_code, rc.beopjungri_code)::text) from 1 for 2)
    )) AS sido,
    t.asset_type,
    t.contract_year,
    array_agg(t.unit_price ORDER BY t.unit_price) AS prices
FROM collective_transactions t
LEFT JOIN LATERAL (
    SELECT eupmyeondong_code, sigungu_code, sido_code, beopjungri_code
    FROM region_codes rc
    WHERE COALESCE(rc.is_active, TRUE)
      AND (
            (t.beopjungri_code IS NOT NULL AND btrim(rc.beopjungri_code::text) = btrim(t.beopjungri_code::text))
         OR (
            rc.sido_name = t.addr1
            AND (t.addr2 IS NULL OR btrim(t.addr2::text) = '' OR rc.sigungu_name = t.addr2)
            AND rc.eupmyeondong_name = t.addr3
         )
      )
    LIMIT 1
) rc ON TRUE
WHERE t.is_valid = true
  AND t.unit_price IS NOT NULL
  AND t.unit_price > 0
  AND t.contract_year IS NOT NULL
  {addr1_clause}
GROUP BY 1, 2, 3, 4, 5
"""


def _distinct_addr1(conn) -> list[str]:
    rows = conn.execute(
        text(
            """
            SELECT DISTINCT addr1 AS a
            FROM collective_transactions
            WHERE addr1 IS NOT NULL AND btrim(addr1::text) <> ''
            ORDER BY 1
            """
        )
    ).fetchall()
    return [str(r.a) for r in rows]


def _rollup_records(
    rows,
    *,
    as_of_month: date | None,
    window_years: int | None,
    period_start: date | None,
    period_end: date | None,
    batch_id: str,
    calendar_year: int | None = None,
) -> list[dict]:
    buckets: dict[tuple[str, str, str], list[float]] = {}
    for row in rows:
        domain = ASSET_DOMAINS.get(row["asset_type"])
        if not domain:
            continue
        prices = [float(x) for x in (row["prices"] or []) if x is not None]
        if not prices:
            continue
        level_codes = (
            ("eupmyeondong", (row.get("bcode8") or "").strip()),
            ("sigungu", (row.get("sigungu") or "").strip()),
            ("sido", (row.get("sido") or "").strip()),
        )
        for level, rc in level_codes:
            if not rc or not rc.isdigit():
                continue
            buckets.setdefault((domain, level, rc), []).extend(prices)

    out: list[dict] = []
    for (domain, level, rc), prices in buckets.items():
        st = compute_stats(prices)
        if st["count"] <= 0:
            continue
        rec = {
            "market_domain": domain,
            "region_level": level,
            "region_code": rc,
            "count": st["count"],
            "mean": st["mean"],
            "std": st["std"],
            "ci_lower": st["ci_lower"],
            "ci_upper": st["ci_upper"],
            "p25": st["p25"],
            "median": st["median"],
            "p75": st["p75"],
            "yoy": None,
            "volatility": round(float(st["std"]) / float(st["mean"]), 4)
            if st["mean"] and st["std"] is not None and float(st["mean"]) > 0
            else None,
            "batch_id": batch_id,
        }
        if calendar_year is not None:
            rec["calendar_year"] = calendar_year
        else:
            rec.update(
                {
                    "as_of_month": as_of_month,
                    "window_years": window_years,
                    "period_start": period_start,
                    "period_end": period_end,
                }
            )
        out.append(rec)
    return out


def upsert_market_stats(records: list[dict], engine, *, chunk_size: int = 400) -> None:
    if not records:
        return
    sql = text(
        """
        INSERT INTO market_stats (
            market_domain, region_level, region_code,
            as_of_month, window_years, period_start, period_end,
            count, mean, std, ci_lower, ci_upper,
            p25, median, p75, yoy, volatility,
            computed_at, batch_id
        ) VALUES (
            :market_domain, :region_level, :region_code,
            :as_of_month, :window_years, :period_start, :period_end,
            :count, :mean, :std, :ci_lower, :ci_upper,
            :p25, :median, :p75, :yoy, :volatility,
            NOW(), :batch_id
        )
        ON CONFLICT (market_domain, region_level, region_code, as_of_month, window_years)
        DO UPDATE SET
            period_start = EXCLUDED.period_start,
            period_end = EXCLUDED.period_end,
            count = EXCLUDED.count,
            mean = EXCLUDED.mean,
            std = EXCLUDED.std,
            ci_lower = EXCLUDED.ci_lower,
            ci_upper = EXCLUDED.ci_upper,
            p25 = EXCLUDED.p25,
            median = EXCLUDED.median,
            p75 = EXCLUDED.p75,
            yoy = EXCLUDED.yoy,
            volatility = EXCLUDED.volatility,
            computed_at = NOW(),
            batch_id = EXCLUDED.batch_id
        """
    )
    with engine.begin() as conn:
        for rec in records:
            conn.execute(sql, rec)


def upsert_market_annual(records: list[dict], engine) -> None:
    if not records:
        return
    sql = text(
        """
        INSERT INTO market_annual_stats (
            market_domain, region_level, region_code, calendar_year,
            count, mean, median, std, computed_at, batch_id
        ) VALUES (
            :market_domain, :region_level, :region_code, :calendar_year,
            :count, :mean, :median, :std, NOW(), :batch_id
        )
        ON CONFLICT (market_domain, region_level, region_code, calendar_year)
        DO UPDATE SET
            count = EXCLUDED.count,
            mean = EXCLUDED.mean,
            median = EXCLUDED.median,
            std = EXCLUDED.std,
            computed_at = NOW(),
            batch_id = EXCLUDED.batch_id
        """
    )
    with engine.begin() as conn:
        for rec in records:
            conn.execute(sql, rec)


def build_rolling(
    engine,
    *,
    as_of_month: date,
    windows: list[int],
    addr1_filter: str | None,
    batch_id: str,
) -> int:
    total = 0
    with engine.connect() as conn:
        addr1_list = [addr1_filter] if addr1_filter else _distinct_addr1(conn)

    for wy in windows:
        ps, pe = period_bounds_for_window(as_of_month, wy)
        log.info("market window=%sy period=%s..%s", wy, ps, pe)
        for addr1 in tqdm(addr1_list, desc=f"mkt-w{wy}"):
            addr1_clause = "AND t.addr1 = :addr1" if addr1 else ""
            params = {"p_start": ps, "p_end": pe}
            if addr1:
                params["addr1"] = addr1
            with engine.connect() as conn:
                rows = conn.execute(
                    text(ROLLING_SQL.format(addr1_clause=addr1_clause)),
                    params,
                ).mappings().all()
            records = _rollup_records(
                rows,
                as_of_month=as_of_month,
                window_years=wy,
                period_start=ps,
                period_end=pe,
                batch_id=batch_id,
            )
            upsert_market_stats(records, engine)
            total += len(records)
            del rows, records
            gc.collect()
    return total


def build_annual(engine, *, addr1_filter: str | None, batch_id: str) -> int:
    total = 0
    with engine.connect() as conn:
        addr1_list = [addr1_filter] if addr1_filter else _distinct_addr1(conn)

    for addr1 in tqdm(addr1_list, desc="mkt-annual"):
        addr1_clause = "AND t.addr1 = :addr1" if addr1 else ""
        params = {}
        if addr1:
            params["addr1"] = addr1
        with engine.connect() as conn:
            rows = conn.execute(
                text(ANNUAL_SQL.format(addr1_clause=addr1_clause)),
                params,
            ).mappings().all()

        by_year: dict[int, list] = {}
        for row in rows:
            cy = int(row["contract_year"])
            by_year.setdefault(cy, []).append(row)

        for cy, year_rows in by_year.items():
            records = _rollup_records(
                year_rows,
                as_of_month=None,
                window_years=None,
                period_start=None,
                period_end=None,
                batch_id=batch_id,
                calendar_year=cy,
            )
            upsert_market_annual(records, engine)
            total += len(records)
        del rows, by_year
        gc.collect()
    return total


def main() -> None:
    p = argparse.ArgumentParser(description="집합 market_stats / market_annual_stats")
    p.add_argument("--as-of", type=str, default=None)
    p.add_argument("--windows", type=str, default="3,5")
    p.add_argument("--addr1", type=str, default=None, help="시도 한정 스모크")
    p.add_argument("--skip-annual", action="store_true")
    p.add_argument("--rolling-only", action="store_true")
    args = p.parse_args()

    as_of = parse_as_of_month(args.as_of) if args.as_of else default_as_of_month()
    windows = sorted({int(x.strip()) for x in args.windows.split(",") if x.strip()})

    engine = get_collective_engine()
    batch_id = str(uuid.uuid4())

    with engine.connect() as conn:
        tx_n = conn.execute(text("SELECT COUNT(*) FROM collective_transactions")).scalar()
    log.info("collective_transactions rows=%s as_of=%s", tx_n, as_of)
    if not tx_n:
        raise SystemExit("collective_transactions empty")

    rolling_n = build_rolling(
        engine,
        as_of_month=as_of,
        windows=windows,
        addr1_filter=args.addr1,
        batch_id=batch_id,
    )
    log.info("market_stats upserted ~%s rows", rolling_n)

    if not args.skip_annual and not args.rolling_only:
        annual_n = build_annual(engine, addr1_filter=args.addr1, batch_id=batch_id)
        log.info("market_annual_stats upserted ~%s rows", annual_n)

    with engine.connect() as conn:
        ms = conn.execute(text("SELECT COUNT(*) FROM market_stats")).scalar()
        ma = conn.execute(text("SELECT COUNT(*) FROM market_annual_stats")).scalar()
    log.info("totals: market_stats=%s market_annual=%s", ms, ma)


if __name__ == "__main__":
    main()
