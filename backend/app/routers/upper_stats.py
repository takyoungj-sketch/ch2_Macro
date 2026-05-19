"""
상위 행정구역 사전집계 조회 — `land_upper_stats_v2` 단건 (유료).

설계: docs/UPPER_STATS_DESIGN.md (D-009)
선행: db/010_land_upper_stats_v2.sql + pipeline/build_upper_stats_v2.py 적재

응답 구조는 FreeStatsV2Response 와 같다:
- total (ALL/ALL)
- by_zone / by_land_category / matrix : land_upper_stats_v2 의 zone×cat 행
- by_year : land_transactions 의 region_level/code 별 contract_year 집계
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.population_query import attach_population_year_end
from app.schemas import (
    MatrixCell,
    RegionLevel,
    StatsResult,
    UpperStatsV2Response,
    YearlyTradeStat,
)
from app.v2_stats_windows import (
    default_as_of_month_for_service,
    period_bounds_for_window,
    stats_ui_reference_date,
)

router = APIRouter(prefix="/paid", tags=["상위 행정구역 통계 (유료)"])

_REGION_CODE_LEN: dict[RegionLevel, int] = {
    "sido": 2,
    "sigungu": 5,
    "eupmyeondong": 8,
}

_LEVEL_TX_COL: dict[RegionLevel, str] = {
    "sido": "sido_code",
    "sigungu": "sigungu_code",
    "eupmyeondong": "eupmyeondong_code",
}


def _ensure_upper_table(db: Session) -> None:
    reg = db.execute(
        text("SELECT to_regclass('public.land_upper_stats_v2')::text")
    ).scalar()
    if reg is None or str(reg).strip() == "":
        raise HTTPException(
            status_code=503,
            detail=(
                "land_upper_stats_v2 테이블이 없습니다. "
                "db/010_land_upper_stats_v2.sql 적용 후 다시 시도하세요."
            ),
        )


def _validate_code(level: RegionLevel, code: str) -> str:
    code = (code or "").strip()
    expected = _REGION_CODE_LEN[level]
    if not code.isdigit() or len(code) != expected:
        raise HTTPException(
            status_code=422,
            detail=f"region_code 는 {level} 레벨에서 {expected}자리 숫자여야 합니다.",
        )
    return code


def _region_name(db: Session, level: RegionLevel, code: str) -> str:
    """region_codes 에서 해당 레벨의 대표 이름을 가져온다."""
    if level == "sido":
        col_code, col_name = "sido_code", "sido_name"
    elif level == "sigungu":
        col_code, col_name = "sigungu_code", "sigungu_name"
    else:
        col_code, col_name = "eupmyeondong_code", "eupmyeondong_name"
    row = db.execute(
        text(
            f"""
            SELECT MAX({col_name}) AS name
            FROM region_codes
            WHERE btrim({col_code}::text) = :c
              AND COALESCE(is_active, TRUE)
            """
        ),
        {"c": code},
    ).fetchone()
    return str(row.name) if row and row.name else ""


def _row_to_stats(r) -> StatsResult:
    return StatsResult(
        count=int(r.count),
        mean=float(r.mean) if r.mean is not None else None,
        std=float(r.std) if r.std is not None else None,
        ci_lower=float(r.ci_lower) if r.ci_lower is not None else None,
        ci_upper=float(r.ci_upper) if r.ci_upper is not None else None,
        min=float(r.p_min) if r.p_min is not None else None,
        p25=float(r.p25) if r.p25 is not None else None,
        median=float(r.median) if r.median is not None else None,
        p75=float(r.p75) if r.p75 is not None else None,
        max=float(r.p_max) if r.p_max is not None else None,
        is_reliable=int(r.count) >= 15,
    )


def _resolve_as_of(explicit: Optional[date]) -> date:
    return (
        explicit
        or settings.stats_v2_default_as_of_month
        or default_as_of_month_for_service(settings.stats_v2_assumed_today)
    )


def _fetch_zone_cat_rows(
    db: Session,
    *,
    level: RegionLevel,
    code: str,
    as_of: date,
    window_years: int,
) -> list:
    return db.execute(
        text(
            """
            SELECT zone_type, land_category,
                   count, mean, std, ci_lower, ci_upper,
                   p_min, p25, median, p75, p_max
            FROM land_upper_stats_v2
            WHERE region_level = :level
              AND btrim(region_code::text) = :code
              AND as_of_month = :as_of
              AND window_years = :w
            """
        ),
        {"level": level, "code": code, "as_of": as_of, "w": window_years},
    ).fetchall()


def _by_year_upper(
    db: Session,
    *,
    level: RegionLevel,
    code: str,
    period_start: date,
    period_end: date,
) -> list[YearlyTradeStat]:
    """land_transactions 의 region_level/code 별 contract_year 총계."""
    col = _LEVEL_TX_COL[level]
    y0 = date(period_start.year, 1, 1)
    rows = db.execute(
        text(
            f"""
            SELECT contract_year::int AS y,
                   COUNT(*)::int AS cnt,
                   COALESCE(SUM(total_price_10k), 0) AS sum_price,
                   COALESCE(SUM(area_sqm), 0) AS sum_area
            FROM land_transactions
            WHERE btrim({col}::text) = :code
              AND is_valid IS TRUE
              AND contract_date IS NOT NULL
              AND contract_date >= :d0
              AND contract_date <= :d1
            GROUP BY contract_year
            ORDER BY contract_year
            """
        ),
        {"code": code, "d0": y0, "d1": period_end},
    ).fetchall()
    y_map = {int(r.y): r for r in rows}
    out: list[YearlyTradeStat] = []
    for y in range(int(period_start.year), int(period_end.year) + 1):
        r = y_map.get(y)
        if r:
            sp = float(r.sum_price)
            sa = float(r.sum_area)
            unit = (sp / sa) if sa > 0 else None
            out.append(
                YearlyTradeStat(
                    year=y,
                    count=int(r.cnt),
                    total_price_10k_sum=sp,
                    area_sqm_sum=sa,
                    unit_price_per_sqm=unit,
                )
            )
        else:
            out.append(YearlyTradeStat(year=y, count=0))
    # 인구 합산은 시·도/시·군·구/읍·면·동 모두 region 단위 합산이 의미 있어, 코드 단위 attach.
    # attach_population_year_end 는 region_codes 인자로 동·리 코드 리스트를 받지만,
    # 여기서는 상위 코드 1개를 그대로 넘겨 함수가 (없으면) 인구를 비워두는 것에 의존.
    return attach_population_year_end(db, region_codes=[code], items=out)


@router.get(
    "/upper-stats/{level}/{code}",
    response_model=UpperStatsV2Response,
    summary="상위 행정구역 단건 사전집계 조회 (matrix·by_year 포함)",
)
def get_upper_stats(
    level: RegionLevel,
    code: str,
    window_years: int = Query(5, ge=1, le=5),
    as_of_month: Optional[date] = Query(None),
    db: Session = Depends(get_db),
) -> UpperStatsV2Response:
    _ensure_upper_table(db)
    code = _validate_code(level, code)
    if as_of_month is not None and as_of_month.day != 1:
        raise HTTPException(
            status_code=422,
            detail="as_of_month 는 YYYY-MM-01 형태여야 합니다.",
        )
    as_of = _resolve_as_of(as_of_month)
    period_start, period_end = period_bounds_for_window(as_of, window_years)

    rows = _fetch_zone_cat_rows(
        db, level=level, code=code, as_of=as_of, window_years=window_years
    )
    if not rows:
        raise HTTPException(
            status_code=404,
            detail=(
                f"해당 상위지역 사전집계 없음: level={level} code={code} "
                f"as_of_month={as_of} window_years={window_years}. "
                "build_upper_stats_v2.py 적재 여부를 확인하세요."
            ),
        )

    total: Optional[StatsResult] = None
    by_zone: dict[str, StatsResult] = {}
    by_land_category: dict[str, StatsResult] = {}
    matrix: list[MatrixCell] = []
    for r in rows:
        zt = (r.zone_type or "ALL").strip() or "ALL"
        lc = (r.land_category or "ALL").strip() or "ALL"
        stats = _row_to_stats(r)
        if zt == "ALL" and lc == "ALL":
            total = stats
        elif zt != "ALL" and lc == "ALL":
            by_zone[zt] = stats
        elif zt == "ALL" and lc != "ALL":
            by_land_category[lc] = stats
        else:
            matrix.append(MatrixCell(zone_type=zt, land_category=lc, stats=stats))

    if total is None:
        # ALL/ALL 행이 없으면 가장 기본은 비어 있는 응답 — 404로 일관 처리
        raise HTTPException(
            status_code=404,
            detail="ALL/ALL 사전집계 행을 찾지 못했습니다(adapter/build 점검 필요).",
        )

    by_year = _by_year_upper(
        db,
        level=level,
        code=code,
        period_start=period_start,
        period_end=period_end,
    )

    return UpperStatsV2Response(
        region_level=level,
        region_code=code,
        region_name=_region_name(db, level, code),
        as_of_month=as_of,
        stats_reference_date=stats_ui_reference_date(as_of),
        period_start=period_start,
        period_end=period_end,
        window_years=window_years,
        total=total,
        by_year=by_year,
        by_zone=by_zone,
        by_land_category=by_land_category,
        matrix=matrix,
    )
