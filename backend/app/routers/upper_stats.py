"""
상위 행정구역 사전집계 조회 — `land_upper_stats_v2` 단건 (유료).

설계: docs/UPPER_STATS_DESIGN.md
선행: db/010_land_upper_stats_v2.sql + pipeline/build_upper_stats_v2.py 적재
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.schemas import RegionLevel, StatsResult, UpperStatsV2Response
from app.v2_stats_windows import (
    default_as_of_month_for_service,
    period_bounds_for_window,
    stats_ui_reference_date,
)

router = APIRouter(prefix="/paid", tags=["상위 행정구역 통계 (유료)"])

_REGION_CODE_LEN: dict[str, int] = {
    "sido": 2,
    "sigungu": 5,
    "eupmyeondong": 8,
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


@router.get(
    "/upper-stats/{level}/{code}",
    response_model=UpperStatsV2Response,
    summary="상위 행정구역 단건 사전집계 조회",
)
def get_upper_stats(
    level: RegionLevel,
    code: str,
    window_years: int = Query(5, ge=1, le=5),
    zone_type: str = Query("ALL"),
    land_category: str = Query("ALL"),
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

    row = db.execute(
        text(
            """
            SELECT count, mean, std, ci_lower, ci_upper,
                   p_min, p25, median, p75, p_max
            FROM land_upper_stats_v2
            WHERE region_level = :level
              AND btrim(region_code::text) = :code
              AND as_of_month = :as_of
              AND window_years = :w
              AND zone_type = :z
              AND land_category = :c
            LIMIT 1
            """
        ),
        {
            "level": level,
            "code": code,
            "as_of": as_of,
            "w": window_years,
            "z": zone_type,
            "c": land_category,
        },
    ).fetchone()
    if not row:
        raise HTTPException(
            status_code=404,
            detail=(
                f"해당 상위지역 사전집계 없음: level={level} code={code} "
                f"as_of_month={as_of} window_years={window_years} "
                f"zone_type={zone_type} land_category={land_category}. "
                "build_upper_stats_v2.py 적재 여부를 확인하세요."
            ),
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
        zone_type=zone_type,
        land_category=land_category,
        stats=_row_to_stats(row),
    )
