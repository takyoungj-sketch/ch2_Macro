"""
V2 사전 집계 파이프라인
land_transactions → land_basic_stats_v2

집계 기준 (docs/V2_STATS_DESIGN.md):
  - 법정동/리 × 용도지역 × 지목 (각 'ALL' 포함)
  - 기준월 as_of_month: 해당 달 1일 저장 (UI는 동일 달 말일까지 반영)
  - 창 window_years ∈ {1..5}: contract_date 가 [period_start, period_end] (포함)
  - 해제 제외, is_valid=TRUE, 단가 NOT NULL, contract_date NOT NULL

전국 프로덕션 (무료 3·5년 예시):
  # .env: STATS_V2_ASSUMED_TODAY=2026-01-01 등 — docs/V2_STATS_PRODUCTION.md 참고
  python build_stats_v2.py --as-of 2025-12-01 --windows 3,5

  --region 또는 --sido-code(또는 STATS_V2_SIDO_CODE) 가 있으면 해당 범위만 1회 조회.
  둘 다 없으면 시도 코드 목록을 조회한 뒤 시도별로 청크 처리(메모리·재시작 안전).

선행 조건: db/007_land_basic_stats_v2.sql · 권장 db/008_land_transactions_v2_batch_index.sql
"""

from __future__ import annotations

import argparse
import calendar
import gc
import logging
import os
import sys
import time
import uuid
import warnings
from datetime import date, datetime, timedelta
from itertools import product

import pandas as pd
from sqlalchemy import text
from tqdm import tqdm

from constants import STATS_V2_WINDOW_YEARS_ALL
from db_utils import get_engine
from stats import compute_stats

warnings.filterwarnings("ignore", category=RuntimeWarning, module="scipy")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger(__name__)

DEFAULT_UPSERT_CHUNK = int(os.environ.get("STATS_V2_UPSERT_CHUNK", "400"))


def last_day_of_month(any_date_in_month: date) -> date:
    """해당 연·월의 말일."""
    y, m = any_date_in_month.year, any_date_in_month.month
    return date(y, m, calendar.monthrange(y, m)[1])


def _anchor_n_calendar_years_before(period_end: date, window_years: int) -> date:
    """period_end와 같은 월·일에서 연도만 window_years 만큼 뺀 날(윤달·말일 클램프)."""
    y = period_end.year - window_years
    last = calendar.monthrange(y, period_end.month)[1]
    day = min(period_end.day, last)
    return date(y, period_end.month, day)


def period_bounds_for_window(as_of_month: date, window_years: int) -> tuple[date, date]:
    """
    V2_STATS_DESIGN §3–4: period_end = as_of_month 달의 말일,
    period_start = period_end 에서 달력 window_years년 전(클램프)의 익일.
    """
    if as_of_month.day != 1:
        raise ValueError(f"as_of_month 는 반드시 해당 월 1일이어야 합니다: {as_of_month}")
    period_end = last_day_of_month(as_of_month)
    anchor = _anchor_n_calendar_years_before(period_end, window_years)
    period_start = anchor + timedelta(days=1)
    return period_start, period_end


def default_as_of_month(today: date | None = None) -> date:
    """
    기준월(as_of_month) 기본값:
    - STATS_V2_DEFAULT_AS_OF_MONTH 가 있으면 그 달 1일
    - 없으면 STATS_V2_ASSUMED_TODAY 가 있으면 그 날짜를 «오늘»로 본 §3 직전 달 1일
    - 둘 다 없으면 배치 실행일(실제 오늘) 기준 §3 직전 달 1일
    """
    raw = os.environ.get("STATS_V2_DEFAULT_AS_OF_MONTH", "").strip()
    if raw:
        return parse_as_of_month(raw)
    if today is None:
        assumed = os.environ.get("STATS_V2_ASSUMED_TODAY", "").strip()
        if assumed:
            today = date.fromisoformat(assumed)
    today = today or date.today()
    first_this = today.replace(day=1)
    last_day_prev_month = first_this - timedelta(days=1)
    return last_day_prev_month.replace(day=1)


def parse_as_of_month(s: str) -> date:
    """YYYY-MM-DD → date; 반드시 해당 월 1일."""
    parts = s.strip().split("-")
    if len(parts) != 3:
        raise ValueError("--as-of 는 YYYY-MM-DD 형식(해당 월 1일)이어야 합니다.")
    y, mo, d = int(parts[0]), int(parts[1]), int(parts[2])
    parsed = date(y, mo, d)
    if parsed.day != 1:
        raise ValueError(f"as_of_month 는 월의 1일이어야 합니다: {parsed}")
    return parsed


def parse_sido_code(s: str | None) -> str | None:
    """시도 코드 2자리(숫자). 예: 충청북도 43. 미지정이면 None."""
    if s is None:
        return None
    t = str(s).strip()
    if not t:
        return None
    if len(t) != 2 or not t.isdigit():
        raise ValueError("--sido-code 는 숫자 2자리여야 합니다. 예: 충청북도 43")
    return t


def distinct_sido_codes_in_period(period_start_min: date, period_end: date) -> list[str]:
    """긴 창 구간 안에 거래가 있는 시도 코드 목록(정렬)."""
    engine = get_engine()
    q = text(
        """
        SELECT DISTINCT btrim(sido_code::text) AS sc
        FROM land_transactions
        WHERE is_valid = TRUE
          AND is_cancelled = FALSE
          AND unit_price_per_sqm IS NOT NULL
          AND contract_date IS NOT NULL
          AND contract_date >= :p_start
          AND contract_date <= :p_end
        ORDER BY 1
        """
    )
    with engine.connect() as conn:
        rows = conn.execute(q, {"p_start": period_start_min, "p_end": period_end}).fetchall()
    out: list[str] = []
    for r in rows:
        s = str(r[0]).strip()
        if s:
            out.append(s[:2])
    return out


def fetch_transactions_for_window_union(
    beopjungri_codes: list[str] | None,
    period_start_min: date,
    period_end: date,
    *,
    sido_code: str | None = None,
) -> pd.DataFrame:
    """여러 창을 한 번에 돌릴 때, 가장 긴 구간 [period_start_min, period_end] 만큼만 조회."""
    engine = get_engine()
    where_region = ""
    where_sido = ""
    params: dict = {
        "p_start": period_start_min,
        "p_end": period_end,
    }

    if sido_code:
        where_sido = "AND sido_code = :sido"
        params["sido"] = sido_code
    if beopjungri_codes:
        where_region = "AND beopjungri_code = ANY(:codes)"
        params["codes"] = beopjungri_codes

    query = f"""
        SELECT beopjungri_code, zone_type, land_category, unit_price_per_sqm,
               contract_date::date AS contract_date
        FROM land_transactions
        WHERE is_valid = TRUE
          AND is_cancelled = FALSE
          AND unit_price_per_sqm IS NOT NULL
          AND contract_date IS NOT NULL
          AND contract_date >= :p_start
          AND contract_date <= :p_end
          {where_sido}
          {where_region}
    """
    with engine.connect() as conn:
        rows = conn.execute(text(query), params).fetchall()

    return pd.DataFrame(
        rows,
        columns=[
            "beopjungri_code",
            "zone_type",
            "land_category",
            "unit_price_per_sqm",
            "contract_date",
        ],
    )


def _df_mem_mb(df: pd.DataFrame) -> float:
    try:
        return float(df.memory_usage(deep=True).sum()) / (1024 * 1024)
    except Exception:
        return 0.0


_SIZE_SQL = {
    "land_basic_stats_v2": text(
        "SELECT pg_total_relation_size('land_basic_stats_v2'::regclass)"
    ),
    "land_transactions": text(
        "SELECT pg_total_relation_size('land_transactions'::regclass)"
    ),
}


def _pg_total_relation_size_bytes_whitelist(table: str) -> int | None:
    """PostgreSQL pg_total_relation_size (테이블+토스트+인덱스). 화이트리스트만 허용."""
    sql = _SIZE_SQL.get(table)
    if sql is None:
        return None
    engine = get_engine()
    try:
        with engine.connect() as conn:
            r = conn.execute(sql).scalar()
            return int(r) if r is not None else None
    except Exception as exc:
        log.warning("pg_total_relation_size(%s) 실패: %s", table, exc)
        return None


def _count_v2_batch_rows(as_of_month: date, windows: list[int]) -> int | None:
    if not windows:
        return None
    engine = get_engine()
    ws = sorted({int(w) for w in windows})
    for w in ws:
        if w < 1 or w > 5:
            return None
    in_clause = "window_years IN (" + ",".join(str(w) for w in ws) + ")"
    try:
        with engine.connect() as conn:
            q = text(
                "SELECT COUNT(*) FROM land_basic_stats_v2 "
                "WHERE as_of_month = :a AND " + in_clause
            )
            n = conn.execute(q, {"a": as_of_month}).scalar()
            return int(n) if n is not None else None
    except Exception as exc:
        log.warning("land_basic_stats_v2 행 수 조회 실패: %s", exc)
        return None


def log_empty_fetch_diagnostics_v2(
    beopjungri_codes: list[str] | None,
    period_start: date,
    period_end: date,
    *,
    sido_code: str | None = None,
) -> None:
    engine = get_engine()
    region_tail = ""
    sido_tail = ""
    params: dict = {"p_start": period_start, "p_end": period_end}
    if sido_code:
        sido_tail = " AND sido_code = :sido"
        params["sido"] = sido_code
    if beopjungri_codes:
        region_tail = " AND beopjungri_code = ANY(:codes)"
        params["codes"] = beopjungri_codes

    base_date = (
        "FROM land_transactions WHERE contract_date IS NOT NULL "
        "AND contract_date >= :p_start AND contract_date <= :p_end"
        + sido_tail
        + region_tail
    )

    checks: list[tuple[str, str]] = [
        ("날짜 구간 내 전체", f"SELECT COUNT(*) {base_date}"),
        ("(동일 구간) is_valid = TRUE", f"SELECT COUNT(*) {base_date} AND is_valid = TRUE"),
        (
            "(동일 구간) 해제 아님",
            f"SELECT COUNT(*) {base_date} AND is_valid = TRUE AND is_cancelled = FALSE",
        ),
        (
            "(동일 구간) 단가 NOT NULL",
            f"SELECT COUNT(*) {base_date} AND is_valid = TRUE AND is_cancelled = FALSE "
            f"AND unit_price_per_sqm IS NOT NULL",
        ),
    ]

    log.warning("V2 집계할 데이터가 없습니다. 아래 단계별 건수를 확인하세요.")
    with engine.connect() as conn:
        for label, sql in checks:
            n = conn.execute(text(sql), params).scalar()
            log.warning("  [%s] %s건", label, int(n or 0))


def build_stats_for_region_v2(
    df: pd.DataFrame,
    beopjungri_code: str,
    *,
    as_of_month: date,
    window_years: int,
    period_start: date,
    period_end: date,
    batch_id: str | None,
) -> list[dict]:
    """한 법정동/리 × 한 창 에 대해 용도×지목 조합 통계."""
    sub = df[df["beopjungri_code"].astype(str).str.strip() == str(beopjungri_code).strip()].copy()
    if sub.empty:
        return []

    zone_types = ["ALL"] + sorted(sub["zone_type"].dropna().astype(str).str.strip().unique().tolist())
    land_cats = ["ALL"] + sorted(sub["land_category"].dropna().astype(str).str.strip().unique().tolist())

    records: list[dict] = []
    bclean = str(beopjungri_code).strip()
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
                "as_of_month": as_of_month,
                "window_years": window_years,
                "period_start": period_start,
                "period_end": period_end,
                "beopjungri_code": bclean,
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


def collect_records_for_windows(
    df_full: pd.DataFrame,
    *,
    as_of_month: date,
    windows: list[int],
    batch_id: str,
) -> list[dict]:
    """한 DataFrame(시도 또는 전체 스코프)에 대해 모든 window·법정동 조합 레코드 생성."""
    df = df_full.copy()
    if df.empty:
        return []
    df["contract_date"] = pd.to_datetime(df["contract_date"]).dt.date
    total_records: list[dict] = []
    for w in windows:
        ps, pe = period_bounds_for_window(as_of_month, w)
        df_w = df[(df["contract_date"] >= ps) & (df["contract_date"] <= pe)]
        if df_w.empty:
            log.warning("window_years=%d 에 해당하는 거래가 없습니다. 건너뜀.", w)
            continue
        all_codes = sorted(df_w["beopjungri_code"].astype(str).str.strip().unique())
        for code in all_codes:
            total_records.extend(
                build_stats_for_region_v2(
                    df_w,
                    code,
                    as_of_month=as_of_month,
                    window_years=w,
                    period_start=ps,
                    period_end=pe,
                    batch_id=batch_id,
                )
            )
    return total_records


def upsert_basic_stats_v2(
    records: list[dict],
    *,
    chunk_size: int | None = None,
) -> None:
    """land_basic_stats_v2 UPSERT (db/007 제약과 동일 그레인). 청크 단위 커밋으로 장시간 트랜잭션 완화."""
    if not records:
        return
    cs = chunk_size if chunk_size is not None else DEFAULT_UPSERT_CHUNK
    if cs < 1:
        cs = DEFAULT_UPSERT_CHUNK
    engine = get_engine()
    sql = text(
        """
        INSERT INTO land_basic_stats_v2 (
            as_of_month, window_years, period_start, period_end,
            beopjungri_code, zone_type, land_category,
            count, mean, std, ci_lower, ci_upper,
            p_min, p25, median, p75, p_max,
            computed_at, batch_id
        ) VALUES (
            :as_of_month, :window_years, :period_start, :period_end,
            :beopjungri_code, :zone_type, :land_category,
            :count, :mean, :std, :ci_lower, :ci_upper,
            :p_min, :p25, :median, :p75, :p_max,
            NOW(), :batch_id
        )
        ON CONFLICT (as_of_month, window_years, beopjungri_code, zone_type, land_category)
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


def main() -> None:
    parser = argparse.ArgumentParser(description="V2 사전 집계 (land_basic_stats_v2)")
    parser.add_argument(
        "--as-of",
        type=str,
        default=None,
        help="기준월(YYYY-MM-01). 생략 시 직전 달 1일",
    )
    parser.add_argument(
        "--windows",
        type=str,
        default=",".join(str(x) for x in STATS_V2_WINDOW_YEARS_ALL),
        help="창 연수 목록 (쉼표). 예: 1,2,3,4,5 또는 3,5",
    )
    parser.add_argument("--region", type=str, default=None, help="특정 법정동/리 코드 (미지정 시 전체)")
    parser.add_argument(
        "--sido-code",
        type=str,
        default=None,
        help="시도 코드 2자리로 거래 조회 범위 제한 (예: 충청북도 43). --region 과 병행 가능",
    )
    parser.add_argument(
        "--single-fetch",
        action="store_true",
        help="전국일 때 시도 분할 없이 한 번에 조회(메모리 매우 큼; 디버그용)",
    )
    parser.add_argument(
        "--upsert-chunk",
        type=int,
        default=None,
        help=f"UPSERT 커밋 단위 행 수 (기본 env STATS_V2_UPSERT_CHUNK 또는 {DEFAULT_UPSERT_CHUNK})",
    )
    parser.add_argument(
        "--batch-id",
        type=str,
        default=None,
        help="배치 식별자 (미지정 시 UUID)",
    )
    args = parser.parse_args()

    try:
        sido_filter = parse_sido_code(args.sido_code)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    if sido_filter is None:
        env_sc = os.environ.get("STATS_V2_SIDO_CODE", "").strip()
        if env_sc:
            log.warning(
                "STATS_V2_SIDO_CODE=%s → 시도 단일 모드입니다. 전국 배치는 이 변수를 비우고 실행하세요.",
                env_sc,
            )
            try:
                sido_filter = parse_sido_code(env_sc)
            except ValueError as exc:
                raise SystemExit(f"환경변수 STATS_V2_SIDO_CODE: {exc}") from exc

    as_of_month = parse_as_of_month(args.as_of) if args.as_of else default_as_of_month()

    # 방어 코드: as_of_month 가 비정상 범위이면 경고 후 계속 (오퍼레이터가 눈치채도록).
    _today = date.today()
    if as_of_month > _today:
        log.warning(
            "⚠ as_of_month=%s 이(가) 오늘(%s)보다 미래입니다. "
            "STATS_V2_DEFAULT_AS_OF_MONTH 또는 --as-of 값을 확인하세요.",
            as_of_month,
            _today,
        )
    elif (_today - as_of_month).days > 180:
        log.warning(
            "⚠ as_of_month=%s 이(가) 오늘(%s) 기준 %d일 전입니다(180일 초과). "
            "오래된 기준월로 통계가 집계됩니다. 의도한 경우가 아니면 확인하세요.",
            as_of_month,
            _today,
            (_today - as_of_month).days,
        )

    try:
        windows = sorted({int(x.strip()) for x in args.windows.split(",") if x.strip()})
    except ValueError as exc:
        raise SystemExit(f"--windows 파싱 실패: {args.windows}") from exc
    for w in windows:
        if w < 1 or w > 5:
            raise SystemExit(f"window_years 는 1~5 만 허용: {w}")

    batch_id = args.batch_id or uuid.uuid4().hex
    codes = [args.region] if args.region else None
    upsert_chunk = (
        args.upsert_chunk
        if args.upsert_chunk is not None and args.upsert_chunk > 0
        else DEFAULT_UPSERT_CHUNK
    )

    max_w = max(windows)
    p_start_min, period_end = period_bounds_for_window(as_of_month, max_w)

    use_sido_chunking = (
        codes is None
        and sido_filter is None
        and not args.single_fetch
    )

    log.info(
        "V2 사전집계 as_of_month=%s mode=%s batch_id=%s windows=%s 긴창=[%s ~ %s] upsert_chunk=%d",
        as_of_month,
        "시도청크" if use_sido_chunking else "단일스코프",
        batch_id[:12] + "...",
        windows,
        p_start_min,
        period_end,
        upsert_chunk,
    )

    wall_start_dt = datetime.now().astimezone()
    log.info("배치 wall-clock 시작: %s", wall_start_dt.strftime("%Y-%m-%d %H:%M:%S %z"))

    v2_bytes_before = _pg_total_relation_size_bytes_whitelist("land_basic_stats_v2")
    v2_rows_before = _count_v2_batch_rows(as_of_month, windows)
    if v2_bytes_before is not None:
        log.info(
            "시작 시점 land_basic_stats_v2 총 용량~%.2f MiB (rows as_of+windows=%s)",
            v2_bytes_before / (1024 * 1024),
            f"{v2_rows_before:,}" if v2_rows_before is not None else "N/A",
        )
    else:
        log.info(
            "시작 시점 V2 행수(해당 as_of·windows): %s",
            f"{v2_rows_before:,}" if v2_rows_before is not None else "N/A",
        )

    batch_started = time.perf_counter()
    total_rows_fetched = 0
    total_upsert_rows = 0
    sido_times: list[float] = []
    cumulative_fetch_sec = 0.0
    cumulative_agg_sec = 0.0
    cumulative_upsert_sec = 0.0

    def run_one_scope(
        sido: str | None,
        label: str,
        *,
        record_timing: bool = True,
    ) -> None:
        nonlocal total_rows_fetched, total_upsert_rows, sido_times
        nonlocal cumulative_fetch_sec, cumulative_agg_sec, cumulative_upsert_sec
        scope_start = time.perf_counter()
        log.info("[%s] 조회 시작 sido=%s ...", label, sido or "-")
        df_full = fetch_transactions_for_window_union(
            codes, p_start_min, period_end, sido_code=sido
        )
        n = len(df_full)
        mem_mb = _df_mem_mb(df_full)
        total_rows_fetched += n
        log.info(
            "[%s] 조회 완료 sido=%s 행수=%s DataFrame~%.1fMB 경과=%.1fs",
            label,
            sido or "-",
            f"{n:,}",
            mem_mb,
            time.perf_counter() - scope_start,
        )
        cumulative_fetch_sec += time.perf_counter() - scope_start
        if df_full.empty:
            log_empty_fetch_diagnostics_v2(codes, p_start_min, period_end, sido_code=sido)
            if record_timing:
                sido_times.append(time.perf_counter() - scope_start)
            return
        agg_t0 = time.perf_counter()
        total_records = collect_records_for_windows(
            df_full, as_of_month=as_of_month, windows=windows, batch_id=batch_id
        )
        agg_sec_scope = time.perf_counter() - agg_t0
        cumulative_agg_sec += agg_sec_scope
        log.info(
            "[%s] 집계 행 %d건 (집계 %.1fs)",
            label,
            len(total_records),
            agg_sec_scope,
        )
        up_t0 = time.perf_counter()
        upsert_basic_stats_v2(total_records, chunk_size=upsert_chunk)
        up_sec_scope = time.perf_counter() - up_t0
        cumulative_upsert_sec += up_sec_scope
        log.info("[%s] UPSERT 완료 %d행 (%.1fs)", label, len(total_records), up_sec_scope)
        total_upsert_rows += len(total_records)
        elapsed_scope = time.perf_counter() - scope_start
        if record_timing:
            sido_times.append(elapsed_scope)
        log.info(
            "[%s] 시도 커밋·메모리정리: sido=%s UPSERT=%d행 시도총소요=%.1fs",
            label,
            sido or "-",
            len(total_records),
            elapsed_scope,
        )
        del df_full
        gc.collect()
        gc.collect()

    if use_sido_chunking:
        sidos = distinct_sido_codes_in_period(p_start_min, period_end)
        if not sidos:
            log.error("해당 기간에 거래가 있는 시도가 없습니다.")
            log_empty_fetch_diagnostics_v2(None, p_start_min, period_end, sido_code=None)
            return
        log.info("전국 시도 청크: %d개 시도 %s", len(sidos), sidos)
        current_sido: str | None = None
        try:
            for i, sido in enumerate(tqdm(sidos, desc="sido_code", unit="시도")):
                current_sido = sido
                idx_lbl = f"{i + 1}/{len(sidos)}"
                t_start = datetime.now().astimezone()
                log.info(
                    "[시도 시작] %s/%s sido=%s 시각=%s",
                    i + 1,
                    len(sidos),
                    sido,
                    t_start.strftime("%Y-%m-%d %H:%M:%S"),
                )
                wall = time.perf_counter()
                try:
                    run_one_scope(sido, idx_lbl, record_timing=True)
                except Exception as exc:
                    log.exception(
                        "[배치 실패] 시도 코드=%s (진행 %s/%s). "
                        "이미 처리된 시도는 청크 단위로 커밋됨(UPSERT). 원인 확인 후 동일 명령 재실행.",
                        sido,
                        i + 1,
                        len(sidos),
                    )
                    raise SystemExit(1) from exc
                done = time.perf_counter() - wall
                t_end = datetime.now().astimezone()
                log.info(
                    "[시도 완료] %s/%s sido=%s 소요=%.1fs 종료시각=%s",
                    i + 1,
                    len(sidos),
                    sido,
                    done,
                    t_end.strftime("%Y-%m-%d %H:%M:%S"),
                )
                avg = sum(sido_times) / len(sido_times) if sido_times else 0.0
                remain = max(0, len(sidos) - i - 1)
                eta = avg * remain
                wall_total = time.perf_counter() - batch_started
                pct = 100.0 * (i + 1) / len(sidos)
                eta_end = datetime.now().astimezone() + timedelta(seconds=eta)
                log.info(
                    "[진행] %.1f%% (%s/%s) sido=%s 이번시도=%.1fs 예상잔여=%.1fs 예상종료~%s "
                    "경과=%.1f분 누적조회행=%s",
                    pct,
                    i + 1,
                    len(sidos),
                    sido,
                    done,
                    eta,
                    eta_end.strftime("%Y-%m-%d %H:%M:%S"),
                    wall_total / 60.0,
                    f"{total_rows_fetched:,}",
                )
        except KeyboardInterrupt:
            log.warning(
                "[KeyboardInterrupt] 수동 중단 - 마지막 시도=%s. "
                "완료된 시도는 DB에 반영됨. 재실행은 idempotent(ON CONFLICT).",
                current_sido,
            )
            raise SystemExit(130) from None
    else:
        try:
            run_one_scope(sido_filter, "1/1", record_timing=False)
        except KeyboardInterrupt:
            log.warning("[KeyboardInterrupt] 단일 스코프 중단 - 이미 커밋된 청크는 유지됨.")
            raise SystemExit(130) from None

    wall_total = time.perf_counter() - batch_started
    wall_end_dt = datetime.now().astimezone()
    v2_bytes_after = _pg_total_relation_size_bytes_whitelist("land_basic_stats_v2")
    v2_rows_after = _count_v2_batch_rows(as_of_month, windows)
    delta_mb = None
    if v2_bytes_before is not None and v2_bytes_after is not None:
        delta_mb = (v2_bytes_after - v2_bytes_before) / (1024 * 1024)
    delta_rows = None
    if v2_rows_before is not None and v2_rows_after is not None:
        delta_rows = v2_rows_after - v2_rows_before

    phased = cumulative_fetch_sec + cumulative_agg_sec + cumulative_upsert_sec
    log.info(
        "[build_stats_v2 timing] 누적 phase 합계: sql_fetch %.1fs (%.2f분) | "
        "python_aggregate %.1fs (%.2f분) | db_upsert %.1fs (%.2f분) | 상기합=%.1fs | batch_wall=%.1fs",
        cumulative_fetch_sec,
        cumulative_fetch_sec / 60.0,
        cumulative_agg_sec,
        cumulative_agg_sec / 60.0,
        cumulative_upsert_sec,
        cumulative_upsert_sec / 60.0,
        phased,
        wall_total,
    )
    log.info(
        "V2 사전 집계 완료 - wall 종료=%s 총 %.1f분, 누적조회행=%s, UPSERT시도행=%s",
        wall_end_dt.strftime("%Y-%m-%d %H:%M:%S"),
        wall_total / 60.0,
        f"{total_rows_fetched:,}",
        f"{total_upsert_rows:,}",
    )
    dr_msg = f"{delta_rows:+d}" if delta_rows is not None else "N/A"
    log.info(
        "DB land_basic_stats_v2: 행수=%s (이번 배치 대비 변화 %s), 총용량~%.2f MiB (용량증가~%s)",
        f"{v2_rows_after:,}" if v2_rows_after is not None else "N/A",
        dr_msg,
        (v2_bytes_after or 0) / (1024 * 1024),
        f"{delta_mb:+.2f} MiB" if delta_mb is not None else "N/A",
    )
    log.info(
        "재실행 검증: 동일 --as-of·--windows 로 재실행 시 행수·용량은 유지 또는 소폭 변동(데이터 동일 시), "
        "ON CONFLICT DO UPDATE 로 idempotent."
    )


if __name__ == "__main__":
    main()
