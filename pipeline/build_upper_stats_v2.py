"""
V2 상위 행정구역 사전 집계: land_transactions → land_upper_stats_v2

집계 레벨: sido(2) · sigungu(5) · eupmyeondong(8) · city(5, 자치구형 시 통합 버킷)
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
    parse_col_axes,
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


def _sigungu_to_city_bucket(sigungu_code: str) -> str:
    """시군구 5자리 → 의사 시 단위 버킷 (floor/10*10). 청주 43111~ → 43110."""
    s = str(sigungu_code).strip()
    if not s.isdigit() or len(s) != 5:
        return ""
    n = int(s)
    return str((n // 10) * 10).zfill(5)


def _upper_stats_record(
    *,
    region_level: str,
    region_code: str,
    as_of_month: date,
    window_years: int,
    period_start: date,
    period_end: date,
    zone_type: str,
    land_category: str,
    col_axis: str,
    batch_id: str | None,
    prices,
) -> dict:
    stats = compute_stats(prices)
    return {
        "region_level": region_level,
        "region_code": region_code,
        "as_of_month": as_of_month,
        "window_years": window_years,
        "period_start": period_start,
        "period_end": period_end,
        "zone_type": zone_type,
        "land_category": land_category,
        "col_axis": col_axis,
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


def _zone_land_records_for_frame(
    work: pd.DataFrame,
    *,
    region_level: str,
    region_code: str,
    land_col: str,
    as_of_month: date,
    window_years: int,
    period_start: date,
    period_end: date,
    batch_id: str | None,
    col_axis: str,
) -> list[dict]:
    """한 상위지역 프레임에서 zone×land (ALL 포함) groupby 집계."""
    if work.empty:
        return []
    records: list[dict] = []

    def emit(zone: str, cat: str, prices) -> None:
        records.append(
            _upper_stats_record(
                region_level=region_level,
                region_code=region_code,
                as_of_month=as_of_month,
                window_years=window_years,
                period_start=period_start,
                period_end=period_end,
                zone_type=zone,
                land_category=cat,
                col_axis=col_axis,
                batch_id=batch_id,
                prices=prices,
            )
        )

    emit("ALL", "ALL", work["unit_price_per_sqm"].to_numpy())
    for zone, g in work.groupby("zone_type", sort=False):
        emit(str(zone), "ALL", g["unit_price_per_sqm"].to_numpy())
    for cat, g in work.groupby(land_col, sort=False):
        emit("ALL", str(cat), g["unit_price_per_sqm"].to_numpy())
    for (zone, cat), g in work.groupby(["zone_type", land_col], sort=False):
        emit(str(zone), str(cat), g["unit_price_per_sqm"].to_numpy())
    return records


def build_stats_for_upper_city(
    df: pd.DataFrame,
    city_code: str,
    sigungu_members: set[str],
    *,
    as_of_month: date,
    window_years: int,
    period_start: date,
    period_end: date,
    batch_id: str | None,
    col_axis: str = "category",
) -> list[dict]:
    """자치구형 시: 시군구 코드 여럿을 합쳐 zone×(지목|지목군) 통계."""
    if col_axis not in ("category", "group"):
        raise ValueError(f"col_axis 는 category|group: {col_axis}")
    land_col = "land_category" if col_axis == "category" else "jimok_group_code"
    rc = str(city_code).strip()
    if not sigungu_members:
        return []
    sub = df[df["sigungu_code"].astype(str).str.strip().isin(sigungu_members)]
    if sub.empty:
        return []

    work = sub.loc[:, ["zone_type", land_col, "unit_price_per_sqm"]].copy()
    work["zone_type"] = work["zone_type"].astype(str).str.strip()
    work[land_col] = work[land_col].astype(str).str.strip()
    work = work.dropna(subset=["unit_price_per_sqm"])
    return _zone_land_records_for_frame(
        work,
        region_level="city",
        region_code=rc,
        land_col=land_col,
        as_of_month=as_of_month,
        window_years=window_years,
        period_start=period_start,
        period_end=period_end,
        batch_id=batch_id,
        col_axis=col_axis,
    )


def fetch_transactions_for_upper_union(
    period_start_min: date,
    period_end: date,
    *,
    sido_code: str | None = None,
) -> pd.DataFrame:
    """region_codes 조인으로 eupmyeondong_code 확보.

    D-028: Master beopjungri → canonical 후 region_codes 조인.
    sido/sigungu/eup 는 canonical 행 기준(분구·면→읍 rollup 정합).
    """
    from region_canonical import region_codes_join_on_canonical

    engine = get_engine()
    where_sido = ""
    params: dict = {"p_start": period_start_min, "p_end": period_end}
    if sido_code:
        where_sido = "AND btrim(r.sido_code::text) = :sido"
        params["sido"] = sido_code

    join_sql = region_codes_join_on_canonical("lt", "r", active_only=True)

    query = f"""
        SELECT
            btrim(r.sido_code::text) AS sido_code,
            btrim(r.sigungu_code::text) AS sigungu_code,
            btrim(r.eupmyeondong_code::text) AS eupmyeondong_code,
            lt.zone_type_resolved  AS zone_type,
            lt.land_category_resolved AS land_category,
            COALESCE(lt.jimok_group_code, 'other') AS jimok_group_code,
            lt.unit_price_per_sqm,
            lt.contract_date::date AS contract_date
        FROM land_transactions_resolved lt
        {join_sql}
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
            "jimok_group_code",
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
    col_axis: str = "category",
) -> list[dict]:
    if col_axis not in ("category", "group"):
        raise ValueError(f"col_axis 는 category|group: {col_axis}")
    land_col = "land_category" if col_axis == "category" else "jimok_group_code"
    col = LEVEL_COLUMNS[region_level]
    rc = str(region_code).strip()
    sub = df[df[col].astype(str).str.strip() == rc]
    if sub.empty:
        return []

    work = sub.loc[:, ["zone_type", land_col, "unit_price_per_sqm"]].copy()
    work["zone_type"] = work["zone_type"].astype(str).str.strip()
    work[land_col] = work[land_col].astype(str).str.strip()
    work = work.dropna(subset=["unit_price_per_sqm"])
    return _zone_land_records_for_frame(
        work,
        region_level=region_level,
        region_code=rc,
        land_col=land_col,
        as_of_month=as_of_month,
        window_years=window_years,
        period_start=period_start,
        period_end=period_end,
        batch_id=batch_id,
        col_axis=col_axis,
    )


def _collect_upper_level_axis(
    df_w: pd.DataFrame,
    *,
    region_level: str,
    region_col: str,
    land_col: str,
    as_of_month: date,
    window_years: int,
    period_start: date,
    period_end: date,
    batch_id: str,
    col_axis: str,
) -> list[dict]:
    """한 level × col_axis 를 시도 스코프 전체 groupby로 집계."""
    work = df_w.loc[
        :, [region_col, "zone_type", land_col, "unit_price_per_sqm"]
    ].copy()
    work[region_col] = work[region_col].astype(str).str.strip()
    work["zone_type"] = work["zone_type"].astype(str).str.strip()
    work[land_col] = work[land_col].astype(str).str.strip()
    work = work.dropna(subset=["unit_price_per_sqm"])
    work = work[work[region_col] != ""]
    if work.empty:
        return []

    records: list[dict] = []

    def emit(code: str, zone: str, cat: str, prices) -> None:
        records.append(
            _upper_stats_record(
                region_level=region_level,
                region_code=code,
                as_of_month=as_of_month,
                window_years=window_years,
                period_start=period_start,
                period_end=period_end,
                zone_type=zone,
                land_category=cat,
                col_axis=col_axis,
                batch_id=batch_id,
                prices=prices,
            )
        )

    for code, g in work.groupby(region_col, sort=False):
        emit(str(code), "ALL", "ALL", g["unit_price_per_sqm"].to_numpy())
    for (code, zone), g in work.groupby([region_col, "zone_type"], sort=False):
        emit(str(code), str(zone), "ALL", g["unit_price_per_sqm"].to_numpy())
    for (code, cat), g in work.groupby([region_col, land_col], sort=False):
        emit(str(code), "ALL", str(cat), g["unit_price_per_sqm"].to_numpy())
    for (code, zone, cat), g in work.groupby(
        [region_col, "zone_type", land_col], sort=False
    ):
        emit(str(code), str(zone), str(cat), g["unit_price_per_sqm"].to_numpy())
    return records


def collect_upper_records_for_windows(
    df_full: pd.DataFrame,
    *,
    as_of_month: date,
    windows: list[int],
    batch_id: str,
    levels: list[str] | None = None,
    col_axes: list[str] | None = None,
) -> list[dict]:
    levels = levels or list(LEVEL_COLUMNS.keys())
    axes = col_axes or ["category"]
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
        for axis in axes:
            land_col = "land_category" if axis == "category" else "jimok_group_code"
            for level in levels:
                if level == "city":
                    sg_series = df_w["sigungu_code"].astype(str).str.strip()
                    bucket_to_sigungus: dict[str, set[str]] = {}
                    for s in sg_series.unique():
                        if not s or not str(s).isdigit() or len(str(s)) != 5:
                            continue
                        b = _sigungu_to_city_bucket(s)
                        if not b:
                            continue
                        bucket_to_sigungus.setdefault(b, set()).add(s)
                    for bucket, members in sorted(bucket_to_sigungus.items()):
                        if len(members) < 2:
                            continue
                        total.extend(
                            build_stats_for_upper_city(
                                df_w,
                                bucket,
                                members,
                                as_of_month=as_of_month,
                                window_years=w,
                                period_start=ps,
                                period_end=pe,
                                batch_id=batch_id,
                                col_axis=axis,
                            )
                        )
                    continue

                total.extend(
                    _collect_upper_level_axis(
                        df_w,
                        region_level=level,
                        region_col=LEVEL_COLUMNS[level],
                        land_col=land_col,
                        as_of_month=as_of_month,
                        window_years=w,
                        period_start=ps,
                        period_end=pe,
                        batch_id=batch_id,
                        col_axis=axis,
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
            zone_type, land_category, col_axis,
            count, mean, std, ci_lower, ci_upper,
            p_min, p25, median, p75, p_max,
            computed_at, batch_id
        ) VALUES (
            :region_level, :region_code,
            :as_of_month, :window_years, :period_start, :period_end,
            :zone_type, :land_category, :col_axis,
            :count, :mean, :std, :ci_lower, :ci_upper,
            :p_min, :p25, :median, :p75, :p_max,
            NOW(), :batch_id
        )
        ON CONFLICT (
            region_level, region_code, as_of_month, window_years,
            zone_type, land_category, col_axis
        )
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
        default="sido,sigungu,eupmyeondong,city",
        help="집계 레벨 (쉼표)",
    )
    parser.add_argument("--batch-id", type=str, default=None)
    parser.add_argument("--upsert-chunk", type=int, default=None)
    parser.add_argument(
        "--col-axis",
        type=str,
        default="category",
        help="집계 열 축: category | group | both",
    )
    args = parser.parse_args()

    try:
        sido_filter = parse_sido_code(args.sido_code)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    try:
        col_axes = parse_col_axes(args.col_axis)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    as_of_month = parse_as_of_month(args.as_of) if args.as_of else default_as_of_month()
    windows = sorted({int(x.strip()) for x in args.windows.split(",") if x.strip()})
    for w in windows:
        if w < 1 or w > 5:
            raise SystemExit(f"window_years 1~5만 허용: {w}")

    levels = [x.strip() for x in args.levels.split(",") if x.strip()]
    for lv in levels:
        if lv not in set(LEVEL_COLUMNS) | {"city"}:
            raise SystemExit(f"알 수 없는 level: {lv}")

    batch_id = args.batch_id or uuid.uuid4().hex
    upsert_chunk = args.upsert_chunk or DEFAULT_UPSERT_CHUNK
    max_w = max(windows)
    p_start_min, period_end = period_bounds_for_window(as_of_month, max_w)

    rows_before = _count_upper_rows(as_of_month, windows)
    log.info(
        "upper V2 as_of=%s windows=%s levels=%s col_axes=%s rows_before=%s",
        as_of_month,
        windows,
        levels,
        col_axes,
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
            df,
            as_of_month=as_of_month,
            windows=windows,
            batch_id=batch_id,
            levels=levels,
            col_axes=col_axes,
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
