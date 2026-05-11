"""
유료 동적 분석 API 라우터
- 복수 지역 단위(beopjungri / eupmyeondong / sigungu)·다중 조건 필터
- 매트릭스 특정 칸: 계약연도별 평균 단가(만원/㎡) 추이
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.schemas import (
    MatrixCell,
    MatrixYearlyRequest,
    MatrixYearlyResponse,
    MatrixYearlyStat,
    PaidAnalysisRequest,
    PaidAnalysisResponse,
    RegionSelectionUnit,
    StatsResult,
)
from app.stats_utils import (
    compute_stats,
    outlier_keep_mask,
    remove_outliers,
    stats_dict_from_sql_aggregates,
)

router = APIRouter(prefix="/paid", tags=["유료 분석"])

log = logging.getLogger(__name__)

CACHE_TTL_HOURS = 24


def _make_cache_key(req: PaidAnalysisRequest) -> str:
    payload = json.dumps(_request_stable_payload(req.model_dump()), sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


def _request_stable_payload(d: dict) -> dict:
    """캐시 키·로그 일관화를 위해 선택 단위 순서 고정."""

    dc = dict(d)
    sel = dc.get("region_selections") or []
    if sel:
        dc["region_selections"] = sorted(
            sel, key=lambda x: (x.get("scope_type", ""), x.get("code", ""))
        )
    rc = dc.get("region_codes")
    if rc:
        dc["region_codes"] = sorted(set(rc))
    ys = dc.get("years")
    if ys:
        dc["years"] = sorted(set(int(y) for y in ys))
    return dc


def _normalize_region_units(req: PaidAnalysisRequest) -> list[RegionSelectionUnit]:
    selections: list[RegionSelectionUnit] = []
    if req.region_selections:
        selections.extend(req.region_selections)
    if req.region_codes:
        selections.extend(
            RegionSelectionUnit(scope_type="beopjungri", code=c.strip())
            for c in req.region_codes
            if isinstance(c, str) and c.strip()
        )

    unit_key: set[tuple[str, str]] = set()
    deduped: list[RegionSelectionUnit] = []
    for u in selections:
        c = u.code.strip()
        if not c:
            continue
        k = (u.scope_type, c)
        if k in unit_key:
            continue
        unit_key.add(k)
        deduped.append(RegionSelectionUnit(scope_type=k[0], code=c))

    if not deduped:
        raise HTTPException(status_code=400, detail="지역 범위가 비어 있습니다.")
    return deduped


def expand_region_units(selections: list[RegionSelectionUnit], db: Session) -> list[str]:
    agg: set[str] = set()
    missing: list[str] = []

    for u in selections:
        code = u.code.strip()

        if u.scope_type == "beopjungri":
            row = db.execute(
                text(
                    """
                    SELECT 1 FROM region_codes
                    WHERE beopjungri_code = :c AND COALESCE(is_active, TRUE)
                    LIMIT 1
                    """
                ),
                {"c": code},
            ).fetchone()
            if not row:
                missing.append(f"{u.scope_type}:{code}")
                continue
            agg.add(code)
            continue

        if u.scope_type == "eupmyeondong":
            rows = db.execute(
                text(
                    """
                    SELECT DISTINCT beopjungri_code FROM region_codes
                    WHERE eupmyeondong_code = :c AND COALESCE(is_active, TRUE)
                    """
                ),
                {"c": code},
            ).fetchall()
        elif u.scope_type == "sigungu":
            rows = db.execute(
                text(
                    """
                    SELECT DISTINCT beopjungri_code FROM region_codes
                    WHERE sigungu_code = :c AND COALESCE(is_active, TRUE)
                    """
                ),
                {"c": code},
            ).fetchall()
        else:
            raise HTTPException(
                status_code=400,
                detail=f"지원하지 않는 지역 단위입니다: {u.scope_type}",
            )

        if not rows:
            missing.append(f"{u.scope_type}:{code}")
            continue
        for r in rows:
            agg.add(r[0])

    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"알 수 없거나 비활성인 행정구역 코드: {missing}",
        )
    return sorted(agg)


def _normalize_matrix_yearly_req(req_body: MatrixYearlyRequest) -> PaidAnalysisRequest:
    return PaidAnalysisRequest(
        region_selections=req_body.region_selections,
        region_codes=req_body.region_codes,
        year_from=req_body.year_from,
        year_to=req_body.year_to,
        years=req_body.years,
        road_conditions=req_body.road_conditions,
        area_categories=req_body.area_categories,
        land_categories=req_body.land_categories,
        zone_types=req_body.zone_types,
        exclude_partial=req_body.exclude_partial,
        exclude_outlier=req_body.exclude_outlier,
    )


def _matrix_dimension_sql(alias: str, zone_display: str, land_display: str) -> tuple[str, dict]:
    """매트릭스 헤더 표시용 키(미지정/기타)와 DB 행 연결."""

    param: dict = {}
    zs: list[str] = []

    zd = (zone_display or "").strip()
    if zd in ("미지정", ""):
        zs.append(
            f"({alias}.zone_type IS NULL OR TRIM(BOTH FROM COALESCE({alias}.zone_type::text, '')) = '')"
        )
    else:
        param["mtx_zone"] = zd
        zs.append(
            f"TRIM(BOTH FROM COALESCE({alias}.zone_type::text, ''))"
            " = TRIM(:mtx_zone)"
        )

    ld = (land_display or "").strip()
    if ld in ("기타", ""):
        zs.append(
            f"({alias}.land_category IS NULL OR TRIM(BOTH FROM COALESCE({alias}.land_category::text, '')) = '')"
        )
    else:
        param["mtx_land"] = ld
        zs.append(
            f"TRIM(BOTH FROM COALESCE({alias}.land_category::text, ''))"
            " = TRIM(:mtx_land)"
        )

    return " AND ".join(zs), param


def _build_conditions(
    beopjungri_codes: list[str],
    year_from: Optional[int],
    year_to: Optional[int],
    years: Optional[list[int]],
    road_conditions: Optional[list[str]],
    area_categories: Optional[list[str]],
    land_categories: Optional[list[str]],
    zone_types: Optional[list[str]],
    exclude_partial: bool,
) -> tuple[list[str], dict]:
    conditions = [
        "lt.is_valid = TRUE",
        "lt.is_cancelled = FALSE",
        "lt.unit_price_per_sqm IS NOT NULL",
        "lt.beopjungri_code = ANY(:region_codes)",
    ]
    params: dict = {"region_codes": list(beopjungri_codes)}

    if years is not None and len(years) > 0:
        ys = sorted({int(y) for y in years})
        conditions.append("lt.contract_year = ANY(:filter_years)")
        params["filter_years"] = ys
    else:
        if year_from is not None:
            conditions.append("lt.contract_year >= :year_from")
            params["year_from"] = year_from
        if year_to is not None:
            conditions.append("lt.contract_year <= :year_to")
            params["year_to"] = year_to
    if road_conditions:
        conditions.append("lt.road_condition = ANY(:road_conditions)")
        params["road_conditions"] = road_conditions
    if area_categories:
        conditions.append("lt.area_category = ANY(:area_categories)")
        params["area_categories"] = area_categories
    if land_categories:
        conditions.append("lt.land_category = ANY(:land_categories)")
        params["land_categories"] = land_categories
    if zone_types:
        conditions.append("lt.zone_type = ANY(:zone_types)")
        params["zone_types"] = zone_types
    if exclude_partial:
        conditions.append("lt.is_partial_ownership = FALSE")

    return conditions, params


def _select_full_query(where_sql: str) -> str:
    return f"""
        SELECT lt.beopjungri_code, lt.zone_type, lt.land_category, lt.road_condition,
               lt.unit_price_per_sqm
        FROM land_transactions lt
        WHERE {where_sql}
    """


def _cache_row_payload(row_payload: object) -> dict | None:
    """JSONB/문자열 → dict 안전 변환."""
    if row_payload is None:
        return None
    if isinstance(row_payload, dict):
        return row_payload
    if isinstance(row_payload, str):
        try:
            decoded = json.loads(row_payload)
        except json.JSONDecodeError:
            return None
        return decoded if isinstance(decoded, dict) else None
    return None


def _invalidate_cache_key(key: str, db: Session) -> None:
    try:
        db.execute(text("DELETE FROM analysis_cache WHERE cache_key = :key"), {"key": key})
        db.commit()
    except Exception:
        db.rollback()


def _get_cache(key: str, db: Session) -> dict | None:
    """캐시 테이블 누락·권한 오류 시 조회 없이 무시하고 None."""
    try:
        row = db.execute(
            text(
                "SELECT result_json FROM analysis_cache WHERE cache_key = :key AND expires_at > NOW()"
            ),
            {"key": key},
        ).fetchone()
        if not row:
            return None
        dc = _cache_row_payload(row[0])
        if dc is None:
            log.warning(
                "analysis_cache unreadable payload (%s…), deleting",
                key[:12],
            )
            _invalidate_cache_key(key, db)
            return None

        try:
            db.execute(
                text(
                    "UPDATE analysis_cache SET hit_count = hit_count + 1 WHERE cache_key = :key"
                ),
                {"key": key},
            )
            db.commit()
        except Exception as bump_err:
            log.debug("analysis_cache hit_count bump skipped: %s", bump_err)
            db.rollback()
        return dc
    except Exception as read_err:
        log.warning("analysis_cache read skipped: %s", read_err)
        try:
            db.rollback()
        except Exception:
            pass
        return None


def _set_cache(key: str, result: dict, db: Session) -> None:
    """쓰기 실패는 로그만 — 분석 결과는 그대로 응답."""
    expires = datetime.utcnow() + timedelta(hours=CACHE_TTL_HOURS)
    try:
        db.execute(
            text(
                """
                INSERT INTO analysis_cache (cache_key, result_json, expires_at)
                VALUES (:key, CAST(:result AS jsonb), :expires)
                ON CONFLICT (cache_key) DO UPDATE SET
                    result_json = EXCLUDED.result_json,
                    expires_at = EXCLUDED.expires_at,
                    hit_count = analysis_cache.hit_count + 1
            """
            ),
            {
                "key": key,
                "result": json.dumps(result, ensure_ascii=False, default=str),
                "expires": expires,
            },
        )
        db.commit()
    except Exception as write_err:
        log.warning("analysis_cache write skipped: %s", write_err)
        try:
            db.rollback()
        except Exception:
            pass


def _prices_to_stats(prices: list[float], exclude_outlier: bool) -> StatsResult:
    ps = prices
    if exclude_outlier:
        ps = remove_outliers(ps)
    s = compute_stats(ps)
    return StatsResult(**s)


# 집계에 쓰이는 단가 열(px) 기준 표현식 (CTE base 안에서만 사용)
_AGG_ON_PX = """COUNT(*)::bigint AS n,
  AVG(px)::float8 AS mean_v,
  STDDEV_SAMP(px)::float8 AS std_v,
  MIN(px)::float8 AS min_v,
  percentile_cont(0.25) WITHIN GROUP (ORDER BY px) AS p25_v,
  percentile_cont(0.5) WITHIN GROUP (ORDER BY px) AS med_v,
  percentile_cont(0.75) WITHIN GROUP (ORDER BY px) AS p75_v,
  MAX(px)::float8 AS max_v"""


def _json_obj_maybe(v):
    """psycopg2 가 dict 또는 str 등으로 줄 때 통일."""
    if v is None:
        return None
    if isinstance(v, dict):
        return v
    if isinstance(v, str):
        return json.loads(v)
    return dict(v)


def _json_list_maybe(v) -> list:
    if v is None:
        return []
    if isinstance(v, list):
        return v
    if isinstance(v, str):
        out = json.loads(v)
        return out if isinstance(out, list) else []
    return list(v) if v else []


def _stats_result_from_agg_row(m: dict) -> StatsResult:
    n_raw = m.get("n")
    try:
        n = int(n_raw or 0)
    except (TypeError, ValueError):
        n = 0
    if n <= 0:
        return StatsResult(count=0)
    d = stats_dict_from_sql_aggregates(
        n,
        m.get("mean_v"),
        m.get("std_v"),
        m.get("min_v"),
        m.get("p25_v"),
        m.get("med_v"),
        m.get("p75_v"),
        m.get("max_v"),
    )
    return StatsResult(**d)


def _analyze_core_materialized_rows(
    req: PaidAnalysisRequest,
    *,
    resolved_codes: list[str],
    db: Session,
) -> PaidAnalysisResponse:
    """이상치 제외 시 행 전체를 읽어 그룹별 IQR 필터 (느림, 대용량에 부적합)."""
    parts, params = _build_conditions(
        resolved_codes,
        req.year_from,
        req.year_to,
        req.years,
        req.road_conditions,
        req.area_categories,
        req.land_categories,
        req.zone_types,
        req.exclude_partial,
    )

    query = _select_full_query(" AND ".join(parts))
    rows = db.execute(text(query), params).fetchall()

    if not rows:
        raise HTTPException(status_code=404, detail="해당 조건의 거래 데이터가 없습니다.")

    all_prices: list[float] = []
    by_region: dict[str, list[float]] = defaultdict(list)
    matrix_prices: dict[tuple[str, str], list[float]] = defaultdict(list)

    for r in rows:
        p = float(r.unit_price_per_sqm)
        all_prices.append(p)
        bc = (str(r.beopjungri_code) if r.beopjungri_code is not None else "").strip()
        if bc:
            by_region[bc].append(p)
        zraw = "" if r.zone_type is None else str(r.zone_type).strip()
        lraw = "" if r.land_category is None else str(r.land_category).strip()
        zt = zraw if zraw else "미지정"
        lc = lraw if lraw else "기타"
        matrix_prices[(zt, lc)].append(p)

    total = _prices_to_stats(all_prices, req.exclude_outlier)
    matrix = [
        MatrixCell(zone_type=z, land_category=c, stats=_prices_to_stats(ps, req.exclude_outlier))
        for (z, c), ps in matrix_prices.items()
    ]

    return PaidAnalysisResponse(
        request=req,
        total=total,
        by_region={k: _prices_to_stats(v, req.exclude_outlier) for k, v in by_region.items()},
        by_zone={},
        by_land_category={},
        by_road_condition={},
        matrix=matrix,
        response_ms=0,
    )


def _analyze_core_sql_aggregate(
    req: PaidAnalysisRequest,
    *,
    resolved_codes: list[str],
    db: Session,
) -> PaidAnalysisResponse:
    """
    이상치 미적용.
    현재 웹 화면은 매트릭스 + (복수 시) 법정별 통계만 쓰이므로, 용도·지목·도로 단독 차원 통계 집계는 생략한다.
    percentile 정렬이 work_mem 에 민감해 세션별 work_mem 상향.
    """
    parts, params = _build_conditions(
        resolved_codes,
        req.year_from,
        req.year_to,
        req.years,
        req.road_conditions,
        req.area_categories,
        req.land_categories,
        req.zone_types,
        req.exclude_partial,
    )
    where_sql = " AND ".join(parts)
    apx = _AGG_ON_PX

    wm_mb = max(32, min(512, int(settings.paid_analyze_work_mem_mb)))
    db.execute(text(f"SET LOCAL work_mem = '{wm_mb}MB'"))

    bundle_sql = text(
        f"""
        WITH base AS MATERIALIZED (
          SELECT
            btrim(cast(lt.beopjungri_code AS text)) AS bc,
            lt.zone_type,
            lt.land_category,
            lt.unit_price_per_sqm::float8 AS px
          FROM land_transactions lt
          WHERE {where_sql}
        )
        SELECT
          (SELECT row_to_json(t)
           FROM (SELECT {apx} FROM base) t) AS total_json,
          (SELECT COALESCE(json_agg(row_to_json(x)), '[]'::json)
           FROM (
             SELECT bc AS rk, {apx}
             FROM base
             GROUP BY bc
           ) x) AS by_region_json,
          (SELECT COALESCE(json_agg(row_to_json(x)), '[]'::json)
           FROM (
             SELECT
               COALESCE(NULLIF(BTRIM(zone_type::text), ''), '미지정') AS zt,
               COALESCE(NULLIF(BTRIM(land_category::text), ''), '기타') AS lc,
               {apx}
             FROM base
             GROUP BY 1, 2
           ) x) AS matrix_json
        """
    )

    bundle = db.execute(bundle_sql, params).mappings().one()

    total_d = _json_obj_maybe(bundle["total_json"])
    if not total_d or int(total_d.get("n") or 0) == 0:
        raise HTTPException(status_code=404, detail="해당 조건의 거래 데이터가 없습니다.")
    total = _stats_result_from_agg_row(total_d)

    by_region: dict[str, StatsResult] = {}
    for item in _json_list_maybe(bundle["by_region_json"]):
        if not isinstance(item, dict):
            continue
        k = (item.get("rk") or "").strip()
        if k:
            by_region[k] = _stats_result_from_agg_row(item)

    matrix: list[MatrixCell] = []
    for item in _json_list_maybe(bundle["matrix_json"]):
        if not isinstance(item, dict):
            continue
        zt = (item.get("zt") or "미지정").strip() or "미지정"
        lc = (item.get("lc") or "기타").strip() or "기타"
        matrix.append(
            MatrixCell(
                zone_type=zt,
                land_category=lc,
                stats=_stats_result_from_agg_row(item),
            )
        )

    return PaidAnalysisResponse(
        request=req,
        total=total,
        by_region=by_region,
        by_zone={},
        by_land_category={},
        by_road_condition={},
        matrix=matrix,
        response_ms=0,
    )


def _analyze_core(
    req: PaidAnalysisRequest,
    *,
    resolved_codes: list[str],
    db: Session,
) -> PaidAnalysisResponse:
    if req.exclude_outlier:
        return _analyze_core_materialized_rows(
            req, resolved_codes=resolved_codes, db=db
        )
    return _analyze_core_sql_aggregate(req, resolved_codes=resolved_codes, db=db)


def _log_usage(
    req: PaidAnalysisRequest,
    resolved_codes: list[str],
    result_count: int,
    response_ms: int,
    request: Request,
    db: Session,
) -> None:
    try:
        client_ip = request.client.host if request.client else None
        db.execute(
            text(
                """
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
                """
            ),
            {
                "region_codes": resolved_codes,
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
        db.rollback()


@router.post("/analyze", response_model=PaidAnalysisResponse, summary="유료 조건 분석")
def analyze(
    req: PaidAnalysisRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    복수 지역(beopjungri·읍면동·시군구 단위 포함)·필터 기반 통계 계산.
    시·도 전체 단일 선택만으로는 포함할 수 없다.

    이상치 제외가 꺼져 있으면 DB 집계 쿼리만 사용한다(거래 행 전체 적재 안 함).
    이상치 제외가 켜져 있으면 행별 IQR 때문에 전체 결과를 불러오며 느릴 수 있다.
    """

    units = _normalize_region_units(req)
    resolved_codes = expand_region_units(units, db)
    req_for_cache = PaidAnalysisRequest(
        **req.model_dump()
        | {"region_selections": units, "region_codes": sorted(resolved_codes)}
    )

    cache_key = _make_cache_key(req_for_cache)
    cached = _get_cache(cache_key, db)
    if cached is not None:
        try:
            return PaidAnalysisResponse.model_validate(cached)
        except (ValidationError, TypeError, ValueError) as val_err:
            log.warning(
                "analysis_cache entry invalid (%s…), rebuilding: %s",
                cache_key[:12],
                val_err,
            )
            _invalidate_cache_key(cache_key, db)

    t0 = time.time()

    payload = _analyze_core(req, resolved_codes=resolved_codes, db=db)
    elapsed_ms = int((time.time() - t0) * 1000)
    result_count = int(payload.total.count)

    cached_req = PaidAnalysisResponse(
        request=req_for_cache,
        total=payload.total,
        by_region=payload.by_region,
        by_zone=payload.by_zone,
        by_land_category=payload.by_land_category,
        by_road_condition=payload.by_road_condition,
        matrix=payload.matrix,
        response_ms=elapsed_ms,
    )

    dumped = cached_req.model_dump()
    dumped["response_ms"] = elapsed_ms

    _set_cache(cache_key, dumped, db)
    _log_usage(req, resolved_codes, result_count, elapsed_ms, request, db)

    return cached_req


@router.post(
    "/matrix-yearly",
    response_model=MatrixYearlyResponse,
    summary="매트릭스 칸 연도별 평균·건수 추이",
)
def matrix_yearly(body: MatrixYearlyRequest, db: Session = Depends(get_db)):
    """
    같은 필터·지역 범위 안에서 특정 용도지역×지목 칸에 대해 계약연도별로
    만원/㎡ 단가 목록 산술평균을 반환한다. 이상치 제외 시 전체 매칭 행 목록 기준 마스킹 후 연도별로 건수·평균을 계산한다.
    """
    base_req = _normalize_matrix_yearly_req(body)
    units = _normalize_region_units(base_req)
    resolved_codes = expand_region_units(units, db)

    base_parts, params = _build_conditions(
        resolved_codes,
        body.year_from,
        body.year_to,
        body.years,
        body.road_conditions,
        body.area_categories,
        body.land_categories,
        body.zone_types,
        body.exclude_partial,
    )

    mtx_sql, mtx_par = _matrix_dimension_sql(
        "lt", body.zone_type.strip(), body.land_category.strip()
    )

    merged_params = dict(params)
    merged_params.update(mtx_par)
    merged_where = " AND ".join(base_parts + [mtx_sql])

    query = text(
        f"""
        SELECT lt.contract_year AS y, lt.unit_price_per_sqm AS px
        FROM land_transactions lt
        WHERE {merged_where}
        ORDER BY lt.contract_year ASC
        """
    )

    rows = db.execute(query, merged_params).fetchall()
    if not rows:
        raise HTTPException(status_code=404, detail="해당 상세 칸에는 거래가 없습니다.")

    years_px: list[int] = [int(r.y) for r in rows]
    prices_px: list[float] = [float(r.px) for r in rows]

    if body.exclude_outlier:
        keep = outlier_keep_mask(prices_px)
        years_px = [y for y, ok in zip(years_px, keep) if ok]
        prices_px = [p for p, ok in zip(prices_px, keep) if ok]

    if not prices_px:
        raise HTTPException(status_code=404, detail="이상치 제외 후 남은 데이터가 없습니다.")

    out_map: defaultdict[int, list[float]] = defaultdict(list)
    for y, p in zip(years_px, prices_px):
        out_map[y].append(p)

    stat_rows = [
        MatrixYearlyStat(
            year=y,
            count=len(out_map[y]),
            mean_unit_price_per_sqm=round(float(sum(out_map[y])) / len(out_map[y]), 1),
        )
        for y in sorted(out_map.keys())
    ]

    return MatrixYearlyResponse(
        zone_type=body.zone_type.strip(),
        land_category=body.land_category.strip(),
        rows=stat_rows,
    )
