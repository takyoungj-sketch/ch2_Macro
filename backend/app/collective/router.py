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
from app.collective.asset_scope import (
    RESIDENTIAL_ASSET_TYPES,
    apply_asset_type_filter,
    includes_presale,
    is_presale_only,
    normalize_asset_type,
    without_presale_asset_param,
)
from app.collective.meta_cache import get_ttl_cached
from app.collective.building_stats_query import (
    building_addr_meta,
    building_rolling_from_mart,
    building_rolling_live,
    building_yearly_from_mart,
    building_yearly_resolved,
    latest_mart_snapshot,
    list_buildings_from_mart,
    list_buildings_live,
    list_presale_lifetime_from_mart,
    list_related_presale_from_annual,
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
    export_filename,
    transactions_csv_bytes,
    tx_list_select_sql,
    tx_row_dict,
    csv_attachment_response,
)
from app.collective.region_structure import detect_region_structure
from app.collective.resolve_codes import resolve_collective_map_codes
from app.region_catalog import list_gu_options, list_leaf_options
from app.collective.building_geocode import (
    geocode_collective_building,
    resolve_building_map_points,
)
from app.collective.schemas import (
    AnalysisExplain,
    AnalysisFeatures,
    BuildingListResponse,
    CollectiveBuildingGeocodeRequest,
    CollectiveBuildingGeocodeResponse,
    CollectiveBuildingMapPointsRequest,
    CollectiveBuildingMapPointsResponse,
    CollectiveFilterMeta,
    CollectiveMapResolveCodesResponse,
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
    RelatedPresaleCandidate,
    RelatedPresaleResponse,
    TransactionListResponse,
    YearlyStatPoint,
    YearlyStatsResponse,
    RollingStatPoint,
    RollingStatsResponse,
)
from app.config import settings

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
    apply_asset_type_filter(
        clauses, params, asset_type, allowed=RESIDENTIAL_ASSET_TYPES
    )
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
        asset_type=asset_type,
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
    def _distinct_addr1() -> list:
        rows = db.execute(
            text(
                """
                SELECT DISTINCT addr1 AS v FROM collective_transactions
                WHERE addr1 IS NOT NULL AND addr1 <> ''
                ORDER BY 1
                """
            )
        ).fetchall()
        return [r.v for r in rows]

    def _distinct_asset_types() -> list:
        rows = db.execute(
            text(
                """
                SELECT DISTINCT asset_type AS v FROM collective_transactions
                WHERE asset_type IS NOT NULL AND asset_type <> ''
                ORDER BY 1
                """
            )
        ).fetchall()
        return [r.v for r in rows]

    year_params: dict = {}
    year_asset_sql = ""
    apply_asset_type_filter(
        [], year_params, asset_type, allowed=RESIDENTIAL_ASSET_TYPES
    )
    if "asset_type" in year_params:
        year_asset_sql = " AND asset_type = :asset_type"
    elif "asset_types" in year_params:
        year_asset_sql = " AND asset_type = ANY(:asset_types)"
    # 연도는 유형별·값은 작아 캐시 키에 asset 포함
    year_cache_key = f"coll:years:{asset_type or 'all'}"

    def _years() -> list[int]:
        rows = db.execute(
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
        return [int(r.y) for r in rows]

    return CollectiveFilterMeta(
        asset_types=get_ttl_cached("coll:asset_types", _distinct_asset_types),
        contract_years=get_ttl_cached(year_cache_key, _years),
        addr1_list=get_ttl_cached("coll:addr1", _distinct_addr1),
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
        asset_type=asset_type,
        valid_sql="is_valid = true",
    )


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
    conn = db.connection()
    info = detect_region_structure(conn, addr1, addr2, asset_type)
    opts = list_leaf_options(
        conn,
        table="collective_transactions",
        addr1=addr1,
        addr2=addr2,
        gu_list=addr3_list,
        asset_type=asset_type,
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
    info = detect_region_structure(conn, addr1, addr2, asset_type)
    if info.get("has_intermediate"):
        opts = list_gu_options(
            conn,
            table="collective_transactions",
            addr1=addr1,
            addr2=addr2,
            asset_type=asset_type,
        )
    else:
        opts = list_leaf_options(
            conn,
            table="collective_transactions",
            addr1=addr1,
            addr2=addr2,
            gu_list=[],
            asset_type=asset_type,
            leaf_level=info.get("leaf_level", "addr3"),
        )
    return opts


@router.get("/regions/resolve-codes", response_model=CollectiveMapResolveCodesResponse)
def resolve_region_codes_for_map(
    db: Session = Depends(get_collective_db),
    asset_type: Optional[str] = Query(None),
    addr1: Optional[str] = Query(None),
    addr2: Optional[str] = Query(None),
    gu: list[str] = Query(default=[], description="구(addr3) 이름"),
    leaf: list[str] = Query(default=[], description="읍·면·동 이름"),
):
    """좌측 addr 칩 → VWorld 지도용 행정코드 (Collective-M1)."""
    result = resolve_collective_map_codes(
        db.connection(),
        asset_type=asset_type,
        addr1=addr1,
        addr2=addr2,
        gu_list=gu,
        leaf_list=leaf,
    )
    return CollectiveMapResolveCodesResponse(**result)


@router.post("/buildings/geocode", response_model=CollectiveBuildingGeocodeResponse)
def geocode_building_for_map(body: CollectiveBuildingGeocodeRequest):
    """선택 건물 지번 지오코딩 라벨 (VWorld Search · parcel 우선)."""
    key = (settings.vworld_api_key or "").strip()
    if not key:
        raise HTTPException(
            status_code=503,
            detail="VWORLD_API_KEY가 설정되지 않았습니다.",
        )
    result = geocode_collective_building(
        api_key=key,
        addr1=body.addr1,
        addr2=body.addr2,
        jibun_address=body.jibun_address,
        road_address=body.road_address,
    )
    label = (body.label or body.jibun_address or body.road_address or "").strip() or None
    return CollectiveBuildingGeocodeResponse(
        ok=bool(result.get("ok")),
        query=str(result.get("query") or ""),
        longitude=result.get("longitude"),
        latitude=result.get("latitude"),
        matched_name=result.get("matched_name"),
        category=result.get("category"),
        label=label,
        building_key=body.building_key,
        error=result.get("error"),
    )


@router.post("/buildings/map-points", response_model=CollectiveBuildingMapPointsResponse)
def map_points_for_buildings(
    body: CollectiveBuildingMapPointsRequest,
    db: Session = Depends(get_collective_db),
):
    """선택 지역 건물명 지도 라벨 좌표 — 지오코딩 결과는 DB에 캐시."""
    if db is None:
        raise HTTPException(503, "collective_stats DB 미연결")
    key = (settings.vworld_api_key or "").strip()
    if not key:
        raise HTTPException(503, "VWORLD_API_KEY가 설정되지 않았습니다.")
    try:
        points, unresolved = resolve_building_map_points(
            db.connection(),
            api_key=key,
            buildings=[item.model_dump() for item in body.buildings],
        )
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc
    return CollectiveBuildingMapPointsResponse(points=points, unresolved=unresolved)


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
    presale_stats_mode: str = Query(
        "rolling",
        pattern="^(lifetime|rolling)$",
        description="분양권 기본=rolling(3/5년, 타유형과 동일). lifetime=전체기간 mart(보조)",
    ),
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
    as_of_month, _ = latest_mart_snapshot(conn)
    year_override = contract_year_from is not None or contract_year_to is not None
    use_presale_lifetime = (
        includes_presale(asset_type)
        and not year_override
        and presale_stats_mode == "lifetime"
    )
    use_presale_rolling = (
        includes_presale(asset_type)
        and not year_override
        and presale_stats_mode == "rolling"
    )
    presale_only = is_presale_only(asset_type)
    meta: dict = {"data_source": "live", "window_years": window_years}

    def _fetch_live(
        *,
        rolling_window: bool,
        asset_type_param: Optional[str],
    ) -> list[BuildingStatsRow]:
        cd_from = cd_to = None
        if rolling_window and as_of_month is not None:
            cd_from, cd_to = period_bounds_for_window(as_of_month, window_years)
        where, params = _base_where(
            conn=conn,
            asset_type=asset_type_param,
            addr1=addr1,
            addr2=addr2,
            addr3=addr3,
            addr3_list=addr3_list or None,
            addr4_list=addr4_list or None,
            contract_year_from=contract_year_from,
            contract_year_to=contract_year_to,
            contract_date_from=cd_from,
            contract_date_to=cd_to,
        )
        single = normalize_asset_type(asset_type_param, allowed=RESIDENTIAL_ASSET_TYPES)
        return list_buildings_live(conn, where, params, asset_type=single)

    items: list[BuildingStatsRow] = []
    sources: list[str] = []

    # 1) 비분양권 — 기존 3/5년 mart·live
    non_presale_param = without_presale_asset_param(asset_type)
    if non_presale_param is not None:
        mart = list_buildings_from_mart(
            conn,
            asset_type=non_presale_param,
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
        use_live = mart is None
        if mart is not None:
            part, part_meta = mart
            if not part and not year_override:
                use_live = True
            else:
                items.extend(part)
                sources.append(part_meta.get("data_source", "mart"))
                meta.update(part_meta)
        if use_live:
            items.extend(
                _fetch_live(
                    rolling_window=not year_override,
                    asset_type_param=non_presale_param,
                )
            )
            sources.append("live")

    # 2) 분양권 — rolling 3·5(기본, 타유형과 동일) / lifetime(보조) / 연도 live
    if includes_presale(asset_type):
        if year_override:
            items.extend(_fetch_live(rolling_window=False, asset_type_param="presale"))
            sources.append("live")
        elif use_presale_lifetime:
            lt = list_presale_lifetime_from_mart(
                conn,
                addr1=addr1,
                addr2=addr2,
                addr3=addr3,
                addr3_list=addr3_list or None,
                addr4_list=addr4_list or None,
            )
            if lt is not None and len(lt[0]) > 0:
                part, part_meta = lt
                items.extend(part)
                sources.append(part_meta.get("data_source", "mart"))
                if presale_only:
                    meta.update(part_meta)
                else:
                    meta["presale_stats_mode"] = "lifetime"
            else:
                items.extend(_fetch_live(rolling_window=False, asset_type_param="presale"))
                sources.append("live")
                meta["presale_stats_mode"] = "lifetime"
        elif use_presale_rolling:
            mart = list_buildings_from_mart(
                conn,
                asset_type="presale",
                addr1=addr1,
                addr2=addr2,
                addr3=addr3,
                addr3_list=addr3_list or None,
                addr4_list=addr4_list or None,
                window_years=window_years,
                as_of_month=as_of_month,
                contract_year_from=None,
                contract_year_to=None,
            )
            if mart is not None and mart[0]:
                part, part_meta = mart
                items.extend(part)
                sources.append(part_meta.get("data_source", "mart"))
                meta["presale_stats_mode"] = "rolling"
            else:
                items.extend(
                    _fetch_live(rolling_window=True, asset_type_param="presale")
                )
                sources.append("live")
                meta["presale_stats_mode"] = "rolling"

    if sources:
        meta["data_source"] = (
            "mart"
            if all(s == "mart" for s in sources)
            else ("live" if "live" in sources else sources[0])
        )
    if presale_only and use_presale_lifetime:
        meta["window_years"] = None
    else:
        meta["window_years"] = window_years

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
    if presale_only and use_presale_lifetime:
        meta.setdefault("period_start", None)
        meta.setdefault("period_end", None)
        meta.setdefault("stats_as_of_label", "분양권 전체 거래기간")
    elif as_of_month is not None:
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
        presale_stats_mode=meta.get("presale_stats_mode"),
    )


def _get_building_meta(db: Session, building_key: str) -> tuple[str, str]:
    meta = building_addr_meta(db.connection(), building_key)
    if not meta:
        raise HTTPException(404, "건물을 찾을 수 없습니다")
    return str(meta["display_name"] or ""), str(meta["asset_type"] or "")


@router.get("/buildings/{building_key}/related-presale", response_model=RelatedPresaleResponse)
def related_presale_annual(
    building_key: str,
    db: Session = Depends(get_collective_db),
    limit: int = Query(20, ge=1, le=50),
    min_score: float = Query(0.45, ge=0.0, le=1.0),
):
    """장기추세용 — 같은 시군구 annual 분양권 후보(이름 유사도). 키 자동 병합 없음."""
    resolved = list_related_presale_from_annual(
        db.connection(),
        building_key,
        limit=limit,
        min_score=min_score,
    )
    if resolved is None:
        raise HTTPException(404, "건물을 찾을 수 없습니다")
    src, candidates = resolved
    return RelatedPresaleResponse(
        source_building_key=building_key,
        source_display_name=str(src.get("display_name") or ""),
        source_asset_type=str(src.get("asset_type") or ""),
        candidates=[RelatedPresaleCandidate(**c) for c in candidates],
    )


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
    tx_select = tx_list_select_sql(db.connection())
    rows = db.execute(
        text(
            f"""
            {tx_select}
            WHERE {where}
            ORDER BY contract_date DESC NULLS LAST, contract_year DESC NULLS LAST, id DESC
            LIMIT :limit OFFSET :offset
            """
        ),
        params,
    ).mappings().all()
    items = [CollectiveTransactionRow(**tx_row_dict(r)) for r in rows]
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
            {tx_list_select_sql(db.connection())}
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

    live = building_rolling_live(
        conn, building_key, window_years=window_years, as_of_month=as_of_month
    )
    if live is not None:
        display_name, points, data_source = live
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
                       AVG(unit_price)::float AS mean,
                       PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY unit_price)::float AS median
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
                mean=round(float(r["mean"]), 1) if r["mean"] is not None else None,
                median=round(float(r["median"]), 1) if r.get("median") is not None else None,
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
    resolved = building_yearly_resolved(conn, building_key)
    if resolved is not None:
        display_name, points, data_source = resolved
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
        YearlyStatPoint(
            year=int(r["year"]),
            count=int(r["count"]),
            mean=round(float(r["mean"]), 1) if r["mean"] is not None else None,
            median=round(float(r["median"]), 1) if r.get("median") is not None else None,
        )
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
    gates = evaluate_analysis_gates(len(rows), cnt_recent, suggest_cohort=True)
    if not gates.floor_index_eligible and not experiment:
        raise HTTPException(
            403,
            detail="; ".join(gates.messages) if gates.messages else "효용지수 분석 최소 표본 미달",
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
        asset_type=asset_type,
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
        diagnostics=raw.get("diagnostics"),
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
    gates = evaluate_analysis_gates(len(rows), cnt_recent, suggest_cohort=True)
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
    gates = evaluate_analysis_gates(len(rows), cnt_recent, suggest_cohort=True)
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
