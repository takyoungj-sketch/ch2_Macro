"""
무료 통계 V2 API — land_basic_stats_v2 + contract_date 롤링 구간.

- 단건: 사전집계 테이블 조회(빠름) + 연도별 표는 원장 1회 GROUP BY(window·calendar FILTER 동시)
- 벌크: v1 bulk 와 같이 복수 지역 원장을 동일 period 로 합쳐 매트릭스 계산

핫패스 지역 조건: docs/LAND_LEDGER_QUERY_PERF.md
(`beopjungri_code = ANY` 금지 · window/calendar 이중 GROUP BY 금지)

선행: db/007_land_basic_stats_v2.sql + pipeline/build_stats_v2.py 적재
"""

from __future__ import annotations

from datetime import date
from itertools import product
from typing import Annotated, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.jimok_group import display_land_key, matrix_mode_to_col_axis
from app.ledger_region_sql import beopjungri_eq_or_in, execute_expanding
from app.population_query import attach_population_year_end
from app.region_canonical import expand_to_ledger_codes, resolve_to_canonical
from app.routers.free import (
    _MAX_STATS_REGIONS,
    _build_region_title,
    _dedupe_codes_preserve,
    _stats_dict_to_result,
)
from app.schemas import (
    FreeStatsV2BulkRequest,
    FreeStatsV2MetaAsOfResponse,
    FreeStatsV2Response,
    MatrixCell,
    RegionItem,
    StatsResult,
    YearlyTradeStat,
)
from app.stats_utils import compute_stats
from app.v2_stats_windows import (
    UI_WINDOW_YEARS,
    default_as_of_month_for_service,
    period_bounds_for_window,
    stats_ui_reference_date,
)

router = APIRouter(prefix="/free/v2", tags=["무료 통계 V2"])


def _parse_v2_window_years_query(
    window_years: Annotated[
        int | str | list[str] | None,
        Query(
            description=(
                "롤링 창: 3·5·7. 생략 시 5. 빈 값·null 문자열·undefined 는 5로 처리."
            ),
        ),
    ] = 5,
) -> Literal[3, 5, 7]:
    """쿼리스트링에서 `window_years=` 처럼 빈 값이 올 때 Literal 422를 피한다."""
    allowed = set(UI_WINDOW_YEARS)

    def _ok(n: int) -> Literal[3, 5, 7]:
        if n not in allowed:
            raise HTTPException(
                status_code=422,
                detail=f"window_years 는 {sorted(allowed)} 만 허용됩니다.",
            )
        return n  # type: ignore[return-value]

    if window_years is None:
        return 5
    if isinstance(window_years, int):
        return _ok(window_years)
    if isinstance(window_years, list):
        window_years = window_years[0] if window_years else None
        if window_years is None:
            return 5
    s = str(window_years).strip()
    if s == "" or s.lower() in ("null", "undefined"):
        return 5
    try:
        return _ok(int(s))
    except ValueError:
        pass
    raise HTTPException(
        status_code=422,
        detail=f"window_years 는 {sorted(allowed)} 만 허용됩니다.",
    )


def _ensure_v2_table(db: Session) -> None:
    reg = db.execute(
        text("SELECT to_regclass('public.land_basic_stats_v2')::text")
    ).scalar()
    if reg is None or str(reg).strip() == "":
        raise HTTPException(
            status_code=503,
            detail="land_basic_stats_v2 테이블이 없습니다. db/007_land_basic_stats_v2.sql 적용 후 다시 시도하세요.",
        )


def _row_to_stats_v2(r) -> StatsResult:
    return StatsResult(
        count=int(r.count),
        mean=float(r.mean) if r.mean is not None else None,
        std=float(r.std) if getattr(r, "std", None) is not None else None,
        ci_lower=float(r.ci_lower) if r.ci_lower is not None else None,
        ci_upper=float(r.ci_upper) if r.ci_upper is not None else None,
        min=float(r.p_min) if r.p_min is not None else None,
        p25=float(r.p25) if r.p25 is not None else None,
        median=float(r.median) if r.median is not None else None,
        p75=float(r.p75) if r.p75 is not None else None,
        max=float(r.p_max) if r.p_max is not None else None,
        is_reliable=int(r.count) >= 15,
    )


def _resolve_as_of_month_single(
    db: Session,
    *,
    code_trim: str,
    window_years: int,
    explicit: Optional[date],
    col_axis: str = "category",
) -> date:
    eff = (
        explicit
        if explicit is not None
        else (
            settings.stats_v2_default_as_of_month
            or default_as_of_month_for_service(settings.stats_v2_assumed_today)
        )
    )
    row = db.execute(
        text(
            """
            SELECT 1 FROM land_basic_stats_v2
            WHERE beopjungri_code = :c
              AND as_of_month = :as_of
              AND window_years = :w
              AND col_axis = :axis
              AND zone_type = 'ALL' AND land_category = 'ALL'
            LIMIT 1
            """
        ),
        {"c": code_trim, "as_of": eff, "w": window_years, "axis": col_axis},
    ).fetchone()
    if not row:
        raise HTTPException(
            status_code=404,
            detail=(
                f"해당 지역에 as_of_month={eff}, window_years={window_years}, "
                f"matrix_mode={col_axis} 인 V2 집계가 없습니다."
            ),
        )
    return eff


def _split_codes_with_basic_stats_v2(
    db: Session,
    codes: list[str],
    as_of: date,
    window_years: int,
    *,
    col_axis: str = "category",
) -> tuple[list[str], list[str]]:
    if not codes:
        return [], []
    stmt = text(
        """
        SELECT btrim(beopjungri_code::text) AS bc
        FROM land_basic_stats_v2
        WHERE beopjungri_code = ANY(:codes)
          AND as_of_month = :as_of
          AND window_years = :w
          AND col_axis = :axis
          AND zone_type = 'ALL' AND land_category = 'ALL'
        """
    )
    rows = db.execute(
        stmt, {"codes": codes, "as_of": as_of, "w": window_years, "axis": col_axis}
    ).fetchall()
    seen = {str(r.bc).strip() for r in rows}
    kept: list[str] = []
    missing: list[str] = []
    dedupe: set[str] = set()
    for c in codes:
        cc = str(c).strip()
        if not cc or cc in dedupe:
            continue
        dedupe.add(cc)
        if cc in seen:
            kept.append(cc)
        else:
            missing.append(cc)
    return kept, missing


def _resolve_as_of_month_bulk(*, explicit: Optional[date]) -> date:
    if explicit is not None:
        return explicit
    return settings.stats_v2_default_as_of_month or default_as_of_month_for_service(
        settings.stats_v2_assumed_today
    )


def _relabel_land_axis(
    by_land_category: dict[str, StatsResult],
    matrix: list[MatrixCell],
    *,
    matrix_mode: str,
) -> tuple[dict[str, StatsResult], list[MatrixCell]]:
    if matrix_mode_to_col_axis(matrix_mode) != "group":
        return by_land_category, matrix
    by_land = {
        display_land_key(k, matrix_mode=matrix_mode): v
        for k, v in by_land_category.items()
    }
    mtx = [
        MatrixCell(
            zone_type=c.zone_type,
            land_category=display_land_key(c.land_category, matrix_mode=matrix_mode),
            stats=c.stats,
        )
        for c in matrix
    ]
    return by_land, mtx


def _ledger_codes(db: Session, codes: list[str]) -> list[str]:
    """Master 조회용: canonical(+입력) → historical from_code 포함 확장."""
    expanded = expand_to_ledger_codes(db, codes)
    return expanded or list(codes)


def _combined_bundle_v2_from_transactions(
    db: Session,
    codes: list[str],
    period_start: date,
    period_end: date,
    *,
    matrix_mode: str = "category",
) -> tuple[StatsResult, dict[str, StatsResult], dict[str, StatsResult], list[MatrixCell]]:
    land_expr = (
        "COALESCE(jimok_group_code, 'other')"
        if matrix_mode_to_col_axis(matrix_mode) == "group"
        else "land_category_resolved"
    )
    ledger = _ledger_codes(db, codes)
    if not ledger:
        raise HTTPException(
            status_code=404,
            detail="선택 기간·지역에 합산 가능한 거래 단가 데이터가 없습니다.",
        )
    region_pred, region_params = beopjungri_eq_or_in(
        ledger,
        column="beopjungri_code",
        eq_key="region_code",
        in_key="codes",
        expand_flag="_expand_codes",
    )
    sql = f"""
        SELECT zone_type_resolved AS zone_type,
               {land_expr} AS land_category,
               unit_price_per_sqm::double precision AS up
        FROM land_transactions_resolved
        WHERE is_valid = TRUE
          AND is_cancelled = FALSE
          AND unit_price_per_sqm IS NOT NULL
          AND contract_date IS NOT NULL
          AND contract_date >= :ps
          AND contract_date <= :pe
          AND {region_pred}
        """
    raw = execute_expanding(
        db,
        sql,
        {"ps": period_start, "pe": period_end, **region_params},
    ).fetchall()
    trips: list[tuple[str, str, float]] = []
    for r in raw:
        zt = (r.zone_type or "").strip() or "UNKNOWN"
        lc = (r.land_category or "").strip() or "UNKNOWN"
        try:
            p = float(r.up)
        except (TypeError, ValueError):
            continue
        if p == p:
            trips.append((zt, lc, p))

    if not trips:
        raise HTTPException(
            status_code=404,
            detail="선택 기간·지역에 합산 가능한 거래 단가 데이터가 없습니다.",
        )

    zones = sorted({t[0] for t in trips})
    cats_sorted = sorted({t[1] for t in trips})

    def prices_for(zone: str, cat: str) -> list[float]:
        return [
            p
            for zt, lc, p in trips
            if (zone == "ALL" or zt == zone) and (cat == "ALL" or lc == cat)
        ]

    total_d = compute_stats(prices_for("ALL", "ALL"))
    total = _stats_dict_to_result(total_d)

    by_zone: dict[str, StatsResult] = {}
    for zone in zones:
        d = compute_stats(prices_for(zone, "ALL"))
        by_zone[zone] = _stats_dict_to_result(d)

    by_land_category: dict[str, StatsResult] = {}
    for lc in cats_sorted:
        d = compute_stats(prices_for("ALL", lc))
        by_land_category[lc] = _stats_dict_to_result(d)

    matrix_list: list[MatrixCell] = []
    for zone, cat in product(zones, cats_sorted):
        st = compute_stats(prices_for(zone, cat))
        matrix_list.append(
            MatrixCell(zone_type=zone, land_category=cat, stats=_stats_dict_to_result(st))
        )

    by_land_category, matrix_list = _relabel_land_axis(
        by_land_category, matrix_list, matrix_mode=matrix_mode
    )
    return total, by_zone, by_land_category, matrix_list


def _yearly_totals_contract_bounds(period_start: date, period_end: date) -> tuple[date, date]:
    """
    상단 연도별 총계표용 contract_date 조회 하한·상한.

    매트릭스(롤링)와 다름: 첫 연도는 period_start.year의 1/1부터, 그 해·중간 연도는
    각 달력 연도 전체(해당 연 12/31까지), 마지막 연도는 period_end(스냅샷 말일)까지
    포함되도록 [period_start.year의 1/1, period_end]로 넓힌 뒤 contract_year 로 집계.
    """
    return date(period_start.year, 1, 1), period_end


def _year_map_to_stats(
    y_map: dict[int, tuple[int, float, float]],
    year_from: int,
    year_to: int,
) -> list[YearlyTradeStat]:
    """y_map[y] = (count, sum_price_10k, sum_area_sqm)."""
    out: list[YearlyTradeStat] = []
    for y in range(year_from, year_to + 1):
        row = y_map.get(y)
        if row and int(row[0] or 0) > 0:
            cnt, sp, sa = int(row[0]), float(row[1]), float(row[2])
            unit = (sp / sa) if sa > 0 else None
            out.append(
                YearlyTradeStat(
                    year=y,
                    count=cnt,
                    total_price_10k_sum=sp,
                    area_sqm_sum=sa,
                    unit_price_per_sqm=unit,
                )
            )
        else:
            out.append(YearlyTradeStat(year=y, count=0))
    return out


def _fetch_yearly_tx_dual_maps(
    db: Session,
    codes: list[str],
    period_start: date,
    period_end: date,
) -> tuple[dict[int, tuple[int, float, float]], dict[int, tuple[int, float, float]]]:
    """원장 1회 스캔으로 window(period_end 컷) · calendar(연도 전체) 집계.

    이전에는 동일 구간을 두 번 GROUP BY 해 단건 통계가 ~20초까지 늘었다.
    지역 조건은 ``ledger_region_sql.beopjungri_eq_or_in`` (ANY 금지).
    """
    ledger = _ledger_codes(db, codes)
    if not ledger:
        return {}, {}
    y0, y1 = int(period_start.year), int(period_end.year)
    region_pred, region_params = beopjungri_eq_or_in(
        ledger,
        column="beopjungri_code",
        eq_key="region_code",
        in_key="codes",
        expand_flag="_expand_codes",
    )
    select_sql = f"""
            SELECT contract_year::int AS y,
                   COUNT(*) FILTER (
                       WHERE contract_date <= :period_end
                   )::int AS cnt_window,
                   COALESCE(
                       SUM(total_price_10k) FILTER (WHERE contract_date <= :period_end),
                       0
                   ) AS sum_price_window,
                   COALESCE(
                       SUM(area_sqm) FILTER (WHERE contract_date <= :period_end),
                       0
                   ) AS sum_area_window,
                   COUNT(*)::int AS cnt_calendar,
                   COALESCE(SUM(total_price_10k), 0) AS sum_price_calendar,
                   COALESCE(SUM(area_sqm), 0) AS sum_area_calendar
            FROM land_transactions
            WHERE {region_pred}
              AND is_valid IS TRUE
              AND contract_date IS NOT NULL
              AND contract_year >= :y0
              AND contract_year <= :y1
            GROUP BY contract_year
            ORDER BY contract_year
    """
    params: dict = {
        "period_end": period_end,
        "y0": y0,
        "y1": y1,
        **region_params,
    }
    rows = execute_expanding(db, select_sql, params).fetchall()
    window_map: dict[int, tuple[int, float, float]] = {}
    calendar_map: dict[int, tuple[int, float, float]] = {}
    for r in rows:
        y = int(r.y)
        window_map[y] = (
            int(r.cnt_window or 0),
            float(r.sum_price_window or 0),
            float(r.sum_area_window or 0),
        )
        calendar_map[y] = (
            int(r.cnt_calendar or 0),
            float(r.sum_price_calendar or 0),
            float(r.sum_area_calendar or 0),
        )
    return window_map, calendar_map


def _by_year_pair(
    db: Session,
    codes: list[str],
    period_start: date,
    period_end: date,
) -> tuple[list[YearlyTradeStat], list[YearlyTradeStat]]:
    """단건·벌크 공통 — by_year(window) + by_year_calendar_reference."""
    y0, y1 = int(period_start.year), int(period_end.year)
    window_map, calendar_map = _fetch_yearly_tx_dual_maps(
        db, codes, period_start, period_end
    )
    by_year = _year_map_to_stats(window_map, y0, y1)
    by_cal = _year_map_to_stats(calendar_map, y0, y1)
    by_year = attach_population_year_end(db, region_codes=codes, items=by_year)
    by_cal = attach_population_year_end(db, region_codes=codes, items=by_cal)
    return by_year, by_cal


def _by_year_contract_date(
    db: Session,
    code_trim: str,
    period_start: date,
    period_end: date,
) -> list[YearlyTradeStat]:
    """단건 API 연도별 총계 표 — is_valid 만 필터(해제 미필터)."""
    by_year, _ = _by_year_pair(db, [code_trim], period_start, period_end)
    return by_year


def _by_year_bulk_contract_date(
    db: Session,
    codes: list[str],
    period_start: date,
    period_end: date,
) -> list[YearlyTradeStat]:
    by_year, _ = _by_year_pair(db, codes, period_start, period_end)
    return by_year


def _by_year_calendar_reference_single(
    db: Session,
    code_trim: str,
    *,
    period_start: date,
    period_end: date,
) -> list[YearlyTradeStat]:
    """참고 표: 각 달력연도별 contract_date 그 연도만 1·1~12·31."""
    _, by_cal = _by_year_pair(db, [code_trim], period_start, period_end)
    return by_cal


def _by_year_calendar_reference_bulk(
    db: Session,
    codes: list[str],
    *,
    period_start: date,
    period_end: date,
) -> list[YearlyTradeStat]:
    _, by_cal = _by_year_pair(db, codes, period_start, period_end)
    return by_cal


@router.get(
    "/meta/as-of",
    response_model=FreeStatsV2MetaAsOfResponse,
    summary="V2 적재된 최신 기준월·창 목록",
)
def get_v2_meta_as_of(db: Session = Depends(get_db)):
    _ensure_v2_table(db)
    max_row = db.execute(
        text("SELECT MAX(as_of_month) AS am FROM land_basic_stats_v2")
    ).fetchone()
    max_as = max_row.am if max_row else None
    windows: list[int] = []
    if max_as is not None:
        wrows = db.execute(
            text(
                """
                SELECT DISTINCT window_years::int AS w
                FROM land_basic_stats_v2
                WHERE as_of_month = :am
                ORDER BY 1
                """
            ),
            {"am": max_as},
        ).fetchall()
        windows = [int(r.w) for r in wrows]
    return FreeStatsV2MetaAsOfResponse(
        max_as_of_month=max_as, window_years_present=windows
    )


@router.get(
    "/stats/{beopjungri_code}",
    response_model=FreeStatsV2Response,
    summary="법정동/리 기본 통계 (V2 사전집계)",
)
def get_basic_stats_v2(
    beopjungri_code: str,
    db: Session = Depends(get_db),
    window_years: Literal[3, 5, 7] = Depends(_parse_v2_window_years_query),
    as_of_month: Optional[date] = Query(
        None,
        description=(
            "기준월(YYYY-MM-01). 생략 시 STATS_V2_DEFAULT_AS_OF_MONTH(있으면) "
            "또는 STATS_V2_ASSUMED_TODAY 기준 직전 달 1일, 둘 다 없으면 실제 오늘 기준(§3)."
        ),
    ),
    matrix_mode: Literal["category", "group"] = Query(
        "category",
        description="category=용도×지목(기본), group=용도×지목군",
    ),
):
    _ensure_v2_table(db)
    if as_of_month is not None and as_of_month.day != 1:
        raise HTTPException(
            status_code=422,
            detail="as_of_month 는 해당 월 1일(YYYY-MM-01)이어야 합니다.",
        )

    # D-028: GIS/UI 코드 → canonical (원장 코드는 변경하지 않음)
    code_trim = resolve_to_canonical(
        db, _dedupe_codes_preserve([beopjungri_code])
    )[0]

    region = db.execute(
        text("SELECT * FROM region_codes WHERE beopjungri_code = :code"),
        {"code": code_trim},
    ).fetchone()
    if not region:
        raise HTTPException(status_code=404, detail="지역 코드를 찾을 수 없습니다.")

    col_axis = matrix_mode_to_col_axis(matrix_mode)
    as_of = _resolve_as_of_month_single(
        db,
        code_trim=code_trim,
        window_years=window_years,
        explicit=as_of_month,
        col_axis=col_axis,
    )
    ps, pe = period_bounds_for_window(as_of, window_years)

    rows = db.execute(
        text(
            """
            SELECT zone_type, land_category,
                   count, mean, std, ci_lower, ci_upper,
                   p_min, p25, median, p75, p_max,
                   period_start, period_end
            FROM land_basic_stats_v2
            WHERE beopjungri_code = :code
              AND as_of_month = :as_of
              AND window_years = :w
              AND col_axis = :axis
            ORDER BY zone_type, land_category
            """
        ),
        {"code": code_trim, "as_of": as_of, "w": window_years, "axis": col_axis},
    ).fetchall()

    if not rows:
        raise HTTPException(status_code=404, detail="해당 조건의 V2 통계 행이 없습니다.")

    total_row = next(
        (r for r in rows if r.zone_type == "ALL" and r.land_category == "ALL"), None
    )
    if total_row is None:
        raise HTTPException(
            status_code=404, detail="V2 ALL×ALL 통계 행이 없습니다."
        )

    total = _row_to_stats_v2(total_row)

    by_zone = {
        r.zone_type: _row_to_stats_v2(r)
        for r in rows
        if r.zone_type != "ALL" and r.land_category == "ALL"
    }
    by_land_category = {
        r.land_category: _row_to_stats_v2(r)
        for r in rows
        if r.zone_type == "ALL" and r.land_category != "ALL"
    }
    matrix = [
        MatrixCell(
            zone_type=r.zone_type,
            land_category=r.land_category,
            stats=_row_to_stats_v2(r),
        )
        for r in rows
        if r.zone_type != "ALL" and r.land_category != "ALL"
    ]
    by_land_category, matrix = _relabel_land_axis(
        by_land_category, matrix, matrix_mode=matrix_mode
    )

    by_year, by_year_calendar_reference = _by_year_pair(db, [code_trim], ps, pe)

    return FreeStatsV2Response(
        beopjungri_code=code_trim,
        beopjungri_name=str(region.beopjungri_name),
        as_of_month=as_of,
        stats_reference_date=stats_ui_reference_date(as_of),
        period_start=ps,
        period_end=pe,
        window_years=window_years,
        total=total,
        by_year=by_year,
        by_year_calendar_reference=by_year_calendar_reference,
        by_zone=by_zone,
        by_land_category=by_land_category,
        matrix=matrix,
        matrix_mode=matrix_mode,
        stats_excluded_codes=[],
        analysis_base_key=None,
    )


@router.post(
    "/stats/bulk",
    response_model=FreeStatsV2Response,
    summary="복수 법정동·리 V2 합산 (원장 동일 period 재집계)",
)
def get_basic_stats_v2_bulk(
    payload: FreeStatsV2BulkRequest, db: Session = Depends(get_db)
):
    _ensure_v2_table(db)
    codes = resolve_to_canonical(db, _dedupe_codes_preserve(payload.region_codes))
    if not codes:
        raise HTTPException(status_code=422, detail="유효한 지역 코드가 없습니다.")
    if len(codes) > _MAX_STATS_REGIONS:
        raise HTTPException(
            status_code=422,
            detail=f"한 번에 합산할 수 있는 최대 개수({_MAX_STATS_REGIONS})를 초과했습니다.",
        )

    if payload.as_of_month is not None and payload.as_of_month.day != 1:
        raise HTTPException(
            status_code=422,
            detail="as_of_month 는 해당 월 1일(YYYY-MM-01)이어야 합니다.",
        )

    as_of = _resolve_as_of_month_bulk(explicit=payload.as_of_month)
    # 지역 커버리지는 category grain 기준으로 판정(group mart 미적재 시도도 bulk 원장 재집계 가능)
    kept, stats_excluded_codes = _split_codes_with_basic_stats_v2(
        db, codes, as_of, payload.window_years, col_axis="category"
    )
    if not kept:
        preview = ", ".join(stats_excluded_codes[:15])
        tail = " …" if len(stats_excluded_codes) > 15 else ""
        raise HTTPException(
            status_code=404,
            detail="합산에 쓸 V2 사전집계(ALL×ALL)가 있는 코드가 없습니다."
            + (f" (제외: {preview}{tail})" if stats_excluded_codes else ""),
        )

    ps, pe = period_bounds_for_window(as_of, payload.window_years)

    title = _build_region_title(db, kept)
    total, by_zone, by_land_category, matrix = _combined_bundle_v2_from_transactions(
        db, kept, ps, pe, matrix_mode=payload.matrix_mode
    )
    by_year, by_year_calendar_reference = _by_year_pair(db, kept, ps, pe)

    return FreeStatsV2Response(
        beopjungri_code=",".join(kept),
        beopjungri_name=title,
        as_of_month=as_of,
        stats_reference_date=stats_ui_reference_date(as_of),
        period_start=ps,
        period_end=pe,
        window_years=payload.window_years,
        total=total,
        by_year=by_year,
        by_year_calendar_reference=by_year_calendar_reference,
        by_zone=by_zone,
        by_land_category=by_land_category,
        matrix=matrix,
        matrix_mode=payload.matrix_mode,
        stats_excluded_codes=stats_excluded_codes,
        analysis_base_key=None,
    )


# ---------------------------------------------------------------------------
# 지역 카탈로그 — 기존 /free/regions 와 동일 구현. V1 라우터 폐기 후 이 경로가 정식.
# ---------------------------------------------------------------------------
_REGIONS_SEARCH_MAX = 420
_REGIONS_HARD_MAX = 50_000
_REGIONS_DEFAULT_CAP = 500


@router.get("/regions", response_model=list[RegionItem], summary="지역 목록 조회")
def list_regions_v2(
    sigungu_code: str | None = None,
    eupmyeondong_code: str | None = None,
    beopjungri_code: str | None = None,
    search: str | None = Query(
        None,
        description="이름 또는 코드 부분 검색(ILIKE·동명이명 시 상위 행정구역명 포함으로 구분 가능)",
        max_length=64,
    ),
    limit: int = Query(
        _REGIONS_DEFAULT_CAP,
        ge=1,
        le=_REGIONS_HARD_MAX,
        description="결과 행 최대 개수(search 시 서버에서 추가로 묶임)",
    ),
    db: Session = Depends(get_db),
):
    """
    지역 코드 계층 조회. 시군구/읍면동/리 코드로 하위 항목 필터링 가능.
    검색 문자열은 2자 이상 권장(짧으면 과다 매칭·빈 결과).
    """
    where_parts = ["COALESCE(rc.is_active, TRUE) = TRUE"]
    params: dict = {}
    base_alias = (
        "(SELECT *, btrim(cast(beopjungri_code AS text)) AS bc_trim FROM region_codes) rc"
    )
    if sigungu_code:
        where_parts.append("rc.sigungu_code = :sigungu_code")
        params["sigungu_code"] = sigungu_code
    if eupmyeondong_code:
        where_parts.append("rc.eupmyeondong_code = :eupmyeondong_code")
        params["eupmyeondong_code"] = eupmyeondong_code
    if beopjungri_code:
        where_parts.append("rc.bc_trim = :beopjungri_code")
        params["beopjungri_code"] = beopjungri_code.strip()

    q_raw = (search or "").strip()
    if q_raw:
        params["region_search_pat"] = f"%{q_raw}%"
        where_parts.append(
            "("
            "COALESCE(rc.sido_name,'') ILIKE :region_search_pat "
            "OR COALESCE(rc.sigungu_name,'') ILIKE :region_search_pat "
            "OR COALESCE(rc.eupmyeondong_name,'') ILIKE :region_search_pat "
            "OR COALESCE(rc.beopjungri_name,'') ILIKE :region_search_pat "
            "OR rc.bc_trim ILIKE :region_search_pat"
            ")"
        )
        effective_limit = min(limit, _REGIONS_SEARCH_MAX)
    else:
        effective_limit = min(limit, _REGIONS_HARD_MAX)

    where_sql = " AND ".join(where_parts)
    rows = db.execute(
        text(
            f"""
            SELECT rc.beopjungri_code, rc.beopjungri_name,
                   rc.eupmyeondong_code, rc.eupmyeondong_name,
                   rc.sigungu_code, rc.sigungu_name,
                   rc.sido_code, rc.sido_name
            FROM {base_alias}
            WHERE {where_sql}
            ORDER BY rc.beopjungri_code
            LIMIT :region_limit
            """
        ),
        {**params, "region_limit": effective_limit},
    ).fetchall()
    return [RegionItem(**dict(r._mapping)) for r in rows]
