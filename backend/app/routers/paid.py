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
from datetime import date, datetime, timedelta, timezone
from typing import Optional

import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.analysis_base_cache import has_valid_analysis_base_cache
from app.matrix_rolling_buckets import (
    chart_bucket_labels_old_first_for_ref_month,
    iter_rolling_year_buckets_old_first,
)
from app.config import settings
from app.db import get_db
from app.population_query import attach_population_year_end
from app.schemas import (
    HistogramBin,
    MatrixCell,
    MatrixCellHistogramRequest,
    MatrixCellHistogramResponse,
    MatrixCellTransactionItem,
    MatrixCellTransactionsRequest,
    MatrixCellTransactionsResponse,
    MatrixYearlyRequest,
    MatrixYearlyResponse,
    MatrixYearlyStat,
    PaidAnalysisRequest,
    PaidAnalysisResponse,
    RegionSelectionUnit,
    StatsResult,
    YearlyTradeStat,
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


def _effective_paid_request(req: PaidAnalysisRequest) -> PaidAnalysisRequest:
    """
    - 연도 칩(`years` 비어 있지 않음)이 있으면 year_from/year_to는 무시한다(과거 클라이언트가 둘 다 보내도 혼선 방지).
    - 면적 직접 범위(B 모드): area_sqm_min/max 중 하나라도 있으면 area_categories는 무시한다.
    """
    updates: dict = {}

    rps = req.rolling_matrix_period_start
    rpe = req.rolling_matrix_period_end
    if rps is not None and rpe is not None:
        updates["years"] = None
        updates["year_from"] = None
        updates["year_to"] = None

    ys = req.years
    if (rps is None or rpe is None) and ys is not None and len(ys) > 0:
        updates["years"] = sorted({int(y) for y in ys})
        updates["year_from"] = None
        updates["year_to"] = None

    if req.area_sqm_min is not None or req.area_sqm_max is not None:
        if req.area_categories:
            updates["area_categories"] = None

    if not updates:
        return req
    return req.model_copy(update=updates)


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

    beopjungri_units = [
        u.code.strip()
        for u in selections
        if u.scope_type == "beopjungri" and u.code.strip()
    ]
    if beopjungri_units:
        rows = db.execute(
            text(
                """
                SELECT btrim(cast(beopjungri_code AS text)) AS code
                FROM region_codes
                WHERE btrim(cast(beopjungri_code AS text)) = ANY(:codes)
                  AND COALESCE(is_active, TRUE)
                """
            ),
            {"codes": sorted(set(beopjungri_units))},
        ).fetchall()
        found = {str(r._mapping["code"]).strip() for r in rows}
        agg.update(found)
        for code in sorted(set(beopjungri_units)):
            if code not in found:
                missing.append(f"beopjungri:{code}")

    for u in selections:
        if u.scope_type == "beopjungri":
            continue

        code = u.code.strip()
        if not code:
            continue

        if u.scope_type == "eupmyeondong":
            rows = db.execute(
                text(
                    """
                    SELECT DISTINCT btrim(cast(beopjungri_code AS text)) AS code
                    FROM region_codes
                    WHERE btrim(cast(eupmyeondong_code AS text)) = :c
                      AND COALESCE(is_active, TRUE)
                    """
                ),
                {"c": code},
            ).fetchall()
        elif u.scope_type == "sigungu":
            rows = db.execute(
                text(
                    """
                    SELECT DISTINCT btrim(cast(beopjungri_code AS text)) AS code
                    FROM region_codes
                    WHERE btrim(cast(sigungu_code AS text)) = :c
                      AND COALESCE(is_active, TRUE)
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
            agg.add(str(r._mapping["code"]).strip())

    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"알 수 없거나 비활성인 행정구역 코드: {missing}",
        )
    return sorted(agg)


def _normalize_matrix_yearly_req(req_body: MatrixYearlyRequest) -> PaidAnalysisRequest:
    r = PaidAnalysisRequest(
        region_selections=req_body.region_selections,
        region_codes=req_body.region_codes,
        year_from=req_body.year_from,
        year_to=req_body.year_to,
        years=req_body.years,
        base_cache_key=req_body.base_cache_key,
        road_conditions=req_body.road_conditions,
        area_categories=req_body.area_categories,
        land_categories=req_body.land_categories,
        zone_types=req_body.zone_types,
        exclude_partial=req_body.exclude_partial,
        exclude_outlier=req_body.exclude_outlier,
        outlier_iqr_multiplier=req_body.outlier_iqr_multiplier,
        area_sqm_min=req_body.area_sqm_min,
        area_sqm_max=req_body.area_sqm_max,
        rolling_matrix_period_start=req_body.rolling_matrix_period_start,
        rolling_matrix_period_end=req_body.rolling_matrix_period_end,
        rolling_bucket_count=req_body.rolling_bucket_count,
        rolling_stats_reference_date=req_body.rolling_stats_reference_date,
    )
    return _effective_paid_request(r)


def _matrix_cell_merged_where(body: MatrixYearlyRequest, db: Session) -> tuple[str, dict]:
    """land_transactions lt 에 대해 매트릭스 한 칸(용도×지목)까지 적용한 WHERE 절과 바인딩."""
    base_req = _normalize_matrix_yearly_req(body)
    units = _normalize_region_units(base_req)
    resolved_codes = expand_region_units(units, db)
    base_cache_key = (
        body.base_cache_key
        if has_valid_analysis_base_cache(db, body.base_cache_key)
        else None
    )
    roll_ps = base_req.rolling_matrix_period_start
    roll_pe = base_req.rolling_matrix_period_end
    yf, yt, ylst = base_req.year_from, base_req.year_to, base_req.years
    if roll_ps is not None and roll_pe is not None:
        yf = None
        yt = None
        ylst = None

    base_parts, params = _build_conditions(
        resolved_codes,
        yf,
        yt,
        ylst,
        base_cache_key,
        base_req.road_conditions,
        base_req.area_categories,
        base_req.land_categories,
        base_req.zone_types,
        base_req.exclude_partial,
        base_req.area_sqm_min,
        base_req.area_sqm_max,
        rolling_contract_ps=roll_ps,
        rolling_contract_pe=roll_pe,
    )
    mtx_sql, mtx_par = _matrix_dimension_sql(
        "lt", body.zone_type.strip(), body.land_category.strip()
    )
    merged_params = dict(params)
    merged_params.update(mtx_par)
    merged_where = " AND ".join(base_parts + [mtx_sql])
    return merged_where, merged_params


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
    base_cache_key: Optional[str],
    road_conditions: Optional[list[str]],
    area_categories: Optional[list[str]],
    land_categories: Optional[list[str]],
    zone_types: Optional[list[str]],
    exclude_partial: bool,
    area_sqm_min: Optional[float] = None,
    area_sqm_max: Optional[float] = None,
    rolling_contract_ps: Optional[date] = None,
    rolling_contract_pe: Optional[date] = None,
) -> tuple[list[str], dict]:
    conditions = [
        "lt.is_valid = TRUE",
        "lt.is_cancelled = FALSE",
        "lt.unit_price_per_sqm IS NOT NULL",
    ]
    params: dict = {}

    base_key = (base_cache_key or "").strip()
    if base_key:
        conditions.append(
            """
            lt.id IN (
                SELECT unnest(row_ids)
                FROM analysis_base_cache
                WHERE cache_key = :base_cache_key
                  AND expires_at > NOW()
            )
            """
        )
        params["base_cache_key"] = base_key
    else:
        conditions.append("lt.beopjungri_code = ANY(:region_codes)")
        params["region_codes"] = list(beopjungri_codes)

    if rolling_contract_ps is not None and rolling_contract_pe is not None:
        conditions.append("lt.contract_date IS NOT NULL")
        conditions.append("lt.contract_date >= :rolling_ps")
        conditions.append("lt.contract_date <= :rolling_pe")
        params["rolling_ps"] = rolling_contract_ps
        params["rolling_pe"] = rolling_contract_pe
    elif years is not None and len(years) > 0:
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

    use_area_span = area_sqm_min is not None or area_sqm_max is not None
    if use_area_span:
        if area_sqm_min is not None:
            conditions.append("lt.area_sqm >= :area_sqm_min")
            params["area_sqm_min"] = float(area_sqm_min)
        if area_sqm_max is not None:
            conditions.append("lt.area_sqm <= :area_sqm_max")
            params["area_sqm_max"] = float(area_sqm_max)
    elif area_categories:
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
               lt.unit_price_per_sqm,
               lt.contract_year::int AS contract_year,
               lt.total_price_10k::float8 AS total_price_10k,
               lt.area_sqm::float8 AS area_sqm
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
    # DECISIONS D-005 — UTC + tz-aware 통일. PostgreSQL TIMESTAMPTZ 와 비교 시 묵시 캐스팅 위험을 없앤다.
    expires = datetime.now(timezone.utc) + timedelta(hours=CACHE_TTL_HOURS)
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


def _prices_to_stats(
    prices: list[float],
    exclude_outlier: bool,
    *,
    iqr_multiplier: float,
) -> StatsResult:
    ps = prices
    if exclude_outlier:
        ps = remove_outliers(ps, iqr_multiplier=iqr_multiplier)
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


def _ordered_analysis_years(req: PaidAnalysisRequest) -> list[int]:
    if req.years is not None and len(req.years) > 0:
        return sorted({int(y) for y in req.years})
    if req.year_from is not None and req.year_to is not None:
        a, b = int(req.year_from), int(req.year_to)
        if a <= b:
            return list(range(a, b + 1))
    return []


def _parse_by_year_agg_json(rows: list, columns: list[int]) -> list[YearlyTradeStat]:
    m: dict[int, dict] = {}
    for raw in rows:
        if not isinstance(raw, dict):
            continue
        yr = raw.get("yr")
        if yr is None:
            continue
        try:
            y = int(yr)
        except (TypeError, ValueError):
            continue
        m[y] = raw
    out: list[YearlyTradeStat] = []
    for y in columns:
        row = m.get(y)
        if not row:
            out.append(YearlyTradeStat(year=y, count=0))
            continue
        cnt = int(row.get("cnt") or 0)
        sp = float(row.get("sum_p") or 0.0)
        sa = float(row.get("sum_a") or 0.0)
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
    return out


def _by_year_trade_stats_materialized(
    bucket: dict[int, list[tuple[float, float, float]]],
    *,
    columns: list[int],
    iqr_multiplier: float,
) -> list[YearlyTradeStat]:
    """연도별 (단가·총액·면적) 행 목록으로 Tukey 마스크 후 금액·면적 합산."""

    out: list[YearlyTradeStat] = []
    k = float(iqr_multiplier)
    for y in columns:
        tup = bucket.get(y) or ()
        if not tup:
            out.append(YearlyTradeStat(year=y, count=0))
            continue
        prices = [t[0] for t in tup]
        mask = outlier_keep_mask(prices, iqr_multiplier=k)
        kept = [tup[i] for i in range(len(tup)) if mask[i]]
        cnt = len(kept)
        sp = sum(t[1] for t in kept)
        sa = sum(t[2] for t in kept)
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
    return out


def _infer_year_columns_from_items(items: list) -> list[int]:
    ys: list[int] = []
    for it in items:
        if isinstance(it, dict) and it.get("yr") is not None:
            try:
                ys.append(int(it["yr"]))
            except (TypeError, ValueError):
                continue
    return sorted(set(ys))


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
        req.base_cache_key,
        req.road_conditions,
        req.area_categories,
        req.land_categories,
        req.zone_types,
        req.exclude_partial,
        req.area_sqm_min,
        req.area_sqm_max,
    )

    query = _select_full_query(" AND ".join(parts))
    rows = db.execute(text(query), params).fetchall()

    if not rows:
        raise HTTPException(status_code=404, detail="해당 조건의 거래 데이터가 없습니다.")

    all_prices: list[float] = []
    by_region: dict[str, list[float]] = defaultdict(list)
    matrix_prices: dict[tuple[str, str], list[float]] = defaultdict(list)
    year_bucket: dict[int, list[tuple[float, float, float]]] = defaultdict(list)

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
        try:
            cy = int(r.contract_year)
        except (TypeError, ValueError):
            cy = None
        if cy is not None:
            tp = float(r.total_price_10k or 0)
            ar_sq = float(r.area_sqm or 0)
            year_bucket[cy].append((p, tp, ar_sq))

    k = float(req.outlier_iqr_multiplier)
    ycols = _ordered_analysis_years(req)
    if not ycols:
        ycols = sorted(year_bucket.keys())
    by_year_list = _by_year_trade_stats_materialized(
        year_bucket, columns=ycols, iqr_multiplier=k
    )
    by_year_list = attach_population_year_end(
        db, region_codes=resolved_codes, items=by_year_list
    )
    total = _prices_to_stats(all_prices, req.exclude_outlier, iqr_multiplier=k)
    matrix = [
        MatrixCell(
            zone_type=z,
            land_category=c,
            stats=_prices_to_stats(ps, req.exclude_outlier, iqr_multiplier=k),
        )
        for (z, c), ps in matrix_prices.items()
    ]

    return PaidAnalysisResponse(
        request=req,
        total=total,
        by_year=by_year_list,
        by_region={
            rk: _prices_to_stats(v, req.exclude_outlier, iqr_multiplier=k)
            for rk, v in by_region.items()
        },
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
        req.base_cache_key,
        req.road_conditions,
        req.area_categories,
        req.land_categories,
        req.zone_types,
        req.exclude_partial,
        req.area_sqm_min,
        req.area_sqm_max,
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
           ) x) AS matrix_json,
          (SELECT COALESCE(json_agg(row_to_json(x)), '[]'::json)
           FROM (
             SELECT lt.contract_year::int AS yr,
                    COUNT(*)::bigint AS cnt,
                    COALESCE(SUM(lt.total_price_10k), 0)::float8 AS sum_p,
                    COALESCE(SUM(lt.area_sqm), 0)::float8 AS sum_a
             FROM land_transactions lt
             WHERE {where_sql}
             GROUP BY lt.contract_year
           ) x) AS by_year_json
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

    by_year_items = _json_list_maybe(bundle["by_year_json"])
    ycols = _ordered_analysis_years(req)
    if not ycols:
        ycols = _infer_year_columns_from_items(by_year_items)
    by_year_list = _parse_by_year_agg_json(by_year_items, ycols)
    by_year_list = attach_population_year_end(
        db, region_codes=resolved_codes, items=by_year_list
    )

    return PaidAnalysisResponse(
        request=req,
        total=total,
        by_year=by_year_list,
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


def _latest_v2_as_of(db: Session) -> tuple[Optional[object], Optional[object]]:
    """
    DECISIONS D-006 — 유료 응답에 같이 노출할 `as_of_month`, `stats_reference_date`.
    `land_basic_stats_v2` 미적재 환경에서는 둘 다 None.
    """
    try:
        row = db.execute(
            text("SELECT MAX(as_of_month) AS am FROM land_basic_stats_v2")
        ).fetchone()
    except Exception as exc:  # noqa: BLE001
        log.debug("latest_v2_as_of skipped: %s", exc)
        return None, None
    am = row.am if row else None
    if am is None:
        return None, None
    # stats_reference_date = as_of_month 의 다음 달 1일 (`v2_stats_windows.stats_ui_reference_date` 와 동일).
    if am.month == 12:
        ref = am.replace(year=am.year + 1, month=1, day=1)
    else:
        ref = am.replace(month=am.month + 1, day=1)
    return am, ref


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
    복수 법정동·리·필터 기반 거래 원장(`land_transactions`) 집계.

    클라이언트는 시·도·시군구 등 상위 선택도 산하 `beopjungri_code` 목록으로 풀어서
    `region_codes`(또는 `region_selections`)로 넘긴다. 시·도 단일 코드 문자열만으로는
    이 엔드포인트에 전달하지 않는다(API는 영역 목록 또는 하위 행정 단위 선택을 기대).

    이상치 제외가 꺼져 있으면 DB 집계 쿼리만 사용한다(거래 행 전체 적재 안 함).
    이상치 제외가 켜져 있으면 행별 IQR 때문에 전체 결과를 불러오며 느릴 수 있다.
    """

    req0 = _effective_paid_request(req)
    units = _normalize_region_units(req0)
    resolved_codes = expand_region_units(units, db)
    base_cache_key = (
        req0.base_cache_key
        if has_valid_analysis_base_cache(db, req0.base_cache_key)
        else None
    )
    req_for_analysis = req0.model_copy(update={"base_cache_key": base_cache_key})
    req_for_cache = PaidAnalysisRequest(
        **req_for_analysis.model_dump()
        | {"region_selections": units, "region_codes": sorted(resolved_codes)}
    )

    # DECISIONS D-006 — 모든 응답 경로에서 같은 as_of/ref 를 단다.
    as_of, ref = _latest_v2_as_of(db)

    cache_key = _make_cache_key(req_for_cache)
    cached = _get_cache(cache_key, db)
    if cached is not None:
        try:
            resp = PaidAnalysisResponse.model_validate(cached)
            merged_y = attach_population_year_end(
                db, region_codes=resolved_codes, items=list(resp.by_year)
            )
            return resp.model_copy(
                update={
                    "by_year": merged_y,
                    "as_of_month": as_of,
                    "stats_reference_date": ref,
                }
            )
        except (ValidationError, TypeError, ValueError) as val_err:
            log.warning(
                "analysis_cache entry invalid (%s…), rebuilding: %s",
                cache_key[:12],
                val_err,
            )
            _invalidate_cache_key(cache_key, db)

    t0 = time.time()

    payload = _analyze_core(req_for_analysis, resolved_codes=resolved_codes, db=db)
    elapsed_ms = int((time.time() - t0) * 1000)
    result_count = int(payload.total.count)

    cached_req = PaidAnalysisResponse(
        request=req_for_cache,
        total=payload.total,
        by_year=payload.by_year,
        by_region=payload.by_region,
        by_zone=payload.by_zone,
        by_land_category=payload.by_land_category,
        by_road_condition=payload.by_road_condition,
        matrix=payload.matrix,
        response_ms=elapsed_ms,
        as_of_month=as_of,
        stats_reference_date=ref,
    )

    dumped = cached_req.model_dump()
    dumped["response_ms"] = elapsed_ms

    _set_cache(cache_key, dumped, db)
    _log_usage(req_for_analysis, resolved_codes, result_count, elapsed_ms, request, db)

    return cached_req


@router.post(
    "/matrix-yearly",
    response_model=MatrixYearlyResponse,
    summary="매트릭스 칸 연도별 또는 롤링 12개월 구간별 평균·건수 추이",
)
def matrix_yearly(body: MatrixYearlyRequest, db: Session = Depends(get_db)):
    """
    - 기본(레거시): 계약연도별 산술평균.
    - `rolling_matrix_period_*` 와 `rolling_bucket_count` 가 모두 오면 매트릭스 V2와 동일 계약 구간 안에서
      12개월 롤링 버킷(과거→최근) 집계.
    """
    merged_where, merged_params = _matrix_cell_merged_where(body, db)

    rp_s = body.rolling_matrix_period_start
    rp_e = body.rolling_matrix_period_end
    rb_n = body.rolling_bucket_count
    rolling_mode = rp_s is not None and rp_e is not None and rb_n is not None

    if rolling_mode:
        if rp_s > rp_e:
            raise HTTPException(
                status_code=422,
                detail="rolling_matrix_period_start 가 rolling_matrix_period_end 보다 클 수 없습니다.",
            )
        bc = int(rb_n)
        if bc < 1 or bc > 10:
            raise HTTPException(status_code=422, detail="rolling_bucket_count 는 1~10 입니다.")

        buckets = iter_rolling_year_buckets_old_first(rp_e, bc)
        ref_d = body.rolling_stats_reference_date
        chart_labels = chart_bucket_labels_old_first_for_ref_month(ref_d, buckets)
        stat_rows: list[MatrixYearlyStat] = []
        for bi, ((bs_raw, be_raw), chart_label) in enumerate(zip(buckets, chart_labels)):
            bs_eff = bs_raw if bs_raw >= rp_s else rp_s
            be_eff = be_raw if be_raw <= rp_e else rp_e
            if bs_eff > be_eff:
                stat_rows.append(
                    MatrixYearlyStat(
                        year=None,
                        bucket_index=bi,
                        period_start=bs_raw,
                        period_end=be_raw,
                        chart_label=chart_label,
                        count=0,
                        mean_unit_price_per_sqm=None,
                    )
                )
                continue
            w_extra = merged_where + " AND lt.contract_date >= :buck_ps AND lt.contract_date <= :buck_pe"
            pb = dict(merged_params)
            pb["buck_ps"] = bs_eff
            pb["buck_pe"] = be_eff
            qry = text(
                "SELECT lt.unit_price_per_sqm::float8 AS px "
                "FROM land_transactions lt "
                f"WHERE {w_extra}"
            )
            prow = db.execute(qry, pb).fetchall()
            prices_px = [float(r.px) for r in prow if r.px is not None]
            if body.exclude_outlier and prices_px:
                keep = outlier_keep_mask(
                    prices_px, iqr_multiplier=float(body.outlier_iqr_multiplier)
                )
                prices_px = [p for p, k in zip(prices_px, keep) if k]
            if not prices_px:
                mean_v = None
            else:
                mean_v = round(float(sum(prices_px)) / len(prices_px), 1)
            stat_rows.append(
                MatrixYearlyStat(
                    year=None,
                    bucket_index=bi,
                    period_start=bs_raw,
                    period_end=be_raw,
                    chart_label=chart_label,
                    count=len(prices_px),
                    mean_unit_price_per_sqm=mean_v,
                )
            )
        if not any(sr.count > 0 for sr in stat_rows):
            raise HTTPException(
                status_code=404, detail="해당 상세 칸에는 거래가 없습니다."
            )
        return MatrixYearlyResponse(
            zone_type=body.zone_type.strip(),
            land_category=body.land_category.strip(),
            rows=stat_rows,
        )

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
        keep = outlier_keep_mask(
            prices_px, iqr_multiplier=float(body.outlier_iqr_multiplier)
        )
        years_px = [y for y, ok in zip(years_px, keep) if ok]
        prices_px = [p for p, ok in zip(prices_px, keep) if ok]

    if not prices_px:
        raise HTTPException(status_code=404, detail="이상치 제외 후 남은 데이터가 없습니다.")

    out_map: defaultdict[int, list[float]] = defaultdict(list)
    for y, p in zip(years_px, prices_px):
        out_map[y].append(p)

    stat_rows_legacy = [
        MatrixYearlyStat(
            year=y,
            bucket_index=None,
            period_start=None,
            period_end=None,
            chart_label=None,
            count=len(out_map[y]),
            mean_unit_price_per_sqm=round(float(sum(out_map[y])) / len(out_map[y]), 1),
        )
        for y in sorted(out_map.keys())
    ]

    return MatrixYearlyResponse(
        zone_type=body.zone_type.strip(),
        land_category=body.land_category.strip(),
        rows=stat_rows_legacy,
    )


@router.post(
    "/matrix-cell-histogram",
    response_model=MatrixCellHistogramResponse,
    summary="매트릭스 칸 단가 분포(히스토그램)",
)
def matrix_cell_histogram(
    body: MatrixCellHistogramRequest, db: Session = Depends(get_db)
):
    """
    matrix-yearly 와 동일 필터·이상치 정책으로 단가(만원/㎡) 표본을 만든 뒤
    구간별 건수만 반환한다. `histogram_scope=all` 이면 필터 연도 전체,
    `single` 이면 `histogram_year` 한 해의 표본만 사용한다.
    """
    merged_where, merged_params = _matrix_cell_merged_where(body, db)
    query = text(
        f"""
        SELECT lt.contract_date AS cd,
               lt.contract_year AS y,
               lt.unit_price_per_sqm AS px
        FROM land_transactions lt
        WHERE {merged_where}
        ORDER BY lt.contract_year ASC
        """
    )
    rows = db.execute(query, merged_params).fetchall()
    if not rows:
        raise HTTPException(status_code=404, detail="해당 상세 칸에는 거래가 없습니다.")

    cds = [r.cd for r in rows]
    years_px = [int(r.y) for r in rows]
    prices_px = [float(r.px) for r in rows]
    if body.exclude_outlier:
        keep = outlier_keep_mask(
            prices_px, iqr_multiplier=float(body.outlier_iqr_multiplier)
        )
    else:
        keep = [True] * len(prices_px)

    hist_ps: Optional[date] = None
    hist_pe: Optional[date] = None
    h_bucket_index: Optional[int] = None
    rolling_single = False

    rp_s = body.rolling_matrix_period_start
    rp_e = body.rolling_matrix_period_end
    rb_n = body.rolling_bucket_count

    if body.histogram_scope == "single":
        if rp_s is not None and rp_e is not None and rb_n is not None:
            rolling_single = True
            bi = int(body.histogram_bucket_index or 0)
            h_bucket_index = bi
            buckets = iter_rolling_year_buckets_old_first(rp_e, int(rb_n))
            if bi < 0 or bi >= len(buckets):
                raise HTTPException(
                    status_code=422, detail="histogram_bucket_index 범위를 벗어났습니다."
                )
            bs_raw, be_raw = buckets[bi]
            bs_eff = bs_raw if bs_raw >= rp_s else rp_s
            be_eff = be_raw if be_raw <= rp_e else rp_e
            hist_ps, hist_pe = bs_eff, be_eff
            combined = []
            for ok, cd in zip(keep, cds):
                if cd is None or ok is False:
                    combined.append(False)
                    continue
                if not isinstance(cd, date):
                    try:
                        cd = date.fromisoformat(str(cd)[:10])
                    except ValueError:
                        combined.append(False)
                        continue
                combined.append(ok and bs_eff <= cd <= be_eff)
        else:
            hy = int(body.histogram_year or 0)
            combined = [ok and y == hy for ok, y in zip(keep, years_px)]
    else:
        combined = list(keep)

    prices_f = [p for p, ok in zip(prices_px, combined) if ok]
    if not prices_f:
        raise HTTPException(
            status_code=404, detail="이상치·연도 조건 후 남은 단가 표본이 없습니다."
        )

    arr = np.asarray(prices_f, dtype=float)
    n = int(arr.size)
    req_bins = int(body.bin_count)
    if n == 1:
        v = float(arr[0])
        delta = 0.5 if v == 0 else abs(v) * 0.05
        edges = np.array([v - delta, v + delta], dtype=float)
        counts = np.array([1], dtype=int)
    else:
        n_bins = max(3, min(req_bins, n))
        counts, edges = np.histogram(arr, bins=n_bins)

    bins_out: list[HistogramBin] = []
    for i in range(int(counts.size)):
        bins_out.append(
            HistogramBin(
                bin_from=round(float(edges[i]), 4),
                bin_to=round(float(edges[i + 1]), 4),
                count=int(counts[i]),
            )
        )

    return MatrixCellHistogramResponse(
        zone_type=body.zone_type.strip(),
        land_category=body.land_category.strip(),
        n=n,
        exclude_outlier=bool(body.exclude_outlier),
        outlier_iqr_multiplier=float(body.outlier_iqr_multiplier),
        histogram_scope=body.histogram_scope,
        histogram_year=(
            int(body.histogram_year)
            if body.histogram_scope == "single" and not rolling_single
            else None
        ),
        histogram_bucket_index=h_bucket_index if rolling_single else None,
        histogram_period_start=hist_ps if rolling_single else None,
        histogram_period_end=hist_pe if rolling_single else None,
        bins=bins_out,
    )


@router.post(
    "/matrix-cell-transactions",
    response_model=MatrixCellTransactionsResponse,
    summary="매트릭스 칸 원거래 목록(페이지)",
)
def matrix_cell_transactions(
    body: MatrixCellTransactionsRequest, db: Session = Depends(get_db)
):
    """
    matrix-yearly 와 동일 필터·이상치 정책을 적용한 뒤, 남은 행을 최신 계약 순으로 정렬해
    offset/limit 으로 잘라 반환한다.
    """
    merged_where, merged_params = _matrix_cell_merged_where(body, db)
    query = text(
        f"""
        SELECT lt.id, lt.contract_year, lt.contract_month, lt.beopjungri_code,
               TRIM(BOTH FROM COALESCE(rc.beopjungri_name::text, '')) AS beopjungri_name,
               lt.area_sqm::float8 AS area_sqm,
               lt.total_price_10k::float8 AS total_price_10k,
               lt.unit_price_per_sqm::float8 AS unit_price_per_sqm,
               TRIM(BOTH FROM COALESCE(lt.road_condition::text, '')) AS road_condition
        FROM land_transactions lt
        LEFT JOIN region_codes rc ON rc.beopjungri_code = lt.beopjungri_code
        WHERE {merged_where}
        ORDER BY lt.contract_year ASC, lt.contract_month ASC, lt.id ASC
        """
    )
    rows = db.execute(query, merged_params).fetchall()
    if not rows:
        raise HTTPException(status_code=404, detail="해당 상세 칸에는 거래가 없습니다.")

    candidates: list[dict] = []
    prices_px: list[float] = []
    for row in rows:
        m = row._mapping
        px = m["unit_price_per_sqm"]
        if px is None:
            continue
        fv = float(px)
        nm = (m.get("beopjungri_name") or "").strip()
        rd = (m.get("road_condition") or "").strip()
        candidates.append(
            {
                "id": int(m["id"]),
                "contract_year": int(m["contract_year"]),
                "contract_month": int(m["contract_month"]),
                "beopjungri_code": str(m["beopjungri_code"]).strip(),
                "beopjungri_name": nm or None,
                "area_sqm": float(m["area_sqm"]) if m["area_sqm"] is not None else None,
                "total_price_10k": float(m["total_price_10k"]),
                "unit_price_per_sqm": fv,
                "road_condition": rd or None,
            }
        )
        prices_px.append(fv)

    if body.exclude_outlier:
        keep = outlier_keep_mask(
            prices_px, iqr_multiplier=float(body.outlier_iqr_multiplier)
        )
    else:
        keep = [True] * len(candidates)

    filtered = [c for c, ok in zip(candidates, keep) if ok]
    if not filtered:
        raise HTTPException(
            status_code=404, detail="이상치 제외 후 남은 거래가 없습니다."
        )

    filtered.sort(
        key=lambda x: (-x["contract_year"], -x["contract_month"], -x["id"])
    )
    total = len(filtered)
    off = int(body.offset)
    lim = int(body.limit)
    page = filtered[off : off + lim]
    items = [
        MatrixCellTransactionItem(
            id=c["id"],
            contract_year=c["contract_year"],
            contract_month=c["contract_month"],
            beopjungri_code=c["beopjungri_code"],
            beopjungri_name=c["beopjungri_name"],
            area_sqm=c["area_sqm"],
            total_price_10k=c["total_price_10k"],
            unit_price_per_sqm=c["unit_price_per_sqm"],
            road_condition=c["road_condition"],
        )
        for c in page
    ]

    return MatrixCellTransactionsResponse(
        zone_type=body.zone_type.strip(),
        land_category=body.land_category.strip(),
        total=total,
        offset=off,
        limit=lim,
        exclude_outlier=bool(body.exclude_outlier),
        outlier_iqr_multiplier=float(body.outlier_iqr_multiplier),
        items=items,
    )
