"""집합상가·집합공장 cluster API."""

from __future__ import annotations

from typing import Optional

import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session

from app.collective.analysis_explain import (
    build_commercial_floor_index_explain,
    build_commercial_regression_explain,
)
from app.collective.analysis_gates import count_recent_transactions, evaluate_analysis_gates
from app.collective.db import get_collective_db
from app.collective.floor_index import compute_floor_index
from app.collective_commercial.floor_index_regression import compute_shop_floor_index_regression
from app.collective.schemas import AnalysisExplain, AnalysisFeatures, FloorIndexCell
from app.collective.filters import _col, apply_region_filters, apply_year_filters
from app.collective.region_structure import detect_region_structure
from app.collective.schemas import RegionOption, RegionStructureResponse
from app.collective_commercial.schemas import (
    CommercialAddressListResponse,
    CommercialAddressRow,
    CommercialClusterListResponse,
    CommercialClusterRow,
    CommercialFilterMeta,
    CommercialFloorIndexResponse,
    CommercialHistogramBin,
    CommercialHistogramResponse,
    CommercialRegressionRequest,
    CommercialRegressionResponse,
    CommercialTransactionListResponse,
    CommercialTransactionRow,
    CommercialYearlyStatPoint,
    CommercialYearlyStatsResponse,
)
from app.stats_utils import compute_stats

from app.collective_commercial.regression.engine import run_commercial_regression

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
    if asset_type:
        clauses.append(f"{_col('asset_type', p)} = :asset_type")
        params["asset_type"] = asset_type
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
    apply_year_filters(
        clauses,
        params,
        contract_year_from=contract_year_from,
        contract_year_to=contract_year_to,
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
    where, params = _tx_where(conn=db.connection(), asset_type=asset_type, addr1=addr1, addr2=addr2)
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
        conn=db.connection(),
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
    sort: str = Query("count", pattern="^(count|mean|display_label)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500),
):
    if not addr2:
        raise HTTPException(400, "시군구(addr2)를 선택해 주세요.")

    where, params = _tx_where(
        conn=db.connection(),
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
    return CommercialClusterListResponse(total=total, items=page_items)


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
            SELECT unit_price, floor, gross_area, contract_year, building_year, building_age,
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
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
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
                   contract_year, contract_month, price, gross_area, land_area,
                   unit_price, floor, building_year, building_age,
                   zone_type, building_use, area_bucket_label, road_name,
                   road_code, road_width_label
            FROM collective_commercial_transactions
            WHERE cluster_key = :cluster_key AND {where}
            ORDER BY contract_year DESC NULLS LAST, contract_month DESC NULLS LAST, id DESC
            LIMIT :limit OFFSET :offset
            """
        ),
        params,
    ).mappings().all()
    items = [CommercialTransactionRow(**dict(r)) for r in rows]
    return CommercialTransactionListResponse(total=int(total), items=items)
