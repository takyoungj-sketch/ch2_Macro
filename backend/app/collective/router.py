"""집합부동산 collective_stats API."""

from __future__ import annotations

from typing import Optional

import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.collective.address import format_building_address
from app.collective.analysis_gates import count_recent_transactions, evaluate_analysis_gates
from app.collective.db import get_collective_db
from app.collective.filters import apply_region_filters, apply_year_filters
from app.collective.floor_index import compute_floor_index
from app.collective.regression.engine import run_building_regression
from app.collective.region_structure import detect_region_structure
from app.collective.schemas import (
    AnalysisFeatures,
    BuildingListResponse,
    BuildingStatsRow,
    CollectiveFilterMeta,
    CollectiveRegressionRequest,
    CollectiveRegressionResponse,
    CollectiveTransactionRow,
    FloorIndexCell,
    FloorIndexResponse,
    HistogramBin,
    HistogramResponse,
    RegionOption,
    RegionStructureResponse,
    TransactionListResponse,
    YearlyStatPoint,
    YearlyStatsResponse,
)
from app.stats_utils import compute_stats

router = APIRouter(prefix="/collective", tags=["집합부동산"])


def _base_where(
    *,
    asset_type: Optional[str] = None,
    addr1: Optional[str] = None,
    addr2: Optional[str] = None,
    addr3: Optional[str] = None,
    addr3_list: list[str] | None = None,
    addr4_list: list[str] | None = None,
    contract_year_from: Optional[int] = None,
    contract_year_to: Optional[int] = None,
) -> tuple[str, dict]:
    clauses = ["is_valid = true", "unit_price IS NOT NULL", "unit_price > 0"]
    params: dict = {}
    if asset_type:
        clauses.append("asset_type = :asset_type")
        params["asset_type"] = asset_type
    apply_region_filters(
        clauses,
        params,
        addr1=addr1,
        addr2=addr2,
        addr3=addr3,
        addr3_list=addr3_list,
        addr4_list=addr4_list,
    )
    apply_year_filters(
        clauses,
        params,
        contract_year_from=contract_year_from,
        contract_year_to=contract_year_to,
    )
    return " AND ".join(clauses), params


@router.get("/meta/filters", response_model=CollectiveFilterMeta)
def filter_meta(db: Session = Depends(get_collective_db)):
    def _distinct(col: str) -> list:
        rows = db.execute(
            text(
                f"""
                SELECT DISTINCT {col} AS v FROM collective_transactions
                WHERE {col} IS NOT NULL AND btrim({col}::text) <> ''
                ORDER BY 1
                """
            )
        ).fetchall()
        return [r.v for r in rows]

    years = db.execute(
        text(
            """
            SELECT DISTINCT contract_year AS y FROM collective_transactions
            WHERE contract_year IS NOT NULL ORDER BY 1
            """
        )
    ).fetchall()
    return CollectiveFilterMeta(
        asset_types=_distinct("asset_type"),
        contract_years=[int(r.y) for r in years],
        addr1_list=_distinct("addr1"),
    )


@router.get("/regions/addr2")
def list_addr2(db: Session = Depends(get_collective_db), addr1: str = Query(...)):
    rows = db.execute(
        text(
            """
            SELECT DISTINCT addr2 AS v FROM collective_transactions
            WHERE addr1 = :a1 AND addr2 IS NOT NULL AND btrim(addr2) <> ''
            ORDER BY 1
            """
        ),
        {"a1": addr1},
    ).fetchall()
    return [r.v for r in rows]


@router.get("/regions/structure", response_model=RegionStructureResponse)
def region_structure(
    db: Session = Depends(get_collective_db),
    addr1: str = Query(...),
    addr2: str = Query(...),
    asset_type: Optional[str] = Query(None),
):
    info = detect_region_structure(db.connection(), addr1, addr2, asset_type)
    return RegionStructureResponse(**info)


@router.get("/regions/leaf", response_model=list[RegionOption])
def list_leaf_regions(
    db: Session = Depends(get_collective_db),
    addr1: str = Query(...),
    addr2: str = Query(...),
    addr3_list: list[str] = Query(default=[]),
    asset_type: Optional[str] = Query(None),
):
    """청주·수원 등: addr3=구, addr4=읍면동."""
    where, params = _base_where(asset_type=asset_type, addr1=addr1, addr2=addr2, addr3_list=addr3_list or None)
    rows = db.execute(
        text(
            f"""
            SELECT addr4 AS name, addr3 AS parent, COUNT(*)::int AS count
            FROM collective_transactions
            WHERE {where}
              AND addr4 IS NOT NULL AND btrim(addr4::text) <> ''
            GROUP BY addr4, addr3
            ORDER BY addr3, addr4
            """
        ),
        params,
    ).mappings().all()
    return [RegionOption(**dict(r)) for r in rows]


@router.get("/regions/addr3")
def list_addr3(
    db: Session = Depends(get_collective_db),
    addr1: str = Query(...),
    addr2: str = Query(...),
    asset_type: Optional[str] = Query(None),
):
    where, params = _base_where(asset_type=asset_type, addr1=addr1, addr2=addr2)
    rows = db.execute(
        text(
            f"""
            SELECT addr3 AS name, COUNT(*)::int AS count
            FROM collective_transactions
            WHERE {where} AND addr3 IS NOT NULL AND btrim(addr3) <> ''
            GROUP BY addr3
            ORDER BY count DESC, addr3
            """
        ),
        params,
    ).mappings().all()
    return [dict(r) for r in rows]


@router.get("/buildings", response_model=BuildingListResponse)
def list_buildings(
    db: Session = Depends(get_collective_db),
    asset_type: Optional[str] = Query(None),
    addr1: Optional[str] = None,
    addr2: Optional[str] = None,
    addr3: Optional[str] = None,
    addr3_list: list[str] = Query(default=[]),
    addr4_list: list[str] = Query(default=[]),
    contract_year_from: Optional[int] = None,
    contract_year_to: Optional[int] = None,
    sort: str = Query("count", pattern="^(count|mean|display_name)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500),
):
    if not addr2:
        raise HTTPException(400, "시군구(addr2)를 선택해 주세요.")

    where, params = _base_where(
        asset_type=asset_type,
        addr1=addr1,
        addr2=addr2,
        addr3=addr3,
        addr3_list=addr3_list or None,
        addr4_list=addr4_list or None,
        contract_year_from=contract_year_from,
        contract_year_to=contract_year_to,
    )
    rows = db.execute(
        text(
            f"""
            SELECT building_key,
                   MAX(display_name) AS display_name,
                   MAX(asset_type) AS asset_type,
                   MAX(addr3) AS addr3,
                   MAX(addr4) AS addr4,
                   MAX(lot_number) AS lot_number,
                   MAX(road_name) AS road_name,
                   MAX(building_year) AS building_year,
                   array_agg(unit_price ORDER BY unit_price) AS prices,
                   array_agg(contract_year) AS years
            FROM collective_transactions
            WHERE {where}
            GROUP BY building_key
            """
        ),
        params,
    ).mappings().all()

    items: list[BuildingStatsRow] = []
    for r in rows:
        prices = [float(x) for x in (r["prices"] or []) if x is not None]
        years = [int(y) for y in (r["years"] or []) if y is not None]
        st = compute_stats(prices)
        cnt_recent = count_recent_transactions(
            years,
            contract_year_from=contract_year_from,
            contract_year_to=contract_year_to,
        )
        gates = evaluate_analysis_gates(st["count"], cnt_recent)
        items.append(
            BuildingStatsRow(
                building_key=r["building_key"],
                display_name=r["display_name"] or "",
                address=format_building_address(
                    addr3=r["addr3"],
                    addr4=r["addr4"],
                    lot_number=r["lot_number"],
                    road_name=r["road_name"],
                ),
                building_year=int(r["building_year"]) if r["building_year"] is not None else None,
                asset_type=r["asset_type"] or asset_type or "",
                count=st["count"],
                mean=st["mean"],
                median=st["median"],
                ci_lower=st["ci_lower"],
                ci_upper=st["ci_upper"],
                is_reliable=st["is_reliable"],
                analysis=AnalysisFeatures(
                    floor_index=gates.floor_index_eligible,
                    regression=gates.regression_eligible,
                    count_total=gates.count_total,
                    count_recent=gates.count_recent,
                    messages=gates.messages,
                ),
            )
        )

    if sort == "display_name":
        items.sort(key=lambda x: x.display_name)
    elif sort == "mean":
        items.sort(key=lambda x: (x.mean or 0), reverse=True)
    else:
        items.sort(key=lambda x: x.count, reverse=True)

    total = len(items)
    start = (page - 1) * page_size
    page_items = items[start : start + page_size]
    return BuildingListResponse(total=total, items=page_items)


def _get_building_meta(db: Session, building_key: str) -> tuple[str, str]:
    row = db.execute(
        text(
            """
            SELECT display_name, asset_type FROM collective_transactions
            WHERE building_key = :bk LIMIT 1
            """
        ),
        {"bk": building_key},
    ).mappings().first()
    if not row:
        raise HTTPException(404, "건물을 찾을 수 없습니다")
    return row["display_name"], row["asset_type"]


@router.get("/buildings/{building_key}/transactions", response_model=TransactionListResponse)
def building_transactions(
    building_key: str,
    db: Session = Depends(get_collective_db),
    contract_year_from: Optional[int] = None,
    contract_year_to: Optional[int] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    clauses = ["building_key = :bk", "is_valid = true"]
    params: dict = {"bk": building_key}
    apply_year_filters(clauses, params, contract_year_from=contract_year_from, contract_year_to=contract_year_to)
    where = " AND ".join(clauses)
    total = db.execute(text(f"SELECT COUNT(*) FROM collective_transactions WHERE {where}"), params).scalar()
    params.update({"limit": page_size, "offset": (page - 1) * page_size})
    rows = db.execute(
        text(
            f"""
            SELECT id, asset_type, building_key, display_name,
                   addr1, addr2, addr3, contract_year, contract_month,
                   exclusive_area, price, unit_price, floor, dong, building_age
            FROM collective_transactions
            WHERE {where}
            ORDER BY contract_year DESC NULLS LAST, contract_month DESC NULLS LAST, id DESC
            LIMIT :limit OFFSET :offset
            """
        ),
        params,
    ).mappings().all()
    items = [CollectiveTransactionRow(**dict(r)) for r in rows]
    return TransactionListResponse(total=int(total or 0), items=items)


@router.get("/buildings/{building_key}/stats/by-year", response_model=YearlyStatsResponse)
def building_stats_by_year(
    building_key: str,
    db: Session = Depends(get_collective_db),
):
    display_name, _ = _get_building_meta(db, building_key)
    rows = db.execute(
        text(
            """
            SELECT contract_year AS year,
                   COUNT(*)::int AS count,
                   AVG(unit_price)::float AS mean
            FROM collective_transactions
            WHERE building_key = :bk AND is_valid = true AND contract_year IS NOT NULL
            GROUP BY contract_year
            ORDER BY contract_year
            """
        ),
        {"bk": building_key},
    ).mappings().all()
    points = [
        YearlyStatPoint(year=int(r["year"]), count=int(r["count"]), mean=round(float(r["mean"]), 1) if r["mean"] else None)
        for r in rows
    ]
    return YearlyStatsResponse(building_key=building_key, display_name=display_name, points=points)


@router.get("/buildings/{building_key}/histogram", response_model=HistogramResponse)
def building_histogram(
    building_key: str,
    db: Session = Depends(get_collective_db),
    bins: int = Query(12, ge=4, le=40),
    contract_year: Optional[int] = None,
):
    clauses = ["building_key = :bk", "is_valid = true", "unit_price IS NOT NULL"]
    params: dict = {"bk": building_key}
    if contract_year is not None:
        clauses.append("contract_year = :cy")
        params["cy"] = contract_year
    where = " AND ".join(clauses)
    rows = db.execute(
        text(f"SELECT unit_price FROM collective_transactions WHERE {where}"),
        params,
    ).fetchall()
    prices = [float(r[0]) for r in rows if r[0] is not None]
    if not prices:
        return HistogramResponse(building_key=building_key, bins=[], n=0, contract_year=contract_year)
    lo, hi = min(prices), max(prices)
    if lo == hi:
        return HistogramResponse(
            building_key=building_key,
            bins=[HistogramBin(lo=lo, hi=hi, count=len(prices))],
            n=len(prices),
            contract_year=contract_year,
        )
    edges = np.linspace(lo, hi, bins + 1)
    counts, _ = np.histogram(prices, bins=edges)
    out = [
        HistogramBin(lo=round(float(edges[i]), 1), hi=round(float(edges[i + 1]), 1), count=int(counts[i]))
        for i in range(len(counts))
        if counts[i] > 0
    ]
    return HistogramResponse(
        building_key=building_key,
        bins=out,
        n=len(prices),
        contract_year=contract_year,
    )


@router.get("/buildings/{building_key}/floor-index", response_model=FloorIndexResponse)
def building_floor_index(
    building_key: str,
    db: Session = Depends(get_collective_db),
    dimension: str = Query("floor", pattern="^(floor|dong|area)$"),
    contract_year_from: Optional[int] = None,
    contract_year_to: Optional[int] = None,
    experiment: bool = Query(False, description="실험 단계: 표본 게이트 우회"),
):
    import pandas as pd

    display_name, asset_type = _get_building_meta(db, building_key)
    where, params = _base_where(
        contract_year_from=contract_year_from,
        contract_year_to=contract_year_to,
    )
    params["bk"] = building_key
    rows = db.execute(
        text(
            f"""
            SELECT unit_price, floor, dong, exclusive_area, contract_year
            FROM collective_transactions
            WHERE building_key = :bk AND {where}
            """
        ),
        params,
    ).mappings().all()
    years = [int(r["contract_year"]) for r in rows if r.get("contract_year") is not None]
    cnt_recent = count_recent_transactions(
        years,
        contract_year_from=contract_year_from,
        contract_year_to=contract_year_to,
    )
    gates = evaluate_analysis_gates(len(rows), cnt_recent)
    if not gates.floor_index_eligible and not experiment:
        raise HTTPException(
            403,
            detail=gates.messages[0] if gates.messages else "효용지수 분석 최소 표본 미달",
        )

    df = pd.DataFrame(rows)
    raw = compute_floor_index(df, asset_type=asset_type, dimension=dimension)
    cells = [FloorIndexCell(**c) for c in raw["cells"]]
    return FloorIndexResponse(
        building_key=building_key,
        display_name=display_name,
        asset_type=asset_type,
        dimension=raw["dimension"],
        n_total=raw["n_total"],
        baseline_median=raw["baseline_median"],
        cells=cells,
        analysis=AnalysisFeatures(
            floor_index=gates.floor_index_eligible,
            regression=gates.regression_eligible,
            count_total=gates.count_total,
            count_recent=gates.count_recent,
            messages=gates.messages,
        ),
    )


@router.post("/buildings/{building_key}/regression/run", response_model=CollectiveRegressionResponse)
def building_regression(
    building_key: str,
    body: CollectiveRegressionRequest,
    db: Session = Depends(get_collective_db),
):
    import pandas as pd

    display_name, asset_type = _get_building_meta(db, building_key)
    clauses = ["building_key = :bk", "is_valid = true"]
    params: dict = {"bk": building_key}
    apply_year_filters(
        clauses,
        params,
        contract_year_from=body.contract_year_from,
        contract_year_to=body.contract_year_to,
    )
    where = " AND ".join(clauses)
    rows = db.execute(
        text(
            f"""
            SELECT price, unit_price, exclusive_area, building_age, floor, dong, contract_year
            FROM collective_transactions
            WHERE {where}
            """
        ),
        params,
    ).mappings().all()
    years = [int(r["contract_year"]) for r in rows if r.get("contract_year") is not None]
    cnt_recent = count_recent_transactions(
        years,
        contract_year_from=body.contract_year_from,
        contract_year_to=body.contract_year_to,
    )
    gates = evaluate_analysis_gates(len(rows), cnt_recent)
    if not gates.regression_eligible and not body.experiment:
        raise HTTPException(
            403,
            detail="; ".join(gates.messages) if gates.messages else "회귀 분석 최소 표본 미달",
        )

    df = pd.DataFrame(rows)
    if body.asset_type != asset_type:
        pass  # allow client hint; data is keyed by building
    return run_building_regression(df, building_key, display_name, body)
