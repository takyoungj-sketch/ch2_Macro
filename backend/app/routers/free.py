"""
무료 통계 API 라우터
- 사전 집계: land_basic_stats (매트릭스·부분합)
- 연도별 요약: land_transactions 집계 (정상 거래만)
"""

from __future__ import annotations

from itertools import product

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.analysis_base_cache import create_analysis_base_cache
from app.db import get_db
from app.schemas import (
    FreeStatsBulkRequest,
    FreeStatsResponse,
    MatrixCell,
    RegionItem,
    StatsResult,
    YearlyTradeStat,
)
from app.stats_utils import compute_stats

router = APIRouter(prefix="/free", tags=["무료 통계"])

_MAX_STATS_REGIONS = 200


def _dedupe_codes_preserve(region_codes: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for c in region_codes:
        t = str(c).strip()
        if not t or t in seen:
            continue
        seen.add(t)
        out.append(t)
    return out


def _stats_dict_to_result(st: dict) -> StatsResult:
    return StatsResult(
        count=int(st["count"]),
        mean=st.get("mean"),
        std=st.get("std"),
        ci_lower=st.get("ci_lower"),
        ci_upper=st.get("ci_upper"),
        min=st.get("min"),
        p25=st.get("p25"),
        median=st.get("median"),
        p75=st.get("p75"),
        max=st.get("max"),
        is_reliable=bool(st.get("is_reliable", int(st["count"]) >= 15)),
    )


def _validate_basic_stats_all_rows(db: Session, codes: list[str]) -> None:
    """사전 집계(ALL×ALL) 존재 여부 확인 — 패딩은 btrim."""
    stmt = text(
        """
        SELECT btrim(cast(beopjungri_code AS text)) AS bc
        FROM land_basic_stats
        WHERE btrim(cast(beopjungri_code AS text)) = ANY(:codes)
          AND zone_type = 'ALL' AND land_category = 'ALL'
        """
    )
    rows = db.execute(stmt, {"codes": codes}).fetchall()
    if not rows:
        raise HTTPException(
            status_code=404,
            detail="선택 지역 중 사전 집계 통계가 없는 코드가 포함되어 있습니다.",
        )
    seen = {str(r.bc).strip() for r in rows}
    missing = [c for c in codes if c not in seen]
    if missing:
        raise HTTPException(
            status_code=404,
            detail=(
                "다음 법정코드는 사전 집계 데이터가 없어 합산할 수 없습니다: "
                + ", ".join(missing[:15])
                + (" …" if len(missing) > 15 else "")
            ),
        )


def _overlap_year_window(db: Session, codes: list[str]) -> tuple[int, int]:
    """원장 MIN/MAX(contract_year), is_valid만. 복수 코드는 포함 지역 거래 통합 표본의 최소~최대 연도."""
    _validate_basic_stats_all_rows(db, codes)
    stmt = text(
        """
        SELECT MIN(contract_year)::int AS yf, MAX(contract_year)::int AS yt
        FROM land_transactions
        WHERE is_valid IS TRUE
          AND contract_year IS NOT NULL
          AND btrim(cast(beopjungri_code AS text)) = ANY(:codes)
        """
    )
    row = db.execute(stmt, {"codes": codes}).mappings().one()
    yf, yt = row.get("yf"), row.get("yt")
    if yf is None or yt is None or int(yf) > int(yt):
        raise HTTPException(
            status_code=404,
            detail="선택 지역 조건(is_valid 거래)에 해당하는 거래 데이터가 없습니다.",
        )
    return int(yf), int(yt)


def _combined_bundle_from_transactions(
    db: Session,
    codes: list[str],
    year_from: int,
    year_to: int,
) -> tuple[StatsResult, dict[str, StatsResult], dict[str, StatsResult], list[MatrixCell]]:
    """
    build_stats 와 같은 필터(정상·해제 제외·단가 있음)로 원장을 합산해 매트릭스를 계산한다.
    """
    stmt = text(
        """
        SELECT zone_type, land_category, unit_price_per_sqm::double precision AS up
        FROM land_transactions
        WHERE is_valid = TRUE
          AND is_cancelled = FALSE
          AND unit_price_per_sqm IS NOT NULL
          AND contract_year >= :yf
          AND contract_year <= :yt
          AND btrim(cast(beopjungri_code AS text)) = ANY(:codes)
        """
    )
    raw = db.execute(
        stmt,
        {"codes": codes, "yf": year_from, "yt": year_to},
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
            detail="합산 가능한 거래 단가 데이터가 없습니다. 연도 또는 지역을 조정해 보세요.",
        )

    zones = sorted({t[0] for t in trips})
    cats = sorted({t[1] for t in trips})

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
    for lc in cats:
        d = compute_stats(prices_for("ALL", lc))
        by_land_category[lc] = _stats_dict_to_result(d)

    matrix_list: list[MatrixCell] = []
    for zone, cat in product(zones, cats):
        st = compute_stats(prices_for(zone, cat))
        matrix_list.append(
            MatrixCell(
                zone_type=zone,
                land_category=cat,
                stats=_stats_dict_to_result(st),
            )
        )

    return (total, by_zone, by_land_category, matrix_list)


def _build_region_title(db: Session, codes: list[str]) -> str:
    stmt = text(
        """
        SELECT btrim(cast(beopjungri_code AS text)) AS bc, beopjungri_name
        FROM region_codes
        WHERE btrim(cast(beopjungri_code AS text)) = ANY(:codes)
        """
    )
    rows = db.execute(stmt, {"codes": codes}).fetchall()
    cmap = {str(r.bc).strip(): str(r.beopjungri_name) for r in rows}
    missing = [c for c in codes if c not in cmap]
    if missing:
        raise HTTPException(
            status_code=404,
            detail=f"등록되지 않은 법정동·리 코드가 있습니다: {', '.join(missing[:10])}",
        )
    return ", ".join(cmap[c] for c in codes)


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


@router.post(
    "/stats/bulk",
    response_model=FreeStatsResponse,
    summary="복수 법정동·리 기본 통계 합산",
)
def get_basic_stats_bulk(
    payload: FreeStatsBulkRequest,
    db: Session = Depends(get_db),
):
    """
    무료 화면과 동일 형식으로, 선택한 법정동·리 거래 단가를 하나의 표본으로 묶어 집계한다.
    매트릭스는 원장 재집계(사전 집계와 동일한 필터)·연도별는 정상 거래 합계(해제 포함 정책은 단일 통계와 동일).
    """
    codes = _dedupe_codes_preserve(payload.region_codes)
    if not codes:
        raise HTTPException(status_code=422, detail="유효한 지역 코드가 없습니다.")
    if len(codes) > _MAX_STATS_REGIONS:
        raise HTTPException(
            status_code=422,
            detail=f"한 번에 합산할 수 있는 최대 개수({_MAX_STATS_REGIONS})를 초과했습니다.",
        )

    title = _build_region_title(db, codes)
    year_from, year_to = _overlap_year_window(db, codes)
    analysis_base_key = create_analysis_base_cache(
        db, region_codes=codes, year_from=year_from, year_to=year_to
    )
    total, by_zone, by_land_category, matrix = _combined_bundle_from_transactions(
        db, codes, year_from, year_to
    )

    y_stmt = text(
        """
        SELECT contract_year::int AS y,
               COUNT(*)::int AS cnt,
               COALESCE(SUM(total_price_10k), 0) AS sum_price,
               COALESCE(SUM(area_sqm), 0) AS sum_area
        FROM land_transactions
        WHERE btrim(cast(beopjungri_code AS text)) = ANY(:codes)
          AND is_valid IS TRUE
          AND contract_year >= :yf
          AND contract_year <= :yt
        GROUP BY contract_year
        ORDER BY contract_year
        """
    )
    y_rows = db.execute(
        y_stmt,
        {"codes": codes, "yf": year_from, "yt": year_to},
    ).fetchall()
    y_map = {int(r.y): r for r in y_rows}
    by_year: list[YearlyTradeStat] = []
    for y in range(year_from, year_to + 1):
        rr = y_map.get(y)
        if rr:
            sp = float(rr.sum_price)
            sa = float(rr.sum_area)
            unit = (sp / sa) if sa > 0 else None
            by_year.append(
                YearlyTradeStat(
                    year=y,
                    count=int(rr.cnt),
                    total_price_10k_sum=sp,
                    area_sqm_sum=sa,
                    unit_price_per_sqm=unit,
                )
            )
        else:
            by_year.append(YearlyTradeStat(year=y, count=0))

    return FreeStatsResponse(
        beopjungri_code=",".join(codes),
        beopjungri_name=title,
        year_from=year_from,
        year_to=year_to,
        analysis_base_key=analysis_base_key,
        total=total,
        by_year=by_year,
        by_zone=by_zone,
        by_land_category=by_land_category,
        matrix=matrix,
    )


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

    code_trim = _dedupe_codes_preserve([beopjungri_code])[0]
    year_from, year_to = _overlap_year_window(db, [code_trim])

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
    analysis_base_key = create_analysis_base_cache(
        db,
        region_codes=[code_trim],
        year_from=int(year_from),
        year_to=int(year_to),
    )

    # 연도별 실거래 요약 (기간 내 모든 연도 행 포함, 건수 0 허용)
    y_rows = db.execute(
        text("""
            SELECT contract_year::int AS y,
                   COUNT(*)::int AS cnt,
                   COALESCE(SUM(total_price_10k), 0) AS sum_price,
                   COALESCE(SUM(area_sqm), 0) AS sum_area
            FROM land_transactions
            WHERE btrim(cast(beopjungri_code AS text)) = :code_trim
              AND is_valid IS TRUE
              AND contract_year >= :yf
              AND contract_year <= :yt
            GROUP BY contract_year
            ORDER BY contract_year
        """),
        {"code_trim": code_trim, "yf": year_from, "yt": year_to},
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
        analysis_base_key=analysis_base_key,
        total=total,
        by_year=by_year,
        by_zone=by_zone,
        by_land_category=by_land_category,
        matrix=matrix,
    )
