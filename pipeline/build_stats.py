"""
사전 집계 파이프라인
land_transactions 테이블에서 무료 화면용 사전 집계(land_basic_stats)를 생성한다.

집계 기준:
  - 법정동/리 × 용도지역 × 지목 (각 'ALL' 포함)
  - 연도: land_transactions 의 최대 contract_year 기준 최근 N개년(포함), N=constants.DEFAULT_YEARS_BACK
  - 해제 제외, is_valid=TRUE, 단가 NOT NULL

사용법:
    python build_stats.py                   # 전체 재계산
    python build_stats.py --region 4113510700  # 특정 법정동/리만 재계산
"""

from __future__ import annotations

import argparse
import logging
import time
from itertools import product

import pandas as pd
from sqlalchemy import text
from tqdm import tqdm

from constants import DEFAULT_YEARS_BACK
from db_utils import get_engine
from stats import compute_stats

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


def get_year_range() -> tuple[int, int]:
    """
    원장의 최대 contract_year 기준 최근 DEFAULT_YEARS_BACK 개 연도(포함 구간).

    예: MAX(contract_year)=2024, DEFAULT_YEARS_BACK=4 → 2021 ~ 2024
    """
    engine = get_engine()
    with engine.connect() as conn:
        max_year = conn.execute(
            text(
                "SELECT MAX(contract_year) FROM land_transactions "
                "WHERE contract_year IS NOT NULL"
            )
        ).scalar()

    if max_year is None:
        raise RuntimeError(
            "land_transactions 에 유효한 contract_year 가 없습니다. "
            "clean.py 적재 후 다시 실행하세요."
        )

    max_y = int(max_year)
    year_to = max_y
    year_from = max_y - DEFAULT_YEARS_BACK + 1
    log.info(
        "집계 연도 범위: %d ~ %d (원장 MAX(contract_year)=%d, 최근 %d년)",
        year_from,
        year_to,
        max_y,
        DEFAULT_YEARS_BACK,
    )
    return year_from, year_to


def fetch_transactions_for_stats(
    beopjungri_codes: list[str] | None,
    year_from: int,
    year_to: int,
) -> pd.DataFrame:
    """사전 집계용 거래 데이터를 조회한다."""
    engine = get_engine()
    where_region = ""
    params: dict = {"year_from": year_from, "year_to": year_to}

    if beopjungri_codes:
        where_region = "AND beopjungri_code = ANY(:codes)"
        params["codes"] = beopjungri_codes

    query = f"""
        SELECT beopjungri_code, zone_type, land_category, unit_price_per_sqm
        FROM land_transactions
        WHERE is_valid = TRUE
          AND is_cancelled = FALSE
          AND unit_price_per_sqm IS NOT NULL
          AND contract_year BETWEEN :year_from AND :year_to
          {where_region}
    """
    with engine.connect() as conn:
        rows = conn.execute(text(query), params).fetchall()

    return pd.DataFrame(rows, columns=["beopjungri_code", "zone_type", "land_category", "unit_price_per_sqm"])


def log_empty_fetch_diagnostics(
    beopjungri_codes: list[str] | None,
    year_from: int,
    year_to: int,
) -> None:
    """집계 조회가 비었을 때, 필터 단계별 건수를 로그로 남긴다."""
    engine = get_engine()
    region_tail = ""
    params: dict = {"year_from": year_from, "year_to": year_to}
    if beopjungri_codes:
        region_tail = " AND beopjungri_code = ANY(:codes)"
        params["codes"] = beopjungri_codes

    base = (
        "FROM land_transactions WHERE contract_year BETWEEN :year_from AND :year_to"
        + region_tail
    )

    checks: list[tuple[str, str]] = [
        ("연도 구간 내 전체", f"SELECT COUNT(*) {base}"),
        ("… 위 중 is_valid = TRUE", f"SELECT COUNT(*) {base} AND is_valid = TRUE"),
        (
            "… 위 중 해제 아님(is_cancelled = FALSE)",
            f"SELECT COUNT(*) {base} AND is_valid = TRUE AND is_cancelled = FALSE",
        ),
        (
            "… 위 중 단가 NOT NULL (집계 조회와 동일)",
            f"SELECT COUNT(*) {base} AND is_valid = TRUE AND is_cancelled = FALSE "
            f"AND unit_price_per_sqm IS NOT NULL",
        ),
        (
            "… 집계 조건 + beopjungri_code 비어 있음",
            f"SELECT COUNT(*) {base} AND is_valid = TRUE AND is_cancelled = FALSE "
            f"AND unit_price_per_sqm IS NOT NULL "
            f"AND (beopjungri_code IS NULL OR TRIM(beopjungri_code) = '')",
        ),
    ]

    log.warning("집계할 데이터가 없습니다. 아래 단계별 건수를 확인하세요.")
    with engine.connect() as conn:
        for label, sql in checks:
            n = conn.execute(text(sql), params).scalar()
            log.warning("  [%s] %s건", label, int(n or 0))


def build_stats_for_region(
    df: pd.DataFrame,
    beopjungri_code: str,
    year_from: int,
    year_to: int,
) -> list[dict]:
    """
    한 법정동/리에 대해 용도지역 × 지목 조합별 통계를 계산한다.
    'ALL' 레이블은 해당 차원의 전체 합계를 의미한다.
    """
    sub = df[df["beopjungri_code"] == beopjungri_code].copy()
    if sub.empty:
        return []

    zone_types = ["ALL"] + sorted(sub["zone_type"].dropna().unique().tolist())
    land_cats = ["ALL"] + sorted(sub["land_category"].dropna().unique().tolist())

    records = []
    for zone, cat in product(zone_types, land_cats):
        mask = pd.Series([True] * len(sub), index=sub.index)
        if zone != "ALL":
            mask &= sub["zone_type"] == zone
        if cat != "ALL":
            mask &= sub["land_category"] == cat

        prices = sub.loc[mask, "unit_price_per_sqm"].dropna().tolist()
        stats = compute_stats(prices)

        records.append({
            "beopjungri_code": beopjungri_code,
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
            "year_from": year_from,
            "year_to": year_to,
        })

    return records


def _timing_log(prefix: str, label: str, t0: float) -> float:
    """t0부터의 경과(초)를 로깅하고, 경과값을 반환한다."""
    sec = time.perf_counter() - t0
    log.info("[%s timing] %s 소요=%.1fs (%.2f분)", prefix, label, sec, sec / 60.0)
    return sec


def upsert_basic_stats(records: list[dict]) -> None:
    """계산된 통계를 land_basic_stats 에 UPSERT 한다."""
    if not records:
        return
    engine = get_engine()
    with engine.begin() as conn:
        for rec in records:
            conn.execute(
                text("""
                    INSERT INTO land_basic_stats (
                        beopjungri_code, zone_type, land_category,
                        count, mean, std, ci_lower, ci_upper,
                        p_min, p25, median, p75, p_max,
                        year_from, year_to, computed_at
                    ) VALUES (
                        :beopjungri_code, :zone_type, :land_category,
                        :count, :mean, :std, :ci_lower, :ci_upper,
                        :p_min, :p25, :median, :p75, :p_max,
                        :year_from, :year_to, NOW()
                    )
                    ON CONFLICT (beopjungri_code, zone_type, land_category, year_from, year_to)
                    DO UPDATE SET
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
                        computed_at = NOW()
                """),
                rec,
            )


def main():
    parser = argparse.ArgumentParser(description="사전 집계 테이블 생성")
    parser.add_argument("--region", type=str, default=None, help="특정 법정동/리 코드 (미지정 시 전체)")
    args = parser.parse_args()

    pipeline_t0 = time.perf_counter()
    rng_t0 = time.perf_counter()
    year_from, year_to = get_year_range()
    _timing_log("build_stats", "year_range_query", rng_t0)

    codes = [args.region] if args.region else None

    fetch_t0 = time.perf_counter()
    log.info("거래 데이터 조회 중...")
    df = fetch_transactions_for_stats(codes, year_from, year_to)
    _timing_log("build_stats", "sql_fetch_land_transactions", fetch_t0)
    log.info("조회 결과 DataFrame 행수=%s", f"{len(df):,}")

    if df.empty:
        log_empty_fetch_diagnostics(codes, year_from, year_to)
        total_sec = time.perf_counter() - pipeline_t0
        log.info(
            "[%s timing] build_stats_total(비어종료) 소요=%.1fs (%.2f분)",
            "build_stats",
            total_sec,
            total_sec / 60.0,
        )
        return

    all_codes = df["beopjungri_code"].unique().tolist()
    log.info("집계 대상 법정동/리: %d개", len(all_codes))

    agg_t0 = time.perf_counter()
    total_records = []
    for code in tqdm(all_codes, desc="집계"):
        records = build_stats_for_region(df, code, year_from, year_to)
        total_records.extend(records)
    _timing_log("build_stats", "python_aggregate_by_beopjungri", agg_t0)

    log.info("집계 결과: %d행, DB 저장 중...", len(total_records))
    ups_t0 = time.perf_counter()
    upsert_basic_stats(total_records)
    _timing_log("build_stats", "db_upsert_land_basic_stats", ups_t0)
    total_sec = time.perf_counter() - pipeline_t0
    log.info(
        "[%s timing] build_stats_total 소요=%.1fs (%.2f분)",
        "build_stats",
        total_sec,
        total_sec / 60.0,
    )
    log.info("사전 집계 완료")


if __name__ == "__main__":
    main()
