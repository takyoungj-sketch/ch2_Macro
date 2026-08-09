"""집합상가·집합공장 cluster API."""

from __future__ import annotations

from datetime import date
from typing import Optional

import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session

from app.collective.asset_scope import COMMERCIAL_ASSET_TYPES, apply_asset_type_filter
from app.collective.meta_cache import get_ttl_cached
from app.collective.building_stats_query import stats_as_of_label, stats_reference_date
from app.v2_stats_windows import period_bounds_for_window
from app.collective_commercial.cluster_stats_query import (
    cluster_rolling_from_mart,
    cluster_rolling_live,
    cluster_yearly_resolved,
    latest_mart_snapshot,
    list_clusters_from_mart,
    list_clusters_live,
)
from app.collective.analysis_explain import (
    build_commercial_regression_explain,
    build_residential_floor_index_explain,
)
from app.collective.analysis_gates import count_recent_transactions, evaluate_analysis_gates
from app.collective.db import get_collective_db
from app.collective.floor_index_regression import compute_residential_floor_index_regression
from app.collective.schemas import AnalysisExplain, AnalysisFeatures, FloorIndexCell
from app.collective.filters import _col, apply_region_filters
from app.flat_sido_region import list_addr2_for_sido
from app.region_sido import list_sido_names
from app.collective_commercial.tx_rows import apply_commercial_tx_period, commercial_tx_row_dict
from app.collective.region_structure import detect_region_structure
from app.collective.resolve_codes import resolve_collective_map_codes
from app.collective.schemas import CollectiveMapResolveCodesResponse, RegionOption, RegionStructureResponse
from app.collective_commercial.road_geocode import (
    geocode_commercial_road,
    resolve_commercial_map_points,
)
from app.collective_commercial.schemas import (
    CommercialAddressListResponse,
    CommercialAddressRow,
    CommercialClusterListResponse,
    CommercialFilterMeta,
    CommercialFloorIndexResponse,
    CommercialHistogramBin,
    CommercialHistogramResponse,
    CommercialRegressionPredictRequest,
    CommercialRegressionPredictResponse,
    CommercialRegressionRequest,
    CommercialRegressionResponse,
    CommercialRoadGeocodeRequest,
    CommercialRoadGeocodeResponse,
    CommercialRoadMapPointsRequest,
    CommercialRoadMapPointsResponse,
    CommercialRollingStatPoint,
    CommercialRollingStatsResponse,
    CommercialTransactionListResponse,
    CommercialTransactionRow,
    CommercialYearlyStatPoint,
    CommercialYearlyStatsResponse,
)
from app.config import settings
from app.stats_utils import compute_stats

from app.collective_commercial.regression.engine import predict_commercial_regression, run_commercial_regression

router = APIRouter(prefix="/commercial", tags=["집합상가·공장"])


def _tx_where(
    *,
    conn: Connection | None = None,
    asset_type: Optional[str] = None,
    addr1: Optional[str] = None,
    addr2: Optional[str] = None,
    addr3: Optional[str] = None,
    addr3_list: list[str] | None = None,
    addr4_list: list[str] | None = None,
    contract_year_from: Optional[int] = None,
    contract_year_to: Optional[int] = None,
    contract_date_from: Optional[date] = None,
    contract_date_to: Optional[date] = None,
    window_years: Optional[int] = None,
    col_prefix: str = "",
) -> tuple[str, dict]:
    p = col_prefix
    valid_sql = f"{p}.is_valid = true" if p else "is_valid = true"
    clauses = [
        valid_sql,
        f"{_col('unit_price', p)} IS NOT NULL",
        f"{_col('unit_price', p)} > 0",
    ]
    params: dict = {}
    apply_asset_type_filter(
        clauses, params, asset_type, allowed=COMMERCIAL_ASSET_TYPES, col_prefix=p
    )
    apply_region_filters(
        clauses,
        params,
        conn=conn,
        table="collective_commercial_transactions",
        addr1=addr1,
        addr2=addr2,
        addr3=addr3,
        addr3_list=addr3_list,
        addr4_list=addr4_list,
        asset_type=asset_type,
        col_prefix=p,
        valid_sql=valid_sql,
    )
    apply_commercial_tx_period(
        conn,
        clauses,
        params,
        window_years=window_years,
        contract_year_from=contract_year_from,
        contract_year_to=contract_year_to,
        contract_date_from=contract_date_from,
        contract_date_to=contract_date_to,
        col_prefix=p,
    )
    return " AND ".join(clauses), params


def _cluster_display_label(db: Session, cluster_key: str) -> str:
    row = db.execute(
        text(
            """
            SELECT COALESCE(MAX(c.display_label), MAX(t.road_name), :ck) AS label
            FROM collective_commercial_transactions t
            LEFT JOIN commercial_clusters c ON c.id = t.cluster_id
            WHERE t.cluster_key = :ck
            """
        ),
        {"ck": cluster_key},
    ).fetchone()
    return row.label if row and row.label else cluster_key


@router.get("/regions/addr1", response_model=list[str])
def list_addr1(db: Session = Depends(get_collective_db)):
    """시도 목록 — region_codes SSOT (원장 스캔 없음)."""
    return list_sido_names(db.connection())


@router.get("/meta/filters", response_model=CommercialFilterMeta)
def filter_meta(db: Session = Depends(get_collective_db)):
    def _years() -> list[int]:
        rows = db.execute(
            text(
                """
                SELECT DISTINCT contract_year AS y FROM collective_commercial_transactions
                WHERE contract_year IS NOT NULL ORDER BY 1
                """
            )
        ).fetchall()
        return [int(r.y) for r in rows]

    def _types() -> list:
        rows = db.execute(
            text(
                """
                SELECT DISTINCT asset_type AS v FROM collective_commercial_transactions
                WHERE asset_type IS NOT NULL ORDER BY 1
                """
            )
        ).fetchall()
        return [r.v for r in rows]

    return CommercialFilterMeta(
        asset_types=get_ttl_cached("comm:asset_types", _types),
        contract_years=get_ttl_cached("comm:years", _years),
        addr1_list=list_sido_names(db.connection()),
    )


@router.get("/regions/addr2")
def list_addr2(
    db: Session = Depends(get_collective_db),
    addr1: str = Query(...),
    asset_type: Optional[str] = Query(None),
):
    return list_addr2_for_sido(
        db.connection(),
        table="collective_commercial_transactions",
        addr1=addr1,
        asset_type=asset_type,
        valid_sql="is_valid = true",
    )


@router.get("/regions/addr3")
def list_addr3(
    db: Session = Depends(get_collective_db),
    addr1: str = Query(...),
    addr2: str = Query(...),
    asset_type: Optional[str] = Query(None),
    contract_year_from: Optional[int] = None,
    contract_year_to: Optional[int] = None,
    contract_date_from: Optional[date] = None,
    contract_date_to: Optional[date] = None,
    window_years: Optional[int] = Query(None, ge=1, le=5),
):
    conn = db.connection()
    where, params = _tx_where(
        conn=conn,
        asset_type=asset_type,
        addr1=addr1,
        addr2=addr2,
        contract_year_from=contract_year_from,
        contract_year_to=contract_year_to,
        contract_date_from=contract_date_from,
        contract_date_to=contract_date_to,
        window_years=window_years,
    )
    rows = db.execute(
        text(
            f"""
            SELECT addr3 AS name, COUNT(*)::int AS count
            FROM collective_commercial_transactions
            WHERE {where} AND addr3 IS NOT NULL AND btrim(addr3) <> ''
            GROUP BY addr3
            ORDER BY count DESC, addr3
            """
        ),
        params,
    ).mappings().all()
    return [dict(r) for r in rows]


@router.get("/regions/structure", response_model=RegionStructureResponse)
def region_structure(
    db: Session = Depends(get_collective_db),
    addr1: str = Query(...),
    addr2: str = Query(...),
    asset_type: Optional[str] = Query(None),
):
    info = detect_region_structure(
        db.connection(),
        addr1,
        addr2,
        asset_type,
        table="collective_commercial_transactions",
    )
    return RegionStructureResponse(**info)


@router.get("/regions/leaf", response_model=list[RegionOption])
def list_leaf_regions(
    db: Session = Depends(get_collective_db),
    addr1: str = Query(...),
    addr2: str = Query(...),
    addr3_list: list[str] = Query(default=[]),
    asset_type: Optional[str] = Query(None),
    contract_year_from: Optional[int] = None,
    contract_year_to: Optional[int] = None,
    contract_date_from: Optional[date] = None,
    contract_date_to: Optional[date] = None,
    window_years: Optional[int] = Query(None, ge=1, le=5),
):
    conn = db.connection()
    where, params = _tx_where(
        conn=conn,
        asset_type=asset_type,
        addr1=addr1,
        addr2=addr2,
        addr3_list=addr3_list or None,
        contract_year_from=contract_year_from,
        contract_year_to=contract_year_to,
        contract_date_from=contract_date_from,
        contract_date_to=contract_date_to,
        window_years=window_years,
    )
    rows = db.execute(
        text(
            f"""
            SELECT addr4 AS name, addr3 AS parent, COUNT(*)::int AS count
            FROM collective_commercial_transactions
            WHERE {where}
              AND addr4 IS NOT NULL AND btrim(addr4::text) <> ''
            GROUP BY addr4, addr3
            ORDER BY addr3, addr4
            """
        ),
        params,
    ).mappings().all()
    return [RegionOption(**dict(r)) for r in rows]


@router.get("/regions/resolve-codes", response_model=CollectiveMapResolveCodesResponse)
def resolve_region_codes_for_map(
    db: Session = Depends(get_collective_db),
    asset_type: Optional[str] = Query(None),
    addr1: Optional[str] = Query(None),
    addr2: Optional[str] = Query(None),
    gu: list[str] = Query(default=[], description="구(addr3) 이름"),
    leaf: list[str] = Query(default=[], description="읍·면·동 이름"),
):
    """좌측 addr 칩 → VWorld 지도용 행정코드 (집합상가·공장)."""
    result = resolve_collective_map_codes(
        db.connection(),
        asset_type=asset_type,
        addr1=addr1,
        addr2=addr2,
        gu_list=gu,
        leaf_list=leaf,
        table="collective_commercial_transactions",
    )
    return CollectiveMapResolveCodesResponse(**result)


@router.post("/roads/geocode", response_model=CommercialRoadGeocodeResponse)
def geocode_road_for_map(body: CommercialRoadGeocodeRequest):
    """선택 도로(cluster) 지오코딩 라벨 (Road-B · VWorld Search)."""
    key = (settings.vworld_api_key or "").strip()
    if not key:
        raise HTTPException(
            status_code=503,
            detail="VWORLD_API_KEY가 설정되지 않았습니다.",
        )
    result = geocode_commercial_road(
        api_key=key,
        addr1=body.addr1,
        addr2=body.addr2,
        addr3=body.addr3,
        addr4=body.addr4,
        road_name=body.road_name,
    )
    label = (body.label or body.road_name or "").strip() or None
    return CommercialRoadGeocodeResponse(
        ok=bool(result.get("ok")),
        query=str(result.get("query") or ""),
        longitude=result.get("longitude"),
        latitude=result.get("latitude"),
        matched_name=result.get("matched_name"),
        category=result.get("category"),
        label=label,
        cluster_key=body.cluster_key,
        error=result.get("error"),
    )


@router.post("/roads/map-points", response_model=CommercialRoadMapPointsResponse)
def map_points_for_roads(
    body: CommercialRoadMapPointsRequest,
    db: Session = Depends(get_collective_db),
):
    """선택 지역 도로명 cluster 대표점 — 지오코딩 결과는 DB에 캐시."""
    if db is None:
        raise HTTPException(503, "collective_stats DB 미연결")
    key = (settings.vworld_api_key or "").strip()
    if not key:
        raise HTTPException(503, "VWORLD_API_KEY가 설정되지 않았습니다.")
    try:
        points, unresolved = resolve_commercial_map_points(
            db.connection(),
            api_key=key,
            roads=[item.model_dump() for item in body.roads],
        )
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc
    return CommercialRoadMapPointsResponse(points=points, unresolved=unresolved)


@router.get("/clusters", response_model=CommercialClusterListResponse)
def list_clusters(
    db: Session = Depends(get_collective_db),
    asset_type: Optional[str] = Query(None),
    addr1: Optional[str] = None,
    addr2: Optional[str] = None,
    addr3_list: list[str] = Query(default=[]),
    addr4_list: list[str] = Query(default=[]),
    contract_year_from: Optional[int] = None,
    contract_year_to: Optional[int] = None,
    window_years: int = Query(5, ge=1, le=5),
    sort: str = Query("count", pattern="^(count|mean|display_label)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500),
):
    if not addr2:
        raise HTTPException(400, "시군구(addr2)를 선택해 주세요.")
    if (
        contract_year_from is not None
        and contract_year_to is not None
        and contract_year_from > contract_year_to
    ):
        raise HTTPException(400, "연도(from)는 연도(to) 이하여야 합니다.")

    conn = db.connection()
    as_of_month, _ = latest_mart_snapshot(conn)
    meta: dict = {"data_source": "live", "window_years": window_years}

    mart = list_clusters_from_mart(
        conn,
        asset_type=asset_type,
        addr1=addr1,
        addr2=addr2,
        addr3_list=addr3_list or None,
        addr4_list=addr4_list or None,
        window_years=window_years,
        as_of_month=as_of_month,
        contract_year_from=contract_year_from,
        contract_year_to=contract_year_to,
    )
    if mart is not None:
        items, meta = mart
    else:
        where, params = _tx_where(
            conn=conn,
            asset_type=asset_type,
            addr1=addr1,
            addr2=addr2,
            addr3_list=addr3_list or None,
            addr4_list=addr4_list or None,
            contract_year_from=contract_year_from,
            contract_year_to=contract_year_to,
            col_prefix="t",
        )
        items = list_clusters_live(conn, where, params)

    if sort == "mean":
        items.sort(key=lambda x: (x.mean is None, -(x.mean or 0), x.asset_type or ""))
    elif sort == "display_label":
        items.sort(key=lambda x: (x.display_label, x.asset_type or ""))
    else:
        items.sort(key=lambda x: (-x.count, x.asset_type or ""))

    total = len(items)
    start = (page - 1) * page_size
    page_items = items[start : start + page_size]
    if as_of_month is not None:
        ps, pe = period_bounds_for_window(as_of_month, window_years)
        meta.setdefault("period_start", ps.isoformat())
        meta.setdefault("period_end", pe.isoformat())
        if meta.get("data_source") == "live":
            meta.setdefault("stats_as_of_label", stats_as_of_label(as_of_month))
            meta.setdefault("stats_reference_date", stats_reference_date(as_of_month).isoformat())
            meta.setdefault("as_of_month", as_of_month.isoformat())
    return CommercialClusterListResponse(
        total=total,
        items=page_items,
        data_source=meta.get("data_source", "live"),
        as_of_month=meta.get("as_of_month"),
        stats_reference_date=meta.get("stats_reference_date"),
        stats_as_of_label=meta.get("stats_as_of_label"),
        window_years=meta.get("window_years", window_years),
        period_start=meta.get("period_start"),
        period_end=meta.get("period_end"),
    )


@router.get("/clusters/{cluster_key}/addresses", response_model=CommercialAddressListResponse)
def list_cluster_addresses(
    cluster_key: str,
    db: Session = Depends(get_collective_db),
    addr1: Optional[str] = None,
    addr2: Optional[str] = None,
    addr3_list: list[str] = Query(default=[]),
    addr4_list: list[str] = Query(default=[]),
    contract_year_from: Optional[int] = None,
    contract_year_to: Optional[int] = None,
):
    """도로(cluster) 내 번지·읍면동별 ㎡당 단가 — 목록 조회와 동일 지역 필터 적용."""
    where, params = _tx_where(
        conn=db.connection(),
        addr1=addr1,
        addr2=addr2,
        addr3_list=addr3_list or None,
        addr4_list=addr4_list or None,
        contract_year_from=contract_year_from,
        contract_year_to=contract_year_to,
        col_prefix="t",
    )
    params["cluster_key"] = cluster_key
    rows = db.execute(
        text(
            f"""
            SELECT COALESCE(NULLIF(btrim(t.lot_number::text), ''), '번지 미상') AS lot_number,
                   MAX(t.addr3) AS addr3,
                   MAX(t.addr4) AS addr4,
                   MAX(t.road_name) AS road_name,
                   array_agg(t.unit_price ORDER BY t.unit_price) AS prices
            FROM collective_commercial_transactions t
            WHERE t.cluster_key = :cluster_key AND {where}
            GROUP BY COALESCE(NULLIF(btrim(t.lot_number::text), ''), '번지 미상'), t.addr4
            ORDER BY COUNT(*) DESC, lot_number
            """
        ),
        params,
    ).mappings().all()

    items: list[CommercialAddressRow] = []
    road_name = None
    for r in rows:
        if road_name is None and r["road_name"]:
            road_name = r["road_name"]
        prices = [float(x) for x in (r["prices"] or []) if x is not None]
        st = compute_stats(prices)
        items.append(
            CommercialAddressRow(
                lot_number=r["lot_number"],
                addr3=r["addr3"],
                addr4=r["addr4"],
                count=st["count"],
                mean=st["mean"],
                median=st["median"],
                ci_lower=st["ci_lower"],
                ci_upper=st["ci_upper"],
                is_reliable=st["count"] >= 15,
            )
        )
    return CommercialAddressListResponse(
        cluster_key=cluster_key,
        road_name=road_name,
        total=len(items),
        items=items,
    )


@router.get("/clusters/{cluster_key}/stats/rolling", response_model=CommercialRollingStatsResponse)
def cluster_stats_rolling(
    cluster_key: str,
    db: Session = Depends(get_collective_db),
    window_years: int = Query(5, ge=1, le=5),
):
    conn = db.connection()
    as_of_month, _ = latest_mart_snapshot(conn)
    mart = cluster_rolling_from_mart(
        conn, cluster_key, window_years=window_years, as_of_month=as_of_month
    )
    if mart is not None:
        display_label, points, data_source = mart
        return CommercialRollingStatsResponse(
            cluster_key=cluster_key,
            display_label=display_label,
            window_years=window_years,
            as_of_month=as_of_month.isoformat() if as_of_month else None,
            stats_as_of_label=stats_as_of_label(as_of_month),
            points=[CommercialRollingStatPoint(**p) for p in points],
            data_source=data_source,
        )

    live = cluster_rolling_live(
        conn, cluster_key, window_years=window_years, as_of_month=as_of_month
    )
    if live is not None:
        display_label, points, data_source = live
        return CommercialRollingStatsResponse(
            cluster_key=cluster_key,
            display_label=display_label,
            window_years=window_years,
            as_of_month=as_of_month.isoformat() if as_of_month else None,
            stats_as_of_label=stats_as_of_label(as_of_month),
            points=[CommercialRollingStatPoint(**p) for p in points],
            data_source=data_source,
        )

    return CommercialRollingStatsResponse(
        cluster_key=cluster_key,
        display_label=_cluster_display_label(db, cluster_key),
        window_years=window_years,
        points=[],
        data_source="live",
    )


@router.get("/clusters/{cluster_key}/stats/by-year", response_model=CommercialYearlyStatsResponse)
def cluster_stats_by_year(
    cluster_key: str,
    db: Session = Depends(get_collective_db),
    addr1: Optional[str] = None,
    addr2: Optional[str] = None,
    addr3_list: list[str] = Query(default=[]),
    addr4_list: list[str] = Query(default=[]),
    contract_year_from: Optional[int] = None,
    contract_year_to: Optional[int] = None,
):
    conn = db.connection()
    scoped = any(
        [
            addr1,
            addr2,
            addr3_list,
            addr4_list,
            contract_year_from is not None,
            contract_year_to is not None,
        ]
    )
    if not scoped:
        resolved = cluster_yearly_resolved(conn, cluster_key)
        if resolved is not None:
            display_label, points, data_source = resolved
            return CommercialYearlyStatsResponse(
                cluster_key=cluster_key,
                display_label=display_label,
                points=[CommercialYearlyStatPoint(**p) for p in points],
                data_source=data_source,
            )

    where, params = _tx_where(
        conn=db.connection(),
        addr1=addr1,
        addr2=addr2,
        addr3_list=addr3_list or None,
        addr4_list=addr4_list or None,
        contract_year_from=contract_year_from,
        contract_year_to=contract_year_to,
    )
    params["cluster_key"] = cluster_key
    rows = db.execute(
        text(
            f"""
            SELECT contract_year AS year,
                   COUNT(*)::int AS count,
                   AVG(unit_price)::float AS mean,
                   PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY unit_price)::float AS median
            FROM collective_commercial_transactions
            WHERE cluster_key = :cluster_key AND {where}
              AND contract_year IS NOT NULL
            GROUP BY contract_year
            ORDER BY contract_year
            """
        ),
        params,
    ).mappings().all()
    points = [
        CommercialYearlyStatPoint(
            year=int(r["year"]),
            count=int(r["count"]),
            mean=round(float(r["mean"]), 1) if r["mean"] is not None else None,
            median=round(float(r["median"]), 1) if r.get("median") is not None else None,
        )
        for r in rows
    ]
    return CommercialYearlyStatsResponse(
        cluster_key=cluster_key,
        display_label=_cluster_display_label(db, cluster_key),
        points=points,
        data_source="live",
    )


@router.get("/clusters/{cluster_key}/histogram", response_model=CommercialHistogramResponse)
def cluster_histogram(
    cluster_key: str,
    db: Session = Depends(get_collective_db),
    addr1: Optional[str] = None,
    addr2: Optional[str] = None,
    addr3_list: list[str] = Query(default=[]),
    addr4_list: list[str] = Query(default=[]),
    contract_year_from: Optional[int] = None,
    contract_year_to: Optional[int] = None,
    bins: int = Query(12, ge=4, le=40),
    contract_year: Optional[int] = None,
):
    where, params = _tx_where(
        conn=db.connection(),
        addr1=addr1,
        addr2=addr2,
        addr3_list=addr3_list or None,
        addr4_list=addr4_list or None,
        contract_year_from=contract_year_from,
        contract_year_to=contract_year_to,
    )
    params["cluster_key"] = cluster_key
    if contract_year is not None:
        where = f"{where} AND contract_year = :hist_year"
        params["hist_year"] = contract_year
    rows = db.execute(
        text(
            f"""
            SELECT unit_price FROM collective_commercial_transactions
            WHERE cluster_key = :cluster_key AND {where}
            """
        ),
        params,
    ).fetchall()
    prices = [float(r[0]) for r in rows if r[0] is not None]
    if not prices:
        return CommercialHistogramResponse(
            cluster_key=cluster_key, bins=[], n=0, contract_year=contract_year
        )
    lo, hi = min(prices), max(prices)
    if lo == hi:
        return CommercialHistogramResponse(
            cluster_key=cluster_key,
            bins=[CommercialHistogramBin(lo=lo, hi=hi, count=len(prices))],
            n=len(prices),
            contract_year=contract_year,
        )
    edges = np.linspace(lo, hi, bins + 1)
    counts, _ = np.histogram(prices, bins=edges)
    out = [
        CommercialHistogramBin(
            lo=round(float(edges[i]), 1),
            hi=round(float(edges[i + 1]), 1),
            count=int(counts[i]),
        )
        for i in range(len(counts))
        if counts[i] > 0
    ]
    return CommercialHistogramResponse(
        cluster_key=cluster_key,
        bins=out,
        n=len(prices),
        contract_year=contract_year,
    )


@router.post("/clusters/{cluster_key}/regression/run", response_model=CommercialRegressionResponse)
def cluster_regression(
    cluster_key: str,
    body: CommercialRegressionRequest,
    db: Session = Depends(get_collective_db),
):
    import pandas as pd

    where, params = _tx_where(
        conn=db.connection(),
        addr1=body.addr1,
        addr2=body.addr2,
        addr3_list=body.addr3_list or None,
        addr4_list=body.addr4_list or None,
        contract_year_from=body.contract_year_from,
        contract_year_to=body.contract_year_to,
    )
    params["cluster_key"] = cluster_key
    rows = db.execute(
        text(
            f"""
            SELECT price, unit_price, gross_area, land_area, building_age, building_year, floor,
                   zone_type, building_use, road_width_label, road_code, addr4, contract_year,
                   asset_type
            FROM collective_commercial_transactions
            WHERE cluster_key = :cluster_key AND {where}
            """
        ),
        params,
    ).mappings().all()
    if not rows:
        raise HTTPException(404, "해당 cluster 거래가 없습니다.")

    years = [int(r["contract_year"]) for r in rows if r.get("contract_year") is not None]
    gates = evaluate_analysis_gates(
        len(rows),
        count_recent_transactions(
            years,
            contract_year_from=body.contract_year_from,
            contract_year_to=body.contract_year_to,
        ),
    )
    if not gates.regression_eligible and not body.experiment:
        raise HTTPException(
            403,
            detail="; ".join(gates.messages) if gates.messages else "회귀 분석 최소 표본 미달",
        )

    asset_type = rows[0].get("asset_type") or ""
    is_shop = asset_type == "collective_shop"
    display_label = _cluster_display_label(db, cluster_key)
    df = pd.DataFrame(rows)
    result = run_commercial_regression(
        df,
        cluster_key,
        display_label,
        body,
        is_shop=is_shop,
    )
    return result.model_copy(
        update={
            "explain": AnalysisExplain(
                **build_commercial_regression_explain(result, body, is_shop=is_shop),
            ),
        }
    )


@router.post("/clusters/{cluster_key}/regression/predict", response_model=CommercialRegressionPredictResponse)
def cluster_regression_predict(
    cluster_key: str,
    body: CommercialRegressionPredictRequest,
    db: Session = Depends(get_collective_db),
):
    import pandas as pd

    where, params = _tx_where(
        conn=db.connection(),
        addr1=body.addr1,
        addr2=body.addr2,
        addr3_list=body.addr3_list or None,
        addr4_list=body.addr4_list or None,
        contract_year_from=body.contract_year_from,
        contract_year_to=body.contract_year_to,
    )
    params["cluster_key"] = cluster_key
    rows = db.execute(
        text(
            f"""
            SELECT price, unit_price, gross_area, land_area, building_age, building_year, floor,
                   zone_type, building_use, road_width_label, road_code, addr4, contract_year,
                   asset_type
            FROM collective_commercial_transactions
            WHERE cluster_key = :cluster_key AND {where}
            """
        ),
        params,
    ).mappings().all()
    if not rows:
        raise HTTPException(404, "해당 cluster 거래가 없습니다.")

    years = [int(r["contract_year"]) for r in rows if r.get("contract_year") is not None]
    gates = evaluate_analysis_gates(
        len(rows),
        count_recent_transactions(
            years,
            contract_year_from=body.contract_year_from,
            contract_year_to=body.contract_year_to,
        ),
    )
    if not gates.regression_eligible and not body.experiment:
        raise HTTPException(
            403,
            detail="; ".join(gates.messages) if gates.messages else "회귀 예측 최소 표본 미달",
        )

    asset_type = rows[0].get("asset_type") or ""
    is_shop = asset_type == "collective_shop"
    df = pd.DataFrame(rows)
    try:
        raw = predict_commercial_regression(df, body, body.inputs, is_shop=is_shop)
    except ValueError as exc:
        raise HTTPException(400, detail=str(exc)) from exc
    return CommercialRegressionPredictResponse(**raw)


@router.get("/clusters/{cluster_key}/floor-index", response_model=CommercialFloorIndexResponse)
def cluster_floor_index(
    cluster_key: str,
    db: Session = Depends(get_collective_db),
    addr1: Optional[str] = None,
    addr2: Optional[str] = None,
    addr3_list: list[str] = Query(default=[]),
    addr4_list: list[str] = Query(default=[]),
    contract_year_from: Optional[int] = None,
    contract_year_to: Optional[int] = None,
    dimension: str = Query("floor", pattern="^(floor|area)$"),
    floor_mode: str = Query("relative", pattern="^(relative|dummy|grouped)$"),
    experiment: bool = Query(False, description="표본 게이트 우회"),
):
    import pandas as pd

    where, params = _tx_where(
        conn=db.connection(),
        addr1=addr1,
        addr2=addr2,
        addr3_list=addr3_list or None,
        addr4_list=addr4_list or None,
        contract_year_from=contract_year_from,
        contract_year_to=contract_year_to,
    )
    params["cluster_key"] = cluster_key
    rows = db.execute(
        text(
            f"""
            SELECT unit_price, floor, gross_area, contract_year, contract_month,
                   building_year, building_age, building_use, area_bucket_label, asset_type
            FROM collective_commercial_transactions
            WHERE cluster_key = :cluster_key AND {where}
            """
        ),
        params,
    ).mappings().all()
    if not rows:
        raise HTTPException(404, "해당 cluster 거래가 없습니다.")

    years = [int(r["contract_year"]) for r in rows if r.get("contract_year") is not None]
    gates = evaluate_analysis_gates(
        len(rows),
        count_recent_transactions(
            years,
            contract_year_from=contract_year_from,
            contract_year_to=contract_year_to,
        ),
    )
    if not gates.floor_index_eligible and not experiment:
        raise HTTPException(
            403,
            detail=gates.messages[0] if gates.messages else "효용지수 분석 최소 표본 미달",
        )

    df = pd.DataFrame(rows)
    df["exclusive_area"] = df["gross_area"]
    asset_type = rows[0].get("asset_type") or "collective_shop"
    display_label = _cluster_display_label(db, cluster_key)

    raw = compute_residential_floor_index_regression(
        df,
        asset_type=asset_type,
        dimension=dimension,
        floor_mode=floor_mode if dimension == "floor" else "relative",
    )
    if asset_type == "collective_factory" and dimension == "floor":
        raw["warnings"] = list(raw.get("warnings") or []) + [
            "집합공장은 층 정보가 일부만 있을 수 있습니다 — 면적형 탭과 함께 참고하세요."
        ]

    cells = [FloorIndexCell(**c) for c in raw["cells"]]
    explain = AnalysisExplain(
        **build_residential_floor_index_explain(
            raw=raw,
            asset_type=asset_type,
            scope_kind="cluster",
        )
    )
    return CommercialFloorIndexResponse(
        cluster_key=cluster_key,
        display_label=display_label,
        asset_type=asset_type,
        dimension=raw["dimension"],
        method=raw.get("method", "regression_semilog"),
        floor_mode=raw.get("floor_mode"),
        reference_floor=raw.get("reference_floor"),
        regression_reference_floor=raw.get("regression_reference_floor"),
        controls=raw.get("controls") or [],
        n_total=raw["n_total"],
        n_regression=raw.get("n_regression"),
        r_squared=raw.get("r_squared"),
        baseline_median=raw.get("baseline_median"),
        cells=cells,
        warnings=raw.get("warnings") or [],
        explain=explain,
        diagnostics=raw.get("diagnostics"),
        analysis=AnalysisFeatures(
            floor_index=gates.floor_index_eligible,
            regression=gates.regression_eligible,
            count_total=gates.count_total,
            count_recent=gates.count_recent,
            messages=gates.messages,
        ),
    )


@router.get("/clusters/{cluster_key}/transactions", response_model=CommercialTransactionListResponse)
def list_cluster_transactions(
    cluster_key: str,
    db: Session = Depends(get_collective_db),
    addr1: Optional[str] = None,
    addr2: Optional[str] = None,
    addr3_list: list[str] = Query(default=[]),
    addr4_list: list[str] = Query(default=[]),
    contract_year_from: Optional[int] = None,
    contract_year_to: Optional[int] = None,
    contract_date_from: Optional[date] = None,
    contract_date_to: Optional[date] = None,
    window_years: Optional[int] = Query(None, ge=1, le=5),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    conn = db.connection()
    where, params = _tx_where(
        conn=conn,
        addr1=addr1,
        addr2=addr2,
        addr3_list=addr3_list or None,
        addr4_list=addr4_list or None,
        contract_year_from=contract_year_from,
        contract_year_to=contract_year_to,
        contract_date_from=contract_date_from,
        contract_date_to=contract_date_to,
        window_years=window_years,
    )
    params["cluster_key"] = cluster_key
    total = db.execute(
        text(
            f"""
            SELECT COUNT(*) FROM collective_commercial_transactions
            WHERE cluster_key = :cluster_key AND {where}
            """
        ),
        params,
    ).scalar() or 0
    offset = (page - 1) * page_size
    params["limit"] = page_size
    params["offset"] = offset
    rows = db.execute(
        text(
            f"""
            SELECT id, asset_type, cluster_key, addr3, addr4, lot_number,
                   contract_year, contract_month, contract_date, price, gross_area, land_area,
                   unit_price, floor, building_year, building_age,
                   zone_type, building_use, area_bucket_label, road_name,
                   road_code, road_width_label
            FROM collective_commercial_transactions
            WHERE cluster_key = :cluster_key AND {where}
            ORDER BY contract_date DESC NULLS LAST, contract_year DESC NULLS LAST, contract_month DESC NULLS LAST, id DESC
            LIMIT :limit OFFSET :offset
            """
        ),
        params,
    ).mappings().all()
    items = [CommercialTransactionRow(**commercial_tx_row_dict(r)) for r in rows]
    return CommercialTransactionListResponse(total=int(total), items=items)


from app.collective_commercial.commercial_cohort_router import router as commercial_cohort_router  # noqa: E402

router.include_router(commercial_cohort_router)
