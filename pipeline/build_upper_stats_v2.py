"""
V2 상위 행정구역 사전 집계: land_transactions → land_upper_stats_v2

집계 레벨: sido(2) · sigungu(5) · eupmyeondong(8)
원장에서 직접 집계 (하위 land_basic_stats_v2 합산 금지).

사용:
  python build_upper_stats_v2.py --as-of 2025-12-01 --windows 3,5
  python build_upper_stats_v2.py --sido-code 43
"""

from __future__ import annotations

import argparse
import gc
import logging
import os
import sys
import time
import uuid
from datetime import date, datetime, timedelta

import pandas as pd
from sqlalchemy import text
from tqdm import tqdm

from build_stats_v2 import (
    DEFAULT_UPSERT_CHUNK,
    _df_mem_mb,
    default_as_of_month,
    distinct_sido_codes_in_period,
    parse_as_of_month,
    parse_sido_code,
    period_bounds_for_window,
)
from constants import STATS_V2_WINDOW_YEARS_ALL
from db_utils import get_engine
from stats import compute_stats

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger(__name__)

LEVEL_COLUMNS: dict[str, str] = {
    "sido": "sido_code",
    "sigungu": "sigungu_code",
    "eupmyeondong": "eupmyeondong_code",
}


def fetch_transactions_for_upper_union(
    period_start_min: date,
    period_end: date,
    *,
    sido_code: str | None = None,
) -> pd.DataFrame:
    """region_codes 조인으로 eupmyeondong_code 확보."""
    engine = get_engine()
    where_sido = ""
    params: dict = {"p_start": period_start_min, "p_end": period_end}
    if sido_code:
        where_sido = "AND btrim(lt.sido_code::text) = :sido"
        params["sido"] = sido_code

    query = f"""
        SELECT
            btrim(lt.sido_code::text) AS sido_code,
            btrim(lt.sigungu_code::text) AS sigungu_code,
            btrim(r.eupmyeondong_code::text) AS eupmyeondong_code,
            lt.zone_type,
            lt.land_category,
            lt.unit_price_per_sqm,
            lt.contract_date::date AS contract_date
        FROM land_transactions lt
        INNER JOIN region_codes r
            ON btrim(r.beopjungri_code::text) = btrim(lt.beopjungri_code::text)
           AND COALESCE(r.is_active, TRUE)
        WHERE lt.is_valid = TRUE
          AND lt.is_cancelled = FALSE
          AND lt.unit_price_per_sqm IS NOT NULL
          AND lt.contract_date IS NOT NULL
          AND btrim(COALESCE(lt.beopjungri_code::text, '')) <> ''
          AND lt.contract_date >= :p_start
          AND lt.contract_date <= :p_end
          {where_sido}
    """
    with engine.connect() as conn:
        rows = conn.execute(text(query), params).fetchall()

    return pd.DataFrame(
        rows,
        columns=[
            "sido_code",
            "sigungu_code",
            "eupmyeondong_code",
            "zone_type",
            "land_category",
            "unit_price_per_sqm",
            "contract_date",
        ],
    )


def build_stats_for_upper_region(
    df: pd.DataFrame,
    region_level: str,
    region_code: str,
    *,
    as_of_month: date,
    window_years: int,
    period_start: date,
    period_end: date,
    batch_id: str | None,
) -> list[dict]:
    col = LEVEL_COLUMNS[region_level]
    rc = str(region_code).strip()
    sub = df[df[col].astype(str).str.strip() == rc]
    if sub.empty:
        return []

    from itertools import product

    zone_types = ["ALL"] + sorted(sub["zone_type"].dropna().astype(str).str.strip().unique().tolist())
    land_cats = ["ALL"] + sorted(sub["land_category"].dropna().astype(str).str.strip().unique().tolist())

    records: list[dict] = []
    for zone, cat in product(zone_types, land_cats):
        mask = pd.Series([True] * len(sub), index=sub.index)
        if zone != "ALL":
            mask &= sub["zone_type"].astype(str).str.strip() == zone
        if cat != "ALL":
            mask &= sub["land_category"].astype(str).str.strip() == cat

        prices = sub.loc[mask, "unit_price_per_sqm"].dropna().tolist()
        stats = compute_stats(prices)
        records.append(
            {
                "region_level": region_level,
                "region_code": rc,
                "as_of_month": as_of_month,
                "window_years": window_years,
                "period_start": period_start,
                "period_end": period_end,
                "zone_type": zone,
                "land_category": cat,
                "count": stats["count"],
                "mean": stats["mean"],
                "std": stats["std"],
                "ci_lower": stats["ci_lower"],
                "ci_upper": stats["ci_upper"],
                "p_min": stats["min"],
                "p25": stats["p25"],
                "median": stats["median"],
                "p75": stats["p75"],
                "p_max": stats["max"],
                "batch_id": batch_id,
            }
        )
    return records


def collect_upper_records_for_windows(
    df_full: pd.DataFrame,
    *,
    as_of_month: date,
    windows: list[int],
    batch_id: str,
    levels: list[str] | None = None,
) -> list[dict]:
    levels = levels or list(LEVEL_COLUMNS.keys())
    df = df_full.copy()
    if df.empty:
        return []

    df["contract_date"] = pd.to_datetime(df["contract_date"]).dt.date
    total: list[dict] = []
    for w in windows:
        ps, pe = period_bounds_for_window(as_of_month, w)
        df_w = df[(df["contract_date"] >= ps) & (df["contract_date"] <= pe)]
        if df_w.empty:
            log.warning("upper window_years=%d: 거래 없음, 건너뜀", w)
            continue
        for level in levels:
            col = LEVEL_COLUMNS[level]
            codes = sorted(c for c in df_w[col].dropna().astype(str).str.strip().unique() if c)
            for code in codes:
                total.extend(
                    build_stats_for_upper_region(
                        df_w,
                        level,
                        code,
                        as_of_month=as_of_month,
                        window_years=w,
                        period_start=ps,
                        period_end=pe,
                        batch_id=batch_id,
                    )
                )
    return total


def upsert_upper_stats_v2(records: list[dict], *, chunk_size: int | None = None) -> None:
    if not records:
        return
    cs = chunk_size if chunk_size and chunk_size > 0 else DEFAULT_UPSERT_CHUNK
    engine = get_engine()
    sql = text(
        """
        INSERT INTO land_upper_stats_v2 (
            region_level, region_code,
            as_of_month, window_years, period_start, period_end,
            zone_type, land_category,
            count, mean, std, ci_lower, ci_upper,
            p_min, p25, median, p75, p_max,
            computed_at, batch_id
        ) VALUES (
            :region_level, :region_code,
            :as_of_month, :window_years, :period_start, :period_end,
            :zone_type, :land_category,
            :count, :mean, :std, :ci_lower, :ci_upper,
            :p_min, :p25, :median, :p75, :p_max,
            NOW(), :batch_id
        )
        ON CONFLICT (region_level, region_code, as_of_month, window_years, zone_type, land_category)
        DO UPDATE SET
            period_start = EXCLUDED.period_start,
            period_end = EXCLUDED.period_end,
            count = EXCLUDED.count,
            mean = EXCLUDED.mean,
            std = EXCLUDED.std,
            ci_lower = EXCLUDED.ci_lower,
            ci_upper = EXCLUDED.ci_upper,
            p_min = EXCLUDED.p_min,
            p25 = EXCLUDED.p25,
            median = EXCLUDED.median,
            p75 = EXCLUDED.p75,
            p_max = EXCLUDED.p_max,
            computed_at = NOW(),
            batch_id = EXCLUDED.batch_id
        """
    )
    for start in range(0, len(records), cs):
        chunk = records[start : start + cs]
        with engine.begin() as conn:
            for rec in chunk:
                conn.execute(sql, rec)


def _count_upper_rows(as_of_month: date, windows: list[int]) -> int | None:
    if not windows:
        return None
    ws = sorted({int(w) for w in windows})
    in_clause = "window_years IN (" + ",".join(str(w) for w in ws) + ")"
    try:
        with get_engine().connect() as conn:
            n = conn.execute(
                text(
                    f"SELECT COUNT(*) FROM land_upper_stats_v2 "
                    f"WHERE as_of_month = :a AND {in_clause}"
                ),
                {"a": as_of_month},
            ).scalar()
            return int(n) if n is not None else None
    except Exception as exc:
        log.warning("land_upper_stats_v2 행 수 조회 실패: %s", exc)
        return None


def main() -> None:
    parser = argparse.ArgumentParser(description="V2 상위 행정구역 사전 집계")
    parser.add_argument("--as-of", type=str, default=None, help="기준월 YYYY-MM-01")
    parser.add_argument(
        "--windows",
        type=str,
        default=",".join(str(x) for x in STATS_V2_WINDOW_YEARS_ALL),
    )
    parser.add_argument("--sido-code", type=str, default=None, help="시도 2자리 제한")
    parser.add_argument(
        "--levels",
        type=str,
        default="sido,sigungu,eupmyeondong",
        help="집계 레벨 (쉼표)",
    )
    parser.add_argument("--batch-id", type=str, default=None)
    parser.add_argument("--upsert-chunk", type=int, default=None)
    args = parser.parse_args()

    try:
        sido_filter = parse_sido_code(args.sido_code)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    as_of_month = parse_as_of_month(args.as_of) if args.as_of else default_as_of_month()
    windows = sorted({int(x.strip()) for x in args.windows.split(",") if x.strip()})
    for w in windows:
        if w < 1 or w > 5:
            raise SystemExit(f"window_years 1~5만 허용: {w}")

    levels = [x.strip() for x in args.levels.split(",") if x.strip()]
    for lv in levels:
        if lv not in LEVEL_COLUMNS:
            raise SystemExit(f"알 수 없는 level: {lv}")

    batch_id = args.batch_id or uuid.uuid4().hex
    upsert_chunk = args.upsert_chunk or DEFAULT_UPSERT_CHUNK
    max_w = max(windows)
    p_start_min, period_end = period_bounds_for_window(as_of_month, max_w)

    rows_before = _count_upper_rows(as_of_month, windows)
    log.info(
        "upper V2 as_of=%s windows=%s levels=%s rows_before=%s",
        as_of_month,
        windows,
        levels,
        rows_before,
    )

    t0 = time.perf_counter()
    sidos = [sido_filter] if sido_filter else distinct_sido_codes_in_period(p_start_min, period_end)
    if not sidos:
        log.error("집계 대상 시도 없음")
        raise SystemExit(1)

    total_upsert = 0
    for i, sido in enumerate(tqdm(sidos, desc="upper_sido", unit="시도")):
        df = fetch_transactions_for_upper_union(p_start_min, period_end, sido_code=sido)
        log.info(
            "[%d/%d] sido=%s rows=%s mem=%.1fMB",
            i + 1,
            len(sidos),
            sido,
            f"{len(df):,}",
            _df_mem_mb(df),
        )
        if df.empty:
            continue
        recs = collect_upper_records_for_windows(
            df, as_of_month=as_of_month, windows=windows, batch_id=batch_id, levels=levels
        )
        upsert_upper_stats_v2(recs, chunk_size=upsert_chunk)
        total_upsert += len(recs)
        del df
        gc.collect()

    rows_after = _count_upper_rows(as_of_month, windows)
    log.info(
        "upper V2 완료 %.1f분 upsert_rows=%s rows_after=%s (delta=%s)",
        (time.perf_counter() - t0) / 60.0,
        f"{total_upsert:,}",
        f"{rows_after:,}" if rows_after is not None else "N/A",
        (
            f"{rows_after - rows_before:+,}"
            if rows_before is not None and rows_after is not None
            else "N/A"
        ),
    )


if __name__ == "__main__":
    main()
