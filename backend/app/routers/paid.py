"""
유료 동적 분석 API 라우터
- 복수 지역, 다중 조건 필터 기반 동적 집계
- land_transactions 원자료에서 직접 계산
- 자주 반복되는 쿼리는 analysis_cache 로 캐시
"""

from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas import (
    MatrixCell,
    PaidAnalysisRequest,
    PaidAnalysisResponse,
    StatsResult,
)
from app.stats_utils import compute_stats, remove_outliers

router = APIRouter(prefix="/paid", tags=["유료 분석"])

CACHE_TTL_HOURS = 24


def _make_cache_key(req: PaidAnalysisRequest) -> str:
    payload = json.dumps(req.model_dump(), sort_keys=True, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()


def _get_cache(key: str, db: Session) -> dict | None:
    row = db.execute(
        text("SELECT result_json FROM analysis_cache WHERE cache_key = :key AND expires_at > NOW()"),
        {"key": key},
    ).fetchone()
    if row:
        db.execute(
            text("UPDATE analysis_cache SET hit_count = hit_count + 1 WHERE cache_key = :key"),
            {"key": key},
        )
        db.commit()
        return row.result_json
    return None


def _set_cache(key: str, result: dict, db: Session) -> None:
    expires = datetime.utcnow() + timedelta(hours=CACHE_TTL_HOURS)
    db.execute(
        text("""
            INSERT INTO analysis_cache (cache_key, result_json, expires_at)
            VALUES (:key, :result::jsonb, :expires)
            ON CONFLICT (cache_key) DO UPDATE SET
                result_json = EXCLUDED.result_json,
                expires_at = EXCLUDED.expires_at,
                hit_count = analysis_cache.hit_count + 1
        """),
        {"key": key, "result": json.dumps(result, default=str), "expires": expires},
    )
    db.commit()


def _build_query(req: PaidAnalysisRequest) -> tuple[str, dict]:
    """요청 조건에 따라 동적 SQL과 파라미터를 생성한다."""
    conditions = [
        "is_valid = TRUE",
        "is_cancelled = FALSE",
        "unit_price_per_sqm IS NOT NULL",
        "beopjungri_code = ANY(:region_codes)",
    ]
    params: dict = {"region_codes": req.region_codes}

    if req.year_from:
        conditions.append("contract_year >= :year_from")
        params["year_from"] = req.year_from
    if req.year_to:
        conditions.append("contract_year <= :year_to")
        params["year_to"] = req.year_to
    if req.road_conditions:
        conditions.append("road_condition = ANY(:road_conditions)")
        params["road_conditions"] = req.road_conditions
    if req.area_categories:
        conditions.append("area_category = ANY(:area_categories)")
        params["area_categories"] = req.area_categories
    if req.land_categories:
        conditions.append("land_category = ANY(:land_categories)")
        params["land_categories"] = req.land_categories
    if req.zone_types:
        conditions.append("zone_type = ANY(:zone_types)")
        params["zone_types"] = req.zone_types
    if req.exclude_partial:
        conditions.append("is_partial_ownership = FALSE")

    where = " AND ".join(conditions)
    query = f"""
        SELECT beopjungri_code, zone_type, land_category, road_condition,
               unit_price_per_sqm
        FROM land_transactions
        WHERE {where}
    """
    return query, params


def _prices_to_stats(prices: list[float], exclude_outlier: bool) -> StatsResult:
    if exclude_outlier:
        prices = remove_outliers(prices)
    s = compute_stats(prices)
    return StatsResult(**s)


@router.post("/analyze", response_model=PaidAnalysisResponse, summary="유료 조건 분석")
def analyze(
    req: PaidAnalysisRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    복수 지역·다중 조건 기반 토지 실거래 통계 동적 계산.
    조건이 동일한 반복 쿼리는 24시간 캐시됩니다.
    """
    if not req.region_codes:
        raise HTTPException(status_code=400, detail="지역 코드가 필요합니다.")

    cache_key = _make_cache_key(req)
    cached = _get_cache(cache_key, db)
    if cached:
        return PaidAnalysisResponse(**cached)

    t0 = time.time()

    query, params = _build_query(req)
    rows = db.execute(text(query), params).fetchall()

    if not rows:
        raise HTTPException(status_code=404, detail="해당 조건의 거래 데이터가 없습니다.")

    all_prices = [float(r.unit_price_per_sqm) for r in rows]

    # 전체 통계
    total = _prices_to_stats(all_prices, req.exclude_outlier)

    # 지역별
    by_region: dict[str, list[float]] = {}
    by_zone: dict[str, list[float]] = {}
    by_cat: dict[str, list[float]] = {}
    by_road: dict[str, list[float]] = {}

    for r in rows:
        p = float(r.unit_price_per_sqm)
        by_region.setdefault(r.beopjungri_code, []).append(p)
        if r.zone_type:
            by_zone.setdefault(r.zone_type, []).append(p)
        if r.land_category:
            by_cat.setdefault(r.land_category, []).append(p)
        if r.road_condition:
            by_road.setdefault(r.road_condition, []).append(p)

    # 용도지역 × 지목 매트릭스
    matrix_prices: dict[tuple[str, str], list[float]] = {}
    for r in rows:
        key = (r.zone_type or "미지정", r.land_category or "기타")
        matrix_prices.setdefault(key, []).append(float(r.unit_price_per_sqm))

    matrix = [
        MatrixCell(
            zone_type=z,
            land_category=c,
            stats=_prices_to_stats(ps, req.exclude_outlier),
        )
        for (z, c), ps in matrix_prices.items()
    ]

    elapsed_ms = int((time.time() - t0) * 1000)

    result = PaidAnalysisResponse(
        request=req,
        total=total,
        by_region={k: _prices_to_stats(v, req.exclude_outlier) for k, v in by_region.items()},
        by_zone={k: _prices_to_stats(v, req.exclude_outlier) for k, v in by_zone.items()},
        by_land_category={k: _prices_to_stats(v, req.exclude_outlier) for k, v in by_cat.items()},
        by_road_condition={k: _prices_to_stats(v, req.exclude_outlier) for k, v in by_road.items()},
        matrix=matrix,
        response_ms=elapsed_ms,
    )

    # 캐시 저장 및 사용 기록
    _set_cache(cache_key, result.model_dump(), db)
    _log_usage(req, len(all_prices), elapsed_ms, request, db)

    return result


def _log_usage(
    req: PaidAnalysisRequest,
    result_count: int,
    response_ms: int,
    request: Request,
    db: Session,
) -> None:
    try:
        client_ip = request.client.host if request.client else None
        db.execute(
            text("""
                INSERT INTO paid_analysis_logs (
                    region_codes, year_from, year_to,
                    road_conditions, area_categories, land_categories, zone_types,
                    exclude_partial, exclude_outlier,
                    result_count, response_ms, ip_address
                ) VALUES (
                    :region_codes, :year_from, :year_to,
                    :road_conditions, :area_categories, :land_categories, :zone_types,
                    :exclude_partial, :exclude_outlier,
                    :result_count, :response_ms, :ip_address
                )
            """),
            {
                "region_codes": req.region_codes,
                "year_from": req.year_from,
                "year_to": req.year_to,
                "road_conditions": req.road_conditions,
                "area_categories": req.area_categories,
                "land_categories": req.land_categories,
                "zone_types": req.zone_types,
                "exclude_partial": req.exclude_partial,
                "exclude_outlier": req.exclude_outlier,
                "result_count": result_count,
                "response_ms": response_ms,
                "ip_address": client_ip,
            },
        )
        db.commit()
    except Exception:
        pass
