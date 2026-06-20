"""집합상가·집합공장 cluster API."""

from __future__ import annotations

from datetime import date
from typing import Any, Optional

import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.collective.analysis_explain import (
    build_commercial_floor_index_explain,
    build_commercial_regression_explain,
)
from app.collective.analysis_gates import (
    COMMERCIAL_COHORT_GUIDANCE,
    count_recent_transactions,
    evaluate_analysis_gates,
)
from app.collective.db import get_collective_db
from app.collective.floor_index import compute_floor_index
from app.collective_commercial.floor_index_regression import (
    compute_commercial_area_index_regression,
    compute_shop_floor_index_regression,
)
from app.collective.schemas import AnalysisExplain, AnalysisFeatures, FloorIndexCell
from app.collective.building_stats_query import stats_as_of_label, stats_reference_date
from app.collective.filters import _col, apply_period_filters, apply_region_filters
from app.collective_commercial.cluster_stats_query import (
    cluster_yearly_from_mart,
    fetch_cluster_rolling,
    latest_mart_snapshot,
    list_clusters_mart,
)
from app.collective.region_structure import detect_region_structure
from app.collective.schemas import FloorIndexDiagnostics, RegionOption, RegionStructureResponse
from app.collective_commercial.schemas import (
    CommercialAddressListResponse,
    CommercialAddressRow,
    CommercialClusterListResponse,
    CommercialClusterRow,
    CommercialFilterMeta,
    CommercialFloorIndexResponse,
    CommercialHistogramBin,
    CommercialHistogramResponse,
    CommercialPeerClusterListResponse,
    CommercialPeerClusterRow,
    CommercialRegressionPredictRequest,
    CommercialRegressionPredictResponse,
    CommercialRegressionRequest,
    CommercialRegressionResponse,
    CommercialRollingStatPoint,
    CommercialRollingStatsResponse,
    CommercialTransactionListResponse,
    CommercialTransactionRow,
    CommercialYearlyStatPoint,
    CommercialYearlyStatsResponse,
)
from app.collective_commercial.regression.engine import predict_commercial_regression, run_commercial_regression
from app.collective_commercial.transaction_export import commercial_transactions_csv_bytes
from app.collective.transaction_export import MAX_COLLECTIVE_TX_EXPORT, csv_attachment_response, export_filename
from app.stats_utils import compute_stats
from app.v2_stats_windows import period_bounds_for_window

router = APIRouter(prefix="/commercial", tags=["집합상가·공장"])


def _normalize_asset_type(asset_type: Optional[str]) -> Optional[str]:
    if not asset_type or asset_type == "all":
        return None
    return asset_type


def _tx_where(
    *,
    asset_type: Optional[str] = None,
    addr1: Optional[str] = None,
    addr2: Optional[str] = None,
    addr3: Optional[str] = None,
    addr3_list: list[str] | None = None,
    addr4_list: list[str] | None = None,
    contract_date_from: Optional[date] = None,
    contract_date_to: Optional[date] = None,
    contract_year_from: Optional[int] = None,
    contract_year_to: Optional[int] = None,
    col_prefix: str = "",
) -> tuple[str, dict]:
    p = col_prefix
    clauses = [
        f"{_col('is_valid', p)} = true",
        f"{_col('unit_price', p)} IS NOT NULL",
        f"{_col('unit_price', p)} > 0",
    ]
    params: dict = {}
    if asset_type:
        norm = _normalize_asset_type(asset_type)
        if norm:
            clauses.append(f"{_col('asset_type', p)} = :asset_type")
            params["asset_type"] = norm
    apply_region_filters(
        clauses,
        params,
        addr1=addr1,
        addr2=addr2,
        addr3=addr3,
        addr3_list=addr3_list,
        addr4_list=addr4_list,
        col_prefix=p,
    )
    apply_period_filters(
        clauses,
        params,
        contract_date_from=contract_date_from,
        contract_date_to=contract_date_to,
        contract_year_from=contract_year_from,
        contract_year_to=contract_year_to,
        col_prefix=p,
    )
    return " AND ".join(clauses), params


def _cluster_list_meta(conn, *, window_years: int, data_source: str) -> dict[str, Any]:
    as_of_month, _ = latest_mart_snapshot(conn)
    meta: dict[str, Any] = {"data_source": data_source, "window_years": window_years}
    if as_of_month is not None:
        ps, pe = period_bounds_for_window(as_of_month, window_years)
        meta["period_start"] = ps.isoformat()
        meta["period_end"] = pe.isoformat()
        meta["as_of_month"] = as_of_month.isoformat()
        meta["stats_as_of_label"] = stats_as_of_label(as_of_month)
        meta["stats_reference_date"] = stats_reference_date(as_of_month).isoformat()
    return meta


def _cluster_list_response(
    *,
    total: int,
    items: list[CommercialClusterRow],
    meta: dict[str, Any],
) -> CommercialClusterListResponse:
    return CommercialClusterListResponse(
        total=total,
        items=items,
        data_source=meta.get("data_source", "live"),
        as_of_month=meta.get("as_of_month"),
        stats_reference_date=meta.get("stats_reference_date"),
        stats_as_of_label=meta.get("stats_as_of_label"),
        window_years=meta.get("window_years"),
        period_start=meta.get("period_start"),
        period_end=meta.get("period_end"),
    )


def _serialize_commercial_tx(row: dict) -> CommercialTransactionRow:
    d = dict(row)
    cd = d.get("contract_date")
    if cd is not None and hasattr(cd, "isoformat"):
        d["contract_date"] = cd.isoformat()
    return CommercialTransactionRow(**d)


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


@router.get("/meta/filters", response_model=CommercialFilterMeta)
def filter_meta(db: Session = Depends(get_collective_db)):
    years = db.execute(
        text(
            """
            SELECT DISTINCT contract_year AS y FROM collective_commercial_transactions
            WHERE contract_year IS NOT NULL ORDER BY 1
            """
        )
    ).fetchall()
    addr1 = db.execute(
        text(
            """
            SELECT DISTINCT addr1 AS v FROM collective_commercial_transactions
            WHERE addr1 IS NOT NULL AND btrim(addr1) <> '' ORDER BY 1
            """
        )
    ).fetchall()
    types = db.execute(
        text(
            """
            SELECT DISTINCT asset_type AS v FROM collective_commercial_transactions
            WHERE asset_type IS NOT NULL ORDER BY 1
            """
        )
    ).fetchall()
    return CommercialFilterMeta(
        asset_types=[r.v for r in types],
        contract_years=[int(r.y) for r in years],
        addr1_list=[r.v for r in addr1],
    )


@router.get("/regions/addr2")
def list_addr2(db: Session = Depends(get_collective_db), addr1: str = Query(...)):
    rows = db.execute(
        text(
            """
            SELECT DISTINCT addr2 AS v FROM collective_commercial_transactions
            WHERE addr1 = :a1 AND addr2 IS NOT NULL AND btrim(addr2) <> ''
            ORDER BY 1
            """
        ),
        {"a1": addr1},
    ).fetchall()
    return [r.v for r in rows]


@router.get("/regions/addr3")
def list_addr3(
    db: Session = Depends(get_collective_db),
    addr1: str = Query(...),
    addr2: str = Query(...),
    asset_type: Optional[str] = Query(None),
):
    where, params = _tx_where(asset_type=asset_type, addr1=addr1, addr2=addr2)
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
):
    where, params = _tx_where(
        asset_type=asset_type,
        addr1=addr1,
        addr2=addr2,
        addr3_list=addr3_list or None,
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
    window_years: int = Query(5, ge=3, le=5),
    sort: str = Query("count", pattern="^(count|mean|display_label)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500),
):
    if not addr2:
        raise HTTPException(400, "시군구(addr2)를 선택해 주세요.")

    asset_type = _normalize_asset_type(asset_type)

    use_mart = contract_year_from is None and contract_year_to is None
    if use_mart:
        mart_items = list_clusters_mart(
            db.connection(),
            asset_type=asset_type,
            addr1=addr1,
            addr2=addr2,
            addr3_list=addr3_list or None,
            addr4_list=addr4_list or None,
            window_years=window_years,
        )
        if mart_items:
            items = mart_items
            if sort == "mean":
                items.sort(key=lambda x: (x.mean is None, -(x.mean or 0)))
            elif sort == "display_label":
                items.sort(key=lambda x: x.display_label)
            else:
                items.sort(key=lambda x: -x.count)
            total = len(items)
            start = (page - 1) * page_size
            meta = _cluster_list_meta(db.connection(), window_years=window_years, data_source="mart")
            return _cluster_list_response(
                total=total,
                items=items[start : start + page_size],
                meta=meta,
            )

    where, params = _tx_where(
        asset_type=asset_type,
        addr1=addr1,
        addr2=addr2,
        addr3_list=addr3_list or None,
        addr4_list=addr4_list or None,
        contract_year_from=contract_year_from,
        contract_year_to=contract_year_to,
        col_prefix="t",
    )
    rows = db.execute(
        text(
            f"""
            SELECT t.cluster_key,
                   MAX(c.display_label) AS display_label,
                   MAX(t.asset_type) AS asset_type,
                   MAX(c.road_name) AS road_name,
                   MAX(t.addr3) AS addr3,
                   MAX(t.addr4) AS addr4,
                   MAX(c.resolution_mode) AS resolution_mode,
                   MAX(t.zone_type) AS zone_type,
                   MAX(t.building_use) AS building_use,
                   MAX(t.building_year) AS building_year,
                   MAX(t.area_bucket_label) AS area_bucket_label,
                   MAX(c.confidence_tier) AS confidence_tier,
                   array_agg(t.unit_price ORDER BY t.unit_price) AS prices
            FROM collective_commercial_transactions t
            JOIN commercial_clusters c ON c.id = t.cluster_id
            WHERE {where}
            GROUP BY t.cluster_key
            """
        ),
        params,
    ).mappings().all()

    items: list[CommercialClusterRow] = []
    for r in rows:
        prices = [float(x) for x in (r["prices"] or []) if x is not None]
        st = compute_stats(prices)
        items.append(
            CommercialClusterRow(
                cluster_key=r["cluster_key"],
                display_label=r["display_label"] or "",
                asset_type=r["asset_type"] or "",
                road_name=r["road_name"],
                addr3=r["addr3"],
                addr4=r["addr4"],
                resolution_mode=r["resolution_mode"],
                zone_type=r["zone_type"],
                building_use=r["building_use"],
                building_year=int(r["building_year"]) if r["building_year"] is not None else None,
                area_bucket_label=r["area_bucket_label"],
                confidence_tier=r["confidence_tier"],
                count=st["count"],
                mean=st["mean"],
                median=st["median"],
                ci_lower=st["ci_lower"],
                ci_upper=st["ci_upper"],
                is_reliable=st["count"] >= 15,
            )
        )

    if sort == "mean":
        items.sort(key=lambda x: (x.mean is None, -(x.mean or 0)))
    elif sort == "display_label":
        items.sort(key=lambda x: x.display_label)
    else:
        items.sort(key=lambda x: -x.count)

    total = len(items)
    start = (page - 1) * page_size
    page_items = items[start : start + page_size]
    meta = (
        _cluster_list_meta(db.connection(), window_years=window_years, data_source="live")
        if use_mart
        else {"data_source": "live", "window_years": window_years}
    )
    return _cluster_list_response(total=total, items=page_items, meta=meta)


@router.get("/clusters/{cluster_key}/addresses", response_model=CommercialAddressListResponse)
def list_cluster_addresses(
    cluster_key: str,
    db: Session = Depends(get_collective_db),
    addr1: Optional[str] = None,
    addr2: Optional[str] = None,
    addr3_list: list[str] = Query(default=[]),
    addr4_list: list[str] = Query(default=[]),
    contract_date_from: Optional[date] = None,
    contract_date_to: Optional[date] = None,
    contract_year_from: Optional[int] = None,
    contract_year_to: Optional[int] = None,
):
    """도로(cluster) 내 번지·읍면동별 ㎡당 단가 — 목록 조회와 동일 지역 필터 적용."""
    where, params = _tx_where(
        addr1=addr1,
        addr2=addr2,
        addr3_list=addr3_list or None,
        addr4_list=addr4_list or None,
        contract_date_from=contract_date_from,
        contract_date_to=contract_date_to,
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


@router.get("/clusters/{cluster_key}/stats/by-year", response_model=CommercialYearlyStatsResponse)
def cluster_stats_by_year(
    cluster_key: str,
    db: Session = Depends(get_collective_db),
    addr1: Optional[str] = None,
    addr2: Optional[str] = None,
    addr3_list: list[str] = Query(default=[]),
    addr4_list: list[str] = Query(default=[]),
    contract_date_from: Optional[date] = None,
    contract_date_to: Optional[date] = None,
    contract_year_from: Optional[int] = None,
    contract_year_to: Optional[int] = None,
):
    has_filters = any(
        [
            addr1,
            addr2,
            addr3_list,
            addr4_list,
            contract_date_from is not None,
            contract_date_to is not None,
            contract_year_from is not None,
            contract_year_to is not None,
        ]
    )
    if has_filters:
        where, params = _tx_where(
            addr1=addr1,
            addr2=addr2,
            addr3_list=addr3_list or None,
            addr4_list=addr4_list or None,
            contract_date_from=contract_date_from,
            contract_date_to=contract_date_to,
            contract_year_from=contract_year_from,
            contract_year_to=contract_year_to,
        )
        params["cluster_key"] = cluster_key
        rows = db.execute(
            text(
                f"""
                SELECT contract_year AS year,
                       COUNT(*)::int AS count,
                       AVG(unit_price)::float AS mean
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
            )
            for r in rows
        ]
        return CommercialYearlyStatsResponse(
            cluster_key=cluster_key,
            display_label=_cluster_display_label(db, cluster_key),
            points=points,
            data_source="live",
        )

    conn = db.connection()
    mart = cluster_yearly_from_mart(conn, cluster_key)
    if mart is not None:
        display_label, points, data_source = mart
        return CommercialYearlyStatsResponse(
            cluster_key=cluster_key,
            display_label=display_label,
            points=[CommercialYearlyStatPoint(**p) for p in points],
            data_source=data_source,
        )

    rows = db.execute(
        text(
            """
            SELECT contract_year AS year,
                   COUNT(*)::int AS count,
                   AVG(unit_price)::float AS mean
            FROM collective_commercial_transactions
            WHERE cluster_key = :cluster_key
              AND is_valid = true
              AND unit_price IS NOT NULL
              AND unit_price > 0
              AND contract_year IS NOT NULL
            GROUP BY contract_year
            ORDER BY contract_year
            """
        ),
        {"cluster_key": cluster_key},
    ).mappings().all()
    points = [
        CommercialYearlyStatPoint(
            year=int(r["year"]),
            count=int(r["count"]),
            mean=round(float(r["mean"]), 1) if r["mean"] is not None else None,
        )
        for r in rows
    ]
    return CommercialYearlyStatsResponse(
        cluster_key=cluster_key,
        display_label=_cluster_display_label(db, cluster_key),
        points=points,
        data_source="live",
    )


@router.get("/clusters/{cluster_key}/stats/rolling", response_model=CommercialRollingStatsResponse)
def cluster_stats_rolling(
    cluster_key: str,
    db: Session = Depends(get_collective_db),
    window_years: int = Query(5, ge=3, le=5),
):
    display_label = _cluster_display_label(db, cluster_key)
    points, as_of, source = fetch_cluster_rolling(
        db.connection(), cluster_key, window_years=window_years
    )
    if not points and source == "live":
        return CommercialRollingStatsResponse(
            cluster_key=cluster_key,
            display_label=display_label,
            window_years=window_years,
            points=[],
            data_source="live",
        )
    return CommercialRollingStatsResponse(
        cluster_key=cluster_key,
        display_label=display_label,
        window_years=window_years,
        as_of_month=as_of.isoformat() if as_of else None,
        points=[CommercialRollingStatPoint(**{**p, "period_start": p["period_start"].isoformat(), "period_end": p["period_end"].isoformat()}) for p in points],
        data_source=source,
    )


@router.get("/clusters/{cluster_key}/histogram", response_model=CommercialHistogramResponse)
def cluster_histogram(
    cluster_key: str,
    db: Session = Depends(get_collective_db),
    addr1: Optional[str] = None,
    addr2: Optional[str] = None,
    addr3_list: list[str] = Query(default=[]),
    addr4_list: list[str] = Query(default=[]),
    contract_date_from: Optional[date] = None,
    contract_date_to: Optional[date] = None,
    contract_year_from: Optional[int] = None,
    contract_year_to: Optional[int] = None,
    bins: int = Query(12, ge=4, le=40),
    contract_year: Optional[int] = None,
):
    where, params = _tx_where(
        addr1=addr1,
        addr2=addr2,
        addr3_list=addr3_list or None,
        addr4_list=addr4_list or None,
        contract_date_from=contract_date_from,
        contract_date_to=contract_date_to,
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


@router.get("/clusters/{cluster_key}/peer-clusters", response_model=CommercialPeerClusterListResponse)
def list_peer_clusters(
    cluster_key: str,
    db: Session = Depends(get_collective_db),
    addr1: Optional[str] = None,
    addr2: Optional[str] = None,
    addr3_list: list[str] = Query(default=[]),
    addr4_list: list[str] = Query(default=[]),
    contract_date_from: Optional[date] = None,
    contract_date_to: Optional[date] = None,
    contract_year_from: Optional[int] = None,
    contract_year_to: Optional[int] = None,
    limit: int = Query(40, ge=1, le=80),
):
    """동일·인접 법정동 내 다른 도로 cluster — 코호트 후보."""
    anchor = db.execute(
        text(
            """
            SELECT MAX(addr1) AS addr1, MAX(addr2) AS addr2,
                   MAX(addr3) AS addr3, MAX(addr4) AS addr4,
                   MAX(asset_type) AS asset_type,
                   COALESCE(MAX(c.display_label), MAX(t.road_name)) AS display_label
            FROM collective_commercial_transactions t
            LEFT JOIN commercial_clusters c ON c.cluster_key = t.cluster_key
            WHERE t.cluster_key = :ck
            """
        ),
        {"ck": cluster_key},
    ).mappings().first()
    if not anchor or not anchor.get("asset_type"):
        raise HTTPException(404, "cluster를 찾을 수 없습니다.")

    where, params = _tx_where(
        addr1=addr1 or anchor.get("addr1"),
        addr2=addr2 or anchor.get("addr2"),
        addr3_list=addr3_list or None,
        addr4_list=addr4_list or None,
        contract_date_from=contract_date_from,
        contract_date_to=contract_date_to,
        contract_year_from=contract_year_from,
        contract_year_to=contract_year_to,
    )
    params["ck"] = cluster_key
    params["asset_type"] = anchor["asset_type"]
    anchor_addr3 = anchor.get("addr3")
    anchor_addr4 = anchor.get("addr4")

    rows = db.execute(
        text(
            f"""
            SELECT t.cluster_key,
                   COALESCE(MAX(c.display_label), MAX(t.road_name), t.cluster_key) AS display_label,
                   MAX(t.road_name) AS road_name,
                   MAX(t.addr3) AS addr3,
                   MAX(t.addr4) AS addr4,
                   COUNT(*)::int AS cnt,
                   CASE
                     WHEN :anchor_addr4 IS NOT NULL AND MAX(t.addr4) = :anchor_addr4 THEN 2
                     WHEN :anchor_addr3 IS NOT NULL AND MAX(t.addr3) = :anchor_addr3 THEN 1
                     ELSE 0
                   END AS adjacency_rank
            FROM collective_commercial_transactions t
            LEFT JOIN commercial_clusters c ON c.cluster_key = t.cluster_key
            WHERE t.cluster_key != :ck
              AND t.asset_type = :asset_type
              AND {where}
            GROUP BY t.cluster_key
            ORDER BY adjacency_rank DESC, cnt DESC, display_label
            LIMIT :lim
            """
        ),
        {
            **params,
            "anchor_addr3": anchor_addr3,
            "anchor_addr4": anchor_addr4,
            "lim": limit,
        },
    ).mappings().all()

    items = [
        CommercialPeerClusterRow(
            cluster_key=r["cluster_key"],
            display_label=r["display_label"] or r["cluster_key"],
            road_name=r.get("road_name"),
            addr3=r.get("addr3"),
            addr4=r.get("addr4"),
            count=int(r["cnt"] or 0),
            same_dong=bool(
                anchor_addr4
                and r.get("addr4")
                and str(r["addr4"]) == str(anchor_addr4)
            ),
        )
        for r in rows
    ]
    return CommercialPeerClusterListResponse(cluster_key=cluster_key, items=items)


@router.post("/clusters/{cluster_key}/regression/run", response_model=CommercialRegressionResponse)
def cluster_regression(
    cluster_key: str,
    body: CommercialRegressionRequest,
    db: Session = Depends(get_collective_db),
):
    import pandas as pd

    where, params = _tx_where(
        addr1=body.addr1,
        addr2=body.addr2,
        addr3_list=body.addr3_list or None,
        addr4_list=body.addr4_list or None,
        contract_date_from=body.contract_date_from,
        contract_date_to=body.contract_date_to,
        contract_year_from=body.contract_year_from,
        contract_year_to=body.contract_year_to,
    )
    params["cluster_key"] = cluster_key
    rows = db.execute(
        text(
            f"""
            SELECT price, unit_price, gross_area, land_area, building_age, building_year, floor,
                   zone_type, building_use, road_width_label, road_code, addr4, contract_year,
                   contract_month, asset_type
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
        suggest_cohort=True,
        cohort_guidance=COMMERCIAL_COHORT_GUIDANCE,
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
        addr1=body.addr1,
        addr2=body.addr2,
        addr3_list=body.addr3_list or None,
        addr4_list=body.addr4_list or None,
        contract_date_from=body.contract_date_from,
        contract_date_to=body.contract_date_to,
        contract_year_from=body.contract_year_from,
        contract_year_to=body.contract_year_to,
    )
    params["cluster_key"] = cluster_key
    rows = db.execute(
        text(
            f"""
            SELECT price, unit_price, gross_area, land_area, building_age, building_year, floor,
                   zone_type, building_use, road_width_label, road_code, addr4, contract_year,
                   contract_month, asset_type, cluster_key
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
        suggest_cohort=True,
        cohort_guidance=COMMERCIAL_COHORT_GUIDANCE,
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
    contract_date_from: Optional[date] = None,
    contract_date_to: Optional[date] = None,
    contract_year_from: Optional[int] = None,
    contract_year_to: Optional[int] = None,
    dimension: str = Query("floor", pattern="^(floor|area)$"),
    experiment: bool = Query(False, description="표본 게이트 우회"),
):
    import pandas as pd

    where, params = _tx_where(
        addr1=addr1,
        addr2=addr2,
        addr3_list=addr3_list or None,
        addr4_list=addr4_list or None,
        contract_date_from=contract_date_from,
        contract_date_to=contract_date_to,
        contract_year_from=contract_year_from,
        contract_year_to=contract_year_to,
    )
    params["cluster_key"] = cluster_key
    rows = db.execute(
        text(
            f"""
            SELECT unit_price, floor, gross_area, contract_year, contract_month, building_year, building_age,
                   building_use, area_bucket_label, asset_type
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
        suggest_cohort=True,
        cohort_guidance=COMMERCIAL_COHORT_GUIDANCE,
    )
    if not gates.floor_index_eligible and not experiment:
        raise HTTPException(
            403,
            detail=gates.messages[0] if gates.messages else "효용지수 분석 최소 표본 미달",
        )

    df = pd.DataFrame(rows)
    asset_type = rows[0].get("asset_type") or "collective_shop"
    display_label = _cluster_display_label(db, cluster_key)

    if dimension == "floor" and asset_type in ("collective_shop", "collective_factory"):
        raw = compute_shop_floor_index_regression(df)
    elif dimension == "area":
        raw = compute_commercial_area_index_regression(df, asset_type=asset_type)
    else:
        df["exclusive_area"] = df["gross_area"]
        raw = compute_floor_index(df, asset_type=asset_type, dimension=dimension)
        raw.setdefault("method", "simple_median")
        raw.setdefault("reference_floor", None)
        raw.setdefault("controls", [])
        raw.setdefault("n_regression", None)
        raw.setdefault("r_squared", None)
        raw.setdefault("warnings", [])
        if asset_type == "collective_factory" and dimension == "floor":
            raw["warnings"] = list(raw.get("warnings") or []) + [
                "집합공장은 층 정보가 일부만 있을 수 있습니다 — 면적대 탭과 함께 참고하세요."
            ]

    cells = [FloorIndexCell(**c) for c in raw["cells"]]
    method = raw.get("method", "simple_median")
    explain = AnalysisExplain(
        **build_commercial_floor_index_explain(
            method=method,
            dimension=raw["dimension"],
            asset_type=asset_type,
            raw=raw,
        )
    )
    diag_raw = raw.get("diagnostics")
    diagnostics = FloorIndexDiagnostics(**diag_raw) if diag_raw else None

    return CommercialFloorIndexResponse(
        cluster_key=cluster_key,
        display_label=display_label,
        asset_type=asset_type,
        dimension=raw["dimension"],
        method=method,
        reference_floor=raw.get("reference_floor"),
        controls=raw.get("controls") or [],
        n_total=raw["n_total"],
        n_regression=raw.get("n_regression"),
        r_squared=raw.get("r_squared"),
        baseline_median=raw.get("baseline_median"),
        cells=cells,
        warnings=raw.get("warnings") or [],
        explain=explain,
        analysis=AnalysisFeatures(
            floor_index=gates.floor_index_eligible,
            regression=gates.regression_eligible,
            count_total=gates.count_total,
            count_recent=gates.count_recent,
            messages=gates.messages,
        ),
        diagnostics=diagnostics,
    )


@router.get("/clusters/{cluster_key}/transactions", response_model=CommercialTransactionListResponse)
def list_cluster_transactions(
    cluster_key: str,
    db: Session = Depends(get_collective_db),
    addr1: Optional[str] = None,
    addr2: Optional[str] = None,
    addr3_list: list[str] = Query(default=[]),
    addr4_list: list[str] = Query(default=[]),
    contract_date_from: Optional[date] = None,
    contract_date_to: Optional[date] = None,
    contract_year_from: Optional[int] = None,
    contract_year_to: Optional[int] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    where, params = _tx_where(
        addr1=addr1,
        addr2=addr2,
        addr3_list=addr3_list or None,
        addr4_list=addr4_list or None,
        contract_date_from=contract_date_from,
        contract_date_to=contract_date_to,
        contract_year_from=contract_year_from,
        contract_year_to=contract_year_to,
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
                   road_code, road_width_label, buyer_type, seller_type, deal_type
            FROM collective_commercial_transactions
            WHERE cluster_key = :cluster_key AND {where}
            ORDER BY contract_date DESC NULLS LAST, contract_year DESC NULLS LAST, contract_month DESC NULLS LAST, id DESC
            LIMIT :limit OFFSET :offset
            """
        ),
        params,
    ).mappings().all()
    items = [_serialize_commercial_tx(dict(r)) for r in rows]
    return CommercialTransactionListResponse(total=int(total), items=items)


@router.get("/clusters/{cluster_key}/transactions/export")
def export_cluster_transactions(
    cluster_key: str,
    db: Session = Depends(get_collective_db),
    addr1: Optional[str] = None,
    addr2: Optional[str] = None,
    addr3_list: list[str] = Query(default=[]),
    addr4_list: list[str] = Query(default=[]),
    contract_date_from: Optional[date] = None,
    contract_date_to: Optional[date] = None,
    contract_year_from: Optional[int] = None,
    contract_year_to: Optional[int] = None,
):
    """목록 API와 동일 필터로 전체 거래를 CSV(UTF-8 BOM)로 반환."""
    where, params = _tx_where(
        addr1=addr1,
        addr2=addr2,
        addr3_list=addr3_list or None,
        addr4_list=addr4_list or None,
        contract_date_from=contract_date_from,
        contract_date_to=contract_date_to,
        contract_year_from=contract_year_from,
        contract_year_to=contract_year_to,
    )
    params["cluster_key"] = cluster_key
    total = int(
        db.execute(
            text(
                f"""
                SELECT COUNT(*) FROM collective_commercial_transactions
                WHERE cluster_key = :cluster_key AND {where}
                """
            ),
            params,
        ).scalar()
        or 0
    )
    if total > MAX_COLLECTIVE_TX_EXPORT:
        raise HTTPException(
            413,
            detail=(
                f"내보내기 상한({MAX_COLLECTIVE_TX_EXPORT:,}건)을 초과했습니다. "
                "연도·기간 범위를 줄여 주세요."
            ),
        )
    rows = db.execute(
        text(
            f"""
            SELECT id, asset_type, cluster_key, addr3, addr4, lot_number,
                   contract_year, contract_month, contract_date, price, gross_area,
                   unit_price, floor, building_year,
                   zone_type, building_use, road_width_label, road_code,
                   buyer_type, seller_type
            FROM collective_commercial_transactions
            WHERE cluster_key = :cluster_key AND {where}
            ORDER BY contract_date DESC NULLS LAST, contract_year DESC NULLS LAST,
                     contract_month DESC NULLS LAST, id DESC
            """
        ),
        params,
    ).mappings().all()
    display_label = _cluster_display_label(db, cluster_key)
    payload = commercial_transactions_csv_bytes([dict(r) for r in rows])
    filename = export_filename(display_name=display_label, prefix="transactions", fallback_key=cluster_key)
    return csv_attachment_response(payload, filename)


from app.collective_commercial.cohort_router import router as commercial_cohort_router  # noqa: E402

router.include_router(commercial_cohort_router)
