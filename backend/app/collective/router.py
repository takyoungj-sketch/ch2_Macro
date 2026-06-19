"""집합부동산 collective_stats API."""

from __future__ import annotations

from datetime import date
from typing import Optional

import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session

from app.collective.analysis_explain import (
    build_residential_floor_index_explain,
    build_residential_regression_explain,
)
from app.collective.analysis_gates import count_recent_transactions, evaluate_analysis_gates
from app.collective.building_stats_query import (
    building_rolling_from_mart,
    building_yearly_from_mart,
    latest_mart_snapshot,
    list_buildings_from_mart,
    list_buildings_live,
    normalize_asset_type,
    stats_as_of_label,
    stats_reference_date,
)
from app.collective.db import get_collective_db
from app.collective.filters import apply_period_filters, apply_region_filters, apply_year_filters
from app.v2_stats_windows import period_bounds_for_window
from app.flat_sido_region import list_addr2_for_sido
from app.collective.floor_index_regression import compute_residential_floor_index_regression
from app.collective.regression.engine import predict_regression, run_building_regression
from app.collective.transaction_export import (
    MAX_COLLECTIVE_TX_EXPORT,
    TX_SELECT,
    export_filename,
    transactions_csv_bytes,
    csv_attachment_response,
)
from app.collective.region_structure import detect_region_structure
from app.region_catalog import list_gu_options, list_leaf_options
from app.collective.schemas import (
    AnalysisExplain,
    AnalysisFeatures,
    BuildingListResponse,
    CollectiveFilterMeta,
    CollectiveRegressionPredictRequest,
    CollectiveRegressionPredictResponse,
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
    RollingStatPoint,
    RollingStatsResponse,
)
router = APIRouter(prefix="/collective", tags=["집합부동산"])


def _base_where(
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
) -> tuple[str, dict]:
    clauses = ["is_valid = true", "unit_price IS NOT NULL", "unit_price > 0"]
    params: dict = {}
    asset_filter = normalize_asset_type(asset_type)
    if asset_filter:
        clauses.append("asset_type = :asset_type")
        params["asset_type"] = asset_filter
    apply_region_filters(
        clauses,
        params,
        conn=conn,
        table="collective_transactions",
        addr1=addr1,
        addr2=addr2,
        addr3=addr3,
        addr3_list=addr3_list,
        addr4_list=addr4_list,
        asset_type=normalize_asset_type(asset_type),
    )
    apply_period_filters(
        clauses,
        params,
        contract_date_from=contract_date_from,
        contract_date_to=contract_date_to,
        contract_year_from=contract_year_from,
        contract_year_to=contract_year_to,
    )
    return " AND ".join(clauses), params


@router.get("/meta/filters", response_model=CollectiveFilterMeta)
def filter_meta(
    db: Session = Depends(get_collective_db),
    asset_type: Optional[str] = Query(None),
):
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

    year_params: dict = {}
    year_asset_sql = ""
    af = normalize_asset_type(asset_type)
    if af:
        year_asset_sql = " AND asset_type = :asset_type"
        year_params["asset_type"] = af
    years = db.execute(
        text(
            f"""
            SELECT DISTINCT contract_year AS y FROM collective_transactions
            WHERE contract_year IS NOT NULL
              AND is_valid = true
              {year_asset_sql}
            ORDER BY 1
            """
        ),
        year_params,
    ).fetchall()
    return CollectiveFilterMeta(
        asset_types=_distinct("asset_type"),
        contract_years=[int(r.y) for r in years],
        addr1_list=_distinct("addr1"),
    )


@router.get("/regions/addr2")
def list_addr2(
    db: Session = Depends(get_collective_db),
    addr1: str = Query(...),
    asset_type: Optional[str] = Query(None),
):
    return list_addr2_for_sido(
        db.connection(),
        table="collective_transactions",
        addr1=addr1,
        asset_type=normalize_asset_type(asset_type),
        valid_sql="is_valid = true",
    )


@router.get("/regions/structure", response_model=RegionStructureResponse)
def region_structure(
    db: Session = Depends(get_collective_db),
    addr1: str = Query(...),
    addr2: str = Query(...),
    asset_type: Optional[str] = Query(None),
):
    info = detect_region_structure(db.connection(), addr1, addr2, normalize_asset_type(asset_type))
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
    conn = db.connection()
    info = detect_region_structure(conn, addr1, addr2, normalize_asset_type(asset_type))
    opts = list_leaf_options(
        conn,
        table="collective_transactions",
        addr1=addr1,
        addr2=addr2,
        gu_list=addr3_list,
        asset_type=normalize_asset_type(asset_type),
        leaf_level=info.get("leaf_level", "addr4"),
    )
    return [RegionOption(**o) for o in opts]


@router.get("/regions/addr3")
def list_addr3(
    db: Session = Depends(get_collective_db),
    addr1: str = Query(...),
    addr2: str = Query(...),
    asset_type: Optional[str] = Query(None),
):
    conn = db.connection()
    info = detect_region_structure(conn, addr1, addr2, normalize_asset_type(asset_type))
    if info.get("has_intermediate"):
        opts = list_gu_options(
            conn,
            table="collective_transactions",
            addr1=addr1,
            addr2=addr2,
            asset_type=normalize_asset_type(asset_type),
        )
    else:
        opts = list_leaf_options(
            conn,
            table="collective_transactions",
            addr1=addr1,
            addr2=addr2,
            gu_list=[],
            asset_type=normalize_asset_type(asset_type),
            leaf_level=info.get("leaf_level", "addr3"),
        )
    return opts


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
    window_years: int = Query(5, ge=1, le=5),
    sort: str = Query("count", pattern="^(count|mean|display_name|address)$"),
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
    asset_filter = normalize_asset_type(asset_type)
    as_of_month, _ = latest_mart_snapshot(conn)
    meta: dict = {"data_source": "live", "window_years": window_years}
    mart = list_buildings_from_mart(
        conn,
        asset_type=normalize_asset_type(asset_type),
        addr1=addr1,
        addr2=addr2,
        addr3=addr3,
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
        where, params = _base_where(
            conn=conn,
            asset_type=normalize_asset_type(asset_type),
            addr1=addr1,
            addr2=addr2,
            addr3=addr3,
            addr3_list=addr3_list or None,
            addr4_list=addr4_list or None,
            contract_year_from=contract_year_from,
            contract_year_to=contract_year_to,
        )
        items = list_buildings_live(conn, where, params, asset_type=asset_filter)

    if sort == "display_name":
        items.sort(key=lambda x: x.display_name)
    elif sort == "address":
        items.sort(key=lambda x: (x.jibun_address or "—", x.display_name))
    elif sort == "mean":
        items.sort(key=lambda x: (x.mean or 0), reverse=True)
    else:
        items.sort(key=lambda x: x.count, reverse=True)

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
    return BuildingListResponse(
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


def _tx_row_dict(r) -> dict:
    d = dict(r)
    cd = d.get("contract_date")
    if cd is not None and hasattr(cd, "isoformat"):
        d["contract_date"] = cd.isoformat()
    return d


@router.get("/buildings/{building_key}/transactions", response_model=TransactionListResponse)
def building_transactions(
    building_key: str,
    db: Session = Depends(get_collective_db),
    contract_year_from: Optional[int] = None,
    contract_year_to: Optional[int] = None,
    contract_date_from: Optional[date] = None,
    contract_date_to: Optional[date] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    clauses = ["building_key = :bk", "is_valid = true"]
    params: dict = {"bk": building_key}
    apply_period_filters(
        clauses,
        params,
        contract_date_from=contract_date_from,
        contract_date_to=contract_date_to,
        contract_year_from=contract_year_from,
        contract_year_to=contract_year_to,
    )
    where = " AND ".join(clauses)
    total = db.execute(text(f"SELECT COUNT(*) FROM collective_transactions WHERE {where}"), params).scalar()
    params.update({"limit": page_size, "offset": (page - 1) * page_size})
    rows = db.execute(
        text(
            f"""
            SELECT id, asset_type, building_key, display_name,
                   addr1, addr2, addr3, contract_year, contract_month, contract_date,
                   exclusive_area, land_area, price, unit_price, floor, dong, housing_subtype, building_age,
                   buyer_type, seller_type, deal_type, road_name
            FROM collective_transactions
            WHERE {where}
            ORDER BY contract_date DESC NULLS LAST, contract_year DESC NULLS LAST, id DESC
            LIMIT :limit OFFSET :offset
            """
        ),
        params,
    ).mappings().all()
    items = [CollectiveTransactionRow(**_tx_row_dict(r)) for r in rows]
    return TransactionListResponse(total=int(total or 0), items=items)


@router.get("/buildings/{building_key}/transactions/export")
def building_transactions_export(
    building_key: str,
    db: Session = Depends(get_collective_db),
    contract_year_from: Optional[int] = None,
    contract_year_to: Optional[int] = None,
    contract_date_from: Optional[date] = None,
    contract_date_to: Optional[date] = None,
):
    """목록 API와 동일 필터로 전체 거래를 CSV(UTF-8 BOM)로 반환."""
    display_name, asset_type = _get_building_meta(db, building_key)
    clauses = ["building_key = :bk", "is_valid = true"]
    params: dict = {"bk": building_key}
    apply_period_filters(
        clauses,
        params,
        contract_date_from=contract_date_from,
        contract_date_to=contract_date_to,
        contract_year_from=contract_year_from,
        contract_year_to=contract_year_to,
    )
    where = " AND ".join(clauses)
    total = int(db.execute(text(f"SELECT COUNT(*) FROM collective_transactions WHERE {where}"), params).scalar() or 0)
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
            {TX_SELECT}
            WHERE {where}
            ORDER BY contract_date DESC NULLS LAST, contract_year DESC NULLS LAST, id DESC
            """
        ),
        params,
    ).mappings().all()
    payload = transactions_csv_bytes([dict(r) for r in rows], asset_type=asset_type)
    filename = export_filename(display_name="", fallback_key=building_key)
    return csv_attachment_response(payload, filename)


@router.get("/buildings/{building_key}/stats/rolling", response_model=RollingStatsResponse)
def building_stats_rolling(
    building_key: str,
    db: Session = Depends(get_collective_db),
    window_years: int = Query(5, ge=1, le=5),
):
    conn = db.connection()
    as_of_month, _ = latest_mart_snapshot(conn)
    mart = building_rolling_from_mart(
        conn, building_key, window_years=window_years, as_of_month=as_of_month
    )
    if mart is not None:
        display_name, points, data_source = mart
        return RollingStatsResponse(
            building_key=building_key,
            display_name=display_name,
            window_years=window_years,
            as_of_month=as_of_month.isoformat() if as_of_month else None,
            points=[RollingStatPoint(**p) for p in points],
            data_source=data_source,
        )

    display_name, _ = _get_building_meta(db, building_key)
    return RollingStatsResponse(
        building_key=building_key,
        display_name=display_name,
        window_years=window_years,
        points=[],
        data_source="live",
    )


@router.get("/buildings/{building_key}/stats/by-year", response_model=YearlyStatsResponse)
def building_stats_by_year(
    building_key: str,
    db: Session = Depends(get_collective_db),
    contract_date_from: Optional[date] = None,
    contract_date_to: Optional[date] = None,
):
    display_name, _ = _get_building_meta(db, building_key)
    if contract_date_from is not None or contract_date_to is not None:
        clauses = ["building_key = :bk", "is_valid = true", "contract_year IS NOT NULL"]
        params: dict = {"bk": building_key}
        apply_period_filters(
            clauses,
            params,
            contract_date_from=contract_date_from,
            contract_date_to=contract_date_to,
        )
        where = " AND ".join(clauses)
        rows = db.execute(
            text(
                f"""
                SELECT contract_year AS year,
                       COUNT(*)::int AS count,
                       AVG(unit_price)::float AS mean
                FROM collective_transactions
                WHERE {where}
                GROUP BY contract_year
                ORDER BY contract_year
                """
            ),
            params,
        ).mappings().all()
        points = [
            YearlyStatPoint(
                year=int(r["year"]),
                count=int(r["count"]),
                mean=round(float(r["mean"]), 1) if r["mean"] else None,
            )
            for r in rows
        ]
        return YearlyStatsResponse(
            building_key=building_key,
            display_name=display_name,
            points=points,
            data_source="live",
        )

    conn = db.connection()
    mart = building_yearly_from_mart(conn, building_key)
    if mart is not None:
        display_name, points, data_source = mart
        return YearlyStatsResponse(
            building_key=building_key,
            display_name=display_name,
            points=[YearlyStatPoint(**p) for p in points],
            data_source=data_source,
        )

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
    return YearlyStatsResponse(
        building_key=building_key,
        display_name=display_name,
        points=points,
        data_source="live",
    )


@router.get("/buildings/{building_key}/histogram", response_model=HistogramResponse)
def building_histogram(
    building_key: str,
    db: Session = Depends(get_collective_db),
    bins: int = Query(12, ge=4, le=40),
    contract_year: Optional[int] = None,
    contract_date_from: Optional[date] = None,
    contract_date_to: Optional[date] = None,
):
    clauses = ["building_key = :bk", "is_valid = true", "unit_price IS NOT NULL"]
    params: dict = {"bk": building_key}
    apply_period_filters(
        clauses,
        params,
        contract_date_from=contract_date_from,
        contract_date_to=contract_date_to,
    )
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
    dimension: str = Query("floor", pattern="^(floor|dong|area|rights)$"),
    floor_mode: str = Query("relative", pattern="^(relative|dummy|grouped|linear)$"),
    contract_year_from: Optional[int] = None,
    contract_year_to: Optional[int] = None,
    contract_date_from: Optional[date] = None,
    contract_date_to: Optional[date] = None,
    experiment: bool = Query(False, description="실험 단계: 표본 게이트 우회"),
):
    import pandas as pd

    display_name, asset_type = _get_building_meta(db, building_key)
    where, params = _base_where(
        conn=db.connection(),
        contract_year_from=contract_year_from,
        contract_year_to=contract_year_to,
        contract_date_from=contract_date_from,
        contract_date_to=contract_date_to,
    )
    params["bk"] = building_key
    rows = db.execute(
        text(
            f"""
            SELECT unit_price, floor, dong, housing_subtype, exclusive_area,
                   contract_year, contract_month, building_age, building_year
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
    raw = compute_residential_floor_index_regression(
        df, asset_type=asset_type, dimension=dimension, floor_mode=floor_mode
    )
    cells = [FloorIndexCell(**c) for c in raw["cells"]]
    explain = AnalysisExplain(**build_residential_floor_index_explain(raw=raw, asset_type=asset_type))
    return FloorIndexResponse(
        building_key=building_key,
        display_name=display_name,
        asset_type=normalize_asset_type(asset_type),
        dimension=raw["dimension"],
        method=raw.get("method"),
        reference_floor=raw.get("reference_floor"),
        controls=raw.get("controls") or [],
        n_total=raw["n_total"],
        n_regression=raw.get("n_regression"),
        r_squared=raw.get("r_squared"),
        baseline_median=raw["baseline_median"],
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
    apply_period_filters(
        clauses,
        params,
        contract_date_from=body.contract_date_from,
        contract_date_to=body.contract_date_to,
        contract_year_from=body.contract_year_from,
        contract_year_to=body.contract_year_to,
    )
    where = " AND ".join(clauses)
    rows = db.execute(
        text(
            f"""
            SELECT price, unit_price, exclusive_area, building_age, floor, dong, housing_subtype, contract_year
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
    result = run_building_regression(df, building_key, display_name, body)
    return result.model_copy(
        update={
            "explain": AnalysisExplain(
                **build_residential_regression_explain(result, body, asset_type=asset_type),
            ),
        }
    )


@router.post("/buildings/{building_key}/regression/predict", response_model=CollectiveRegressionPredictResponse)
def building_regression_predict(
    building_key: str,
    body: CollectiveRegressionPredictRequest,
    db: Session = Depends(get_collective_db),
):
    import pandas as pd

    display_name, asset_type = _get_building_meta(db, building_key)
    clauses = ["building_key = :bk", "is_valid = true"]
    params: dict = {"bk": building_key}
    apply_period_filters(
        clauses,
        params,
        contract_date_from=body.contract_date_from,
        contract_date_to=body.contract_date_to,
        contract_year_from=body.contract_year_from,
        contract_year_to=body.contract_year_to,
    )
    where = " AND ".join(clauses)
    rows = db.execute(
        text(
            f"""
            SELECT price, unit_price, exclusive_area, building_age, floor, dong, housing_subtype, contract_year
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
            detail="; ".join(gates.messages) if gates.messages else "회귀 예측 최소 표본 미달",
        )

    df = pd.DataFrame(rows)
    try:
        raw = predict_regression(df, body, body.inputs, cohort_mode=False)
    except ValueError as exc:
        raise HTTPException(400, detail=str(exc)) from exc
    return CollectiveRegressionPredictResponse(**raw)


from app.collective.cohort_router import router as cohort_router  # noqa: E402

router.include_router(cohort_router)
from app.collective_commercial.router import router as commercial_router  # noqa: E402

router.include_router(commercial_router)
