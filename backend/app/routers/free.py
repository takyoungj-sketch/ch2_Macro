"""
무료 통계 API 라우터
- 사전 집계: land_basic_stats (매트릭스·부분합)
- 연도별 요약: land_transactions 집계 (정상 거래만)
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas import (
    FreeStatsResponse,
    MatrixCell,
    RegionItem,
    StatsResult,
    YearlyTradeStat,
)

router = APIRouter(prefix="/free", tags=["무료 통계"])


@router.get("/regions", response_model=list[RegionItem], summary="지역 목록 조회")
def list_regions(
    sigungu_code: str | None = None,
    eupmyeondong_code: str | None = None,
    db: Session = Depends(get_db),
):
    """지역 코드 계층 조회. 시군구/읍면동 코드로 하위 항목 필터링 가능."""
    where = "WHERE is_active = TRUE"
    params: dict = {}
    if sigungu_code:
        where += " AND sigungu_code = :sigungu_code"
        params["sigungu_code"] = sigungu_code
    if eupmyeondong_code:
        where += " AND eupmyeondong_code = :eupmyeondong_code"
        params["eupmyeondong_code"] = eupmyeondong_code

    rows = db.execute(
        text(f"SELECT * FROM region_codes {where} ORDER BY beopjungri_code LIMIT 500"),
        params,
    ).fetchall()
    return [RegionItem(**dict(r._mapping)) for r in rows]


@router.get("/stats/{beopjungri_code}", response_model=FreeStatsResponse, summary="동/리 기본 통계")
def get_basic_stats(beopjungri_code: str, db: Session = Depends(get_db)):
    """
    법정동/리 코드 기준 기본 통계 조회 (최근 5년, 정상 데이터).
    사전 집계 테이블을 사용하므로 응답이 빠릅니다.
    """
    # 지역명 조회
    region = db.execute(
        text("SELECT * FROM region_codes WHERE beopjungri_code = :code"),
        {"code": beopjungri_code},
    ).fetchone()
    if not region:
        raise HTTPException(status_code=404, detail="지역 코드를 찾을 수 없습니다.")

    has_std = db.execute(
        text("""
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'land_basic_stats'
                  AND column_name = 'std'
            )
        """)
    ).scalar()
    std_select = "std," if has_std else "NULL AS std,"

    # 사전 집계 조회
    rows = db.execute(
        text(f"""
            SELECT zone_type, land_category,
                   count, mean, {std_select} ci_lower, ci_upper,
                   p_min, p25, median, p75, p_max,
                   year_from, year_to
            FROM land_basic_stats
            WHERE beopjungri_code = :code
            ORDER BY zone_type, land_category
        """),
        {"code": beopjungri_code},
    ).fetchall()

    if not rows:
        raise HTTPException(status_code=404, detail="해당 지역의 통계 데이터가 없습니다.")

    # ALL × ALL = 전체 통계
    total_row = next((r for r in rows if r.zone_type == "ALL" and r.land_category == "ALL"), None)
    year_from = rows[0].year_from
    year_to = rows[0].year_to

    def row_to_stats(r) -> StatsResult:
        return StatsResult(
            count=r.count,
            mean=float(r.mean) if r.mean is not None else None,
            std=float(r.std) if r.std is not None else None,
            ci_lower=float(r.ci_lower) if r.ci_lower is not None else None,
            ci_upper=float(r.ci_upper) if r.ci_upper is not None else None,
            min=float(r.p_min) if r.p_min is not None else None,
            p25=float(r.p25) if r.p25 is not None else None,
            median=float(r.median) if r.median is not None else None,
            p75=float(r.p75) if r.p75 is not None else None,
            max=float(r.p_max) if r.p_max is not None else None,
            is_reliable=r.count >= 15,
        )

    total = row_to_stats(total_row) if total_row else StatsResult(count=0)

    # 연도별 실거래 요약 (기간 내 모든 연도 행 포함, 건수 0 허용)
    y_rows = db.execute(
        text("""
            SELECT contract_year::int AS y,
                   COUNT(*)::int AS cnt,
                   COALESCE(SUM(total_price_10k), 0) AS sum_price,
                   COALESCE(SUM(area_sqm), 0) AS sum_area
            FROM land_transactions
            WHERE beopjungri_code = :code
              AND is_valid IS TRUE
              AND contract_year >= :yf
              AND contract_year <= :yt
            GROUP BY contract_year
            ORDER BY contract_year
        """),
        {"code": beopjungri_code, "yf": year_from, "yt": year_to},
    ).fetchall()
    y_map = {int(r.y): r for r in y_rows}
    by_year: list[YearlyTradeStat] = []
    for y in range(int(year_from), int(year_to) + 1):
        r = y_map.get(y)
        if r:
            sp = float(r.sum_price)
            sa = float(r.sum_area)
            unit = (sp / sa) if sa > 0 else None
            by_year.append(
                YearlyTradeStat(
                    year=y,
                    count=int(r.cnt),
                    total_price_10k_sum=sp,
                    area_sqm_sum=sa,
                    unit_price_per_sqm=unit,
                )
            )
        else:
            by_year.append(YearlyTradeStat(year=y, count=0))

    by_zone = {
        r.zone_type: row_to_stats(r)
        for r in rows
        if r.zone_type != "ALL" and r.land_category == "ALL"
    }
    by_land_category = {
        r.land_category: row_to_stats(r)
        for r in rows
        if r.zone_type == "ALL" and r.land_category != "ALL"
    }
    matrix = [
        MatrixCell(zone_type=r.zone_type, land_category=r.land_category, stats=row_to_stats(r))
        for r in rows
        if r.zone_type != "ALL" and r.land_category != "ALL"
    ]

    return FreeStatsResponse(
        beopjungri_code=beopjungri_code,
        beopjungri_name=region.beopjungri_name,
        year_from=year_from,
        year_to=year_to,
        total=total,
        by_year=by_year,
        by_zone=by_zone,
        by_land_category=by_land_category,
        matrix=matrix,
    )
