"""집합부동산 collective_stats API."""

from __future__ import annotations

from typing import Optional

import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.collective.db import get_collective_db
from app.collective.filters import apply_region_filters, apply_year_filters
from app.collective.regression.engine import run_building_regression
from app.collective.schemas import (
    BuildingListResponse,
    BuildingStatsRow,
    CollectiveFilterMeta,
    CollectiveRegressionRequest,
    CollectiveRegressionResponse,
    CollectiveTransactionRow,
    HistogramBin,
    HistogramResponse,
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
    contract_year_from: Optional[int] = None,
    contract_year_to: Optional[int] = None,
) -> tuple[str, dict]:
    clauses = ["is_valid = true", "unit_price IS NOT NULL", "unit_price > 0"]
    params: dict = {}
    if asset_type:
        clauses.append("asset_type = :asset_type")
        params["asset_type"] = asset_type
    apply_region_filters(clauses, params, addr1=addr1, addr2=addr2, addr3=addr3, addr3_list=addr3_list)
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
    contract_year_from: Optional[int] = None,
    contract_year_to: Optional[int] = None,
    sort: str = Query("count", pattern="^(count|mean|display_name)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500),
):
    if not addr2 and not addr1:
        raise HTTPException(400, "addr1·addr2 중 최소 시군구(addr2)까지 선택해 주세요.")

    where, params = _base_where(
        asset_type=asset_type,
        addr1=addr1,
        addr2=addr2,
        addr3=addr3,
        contract_year_from=contract_year_from,
        contract_year_to=contract_year_to,
    )
    rows = db.execute(
        text(
            f"""
            SELECT building_key,
                   MAX(display_name) AS display_name,
                   MAX(asset_type) AS asset_type,
                   array_agg(unit_price ORDER BY unit_price) AS prices
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
        st = compute_stats(prices)
        items.append(
            BuildingStatsRow(
                building_key=r["building_key"],
                display_name=r["display_name"] or "",
                asset_type=r["asset_type"] or asset_type or "",
                count=st["count"],
                mean=st["mean"],
                median=st["median"],
                ci_lower=st["ci_lower"],
                ci_upper=st["ci_upper"],
                is_reliable=st["is_reliable"],
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
            ORDER BY contract_year DESC NULLS LAST, id DESC
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
):
    rows = db.execute(
        text(
            """
            SELECT unit_price FROM collective_transactions
            WHERE building_key = :bk AND is_valid = true AND unit_price IS NOT NULL
            """
        ),
        {"bk": building_key},
    ).fetchall()
    prices = [float(r[0]) for r in rows if r[0] is not None]
    if not prices:
        return HistogramResponse(building_key=building_key, bins=[])
    lo, hi = min(prices), max(prices)
    if lo == hi:
        return HistogramResponse(
            building_key=building_key,
            bins=[HistogramBin(lo=lo, hi=hi, count=len(prices))],
        )
    edges = np.linspace(lo, hi, bins + 1)
    counts, _ = np.histogram(prices, bins=edges)
    out = [
        HistogramBin(lo=round(float(edges[i]), 1), hi=round(float(edges[i + 1]), 1), count=int(counts[i]))
        for i in range(len(counts))
        if counts[i] > 0
    ]
    return HistogramResponse(building_key=building_key, bins=out)


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
            SELECT price, unit_price, exclusive_area, building_age, floor, dong
            FROM collective_transactions
            WHERE {where}
            """
        ),
        params,
    ).mappings().all()
    df = pd.DataFrame(rows)
    if body.asset_type != asset_type:
        pass  # allow client hint; data is keyed by building
    return run_building_regression(df, building_key, display_name, body)
