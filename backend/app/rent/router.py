"""주거 전월세 rent_stats API."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.config import settings

_VALIDATE_JSON = (
    Path(__file__).resolve().parents[3] / "pipeline" / "rent" / "_seoul_conversion_validate.json"
)
_RB_DIST_JSON = (
    Path(__file__).resolve().parents[3] / "pipeline" / "rent" / "_seoul_rb_distribution.json"
)

from app.rent.db import get_rent_db
from app.rent.conversion_query import list_conversion_compare
from app.rent.query import (
    ASSET_TYPES,
    SORT_KEYS,
    building_rolling,
    detect_rent_structure,
    latest_as_of,
    list_addr1,
    list_addr2,
    list_addr3,
    list_addr4,
    list_buildings,
)
from app.collective.building_geocode import geocode_collective_building, resolve_building_map_points
from app.collective.regression.engine import run_building_regression, run_cohort_regression
from app.collective.schemas import CollectiveRegressionRequest, CollectiveRegressionResponse
from app.rent.map_resolve import resolve_rent_map_codes
from app.rent.tx_query import fetch_regression_rows, list_building_transactions
from app.rent.profile_yearly import build_profile_yearly_payload, completed_calendar_years
from app.rent.sangkwon_query import annual_table, import_meta, list_polygons, series_table
from app.rent.sale_join import JOIN_ASSETS, sale_join
from app.rent.schemas import (
    RentBuildingGeocodeRequest,
    RentBuildingGeocodeResponse,
    RentBuildingListResponse,
    RentBuildingMapPointsRequest,
    RentBuildingMapPointsResponse,
    RentConversionCompareResponse,
    RentFilterMeta,
    RentMapResolveCodesResponse,
    RentProfileYearlyResponse,
    RentRegionOption,
    RentRegionStructure,
    RentSaleJoinResponse,
    RentRollingResponse,
    RentTransactionListResponse,
    RentTransactionRow,
    SangkwonAnnualResponse,
    SangkwonPolygonsResponse,
    SangkwonSeriesResponse,
)

router = APIRouter(prefix="/rent", tags=["rent"])


def _as_of_label(as_of) -> str:
    if as_of is None:
        return ""
    y, m = as_of.year, as_of.month
    return f"{y}년 {m}월말 기준"


@router.get("/meta", response_model=RentFilterMeta)
def rent_meta(
    db: Session = Depends(get_rent_db),
    window_years: int = Query(5, ge=1, le=7),
):
    conn = db.connection()
    as_of = latest_as_of(conn)
    addr1 = list_addr1(conn, as_of, window_years) if as_of else []
    return RentFilterMeta(addr1=addr1, as_of_month=as_of)


@router.get("/regions/addr2", response_model=list[RentRegionOption])
def rent_addr2(
    db: Session = Depends(get_rent_db),
    addr1: str = Query(...),
    window_years: int = Query(5, ge=1, le=7),
):
    conn = db.connection()
    as_of = latest_as_of(conn)
    if as_of is None:
        return []
    return [
        RentRegionOption(name=n, count=c)
        for n, c in list_addr2(conn, as_of, window_years, addr1)
    ]


@router.get("/regions/structure", response_model=RentRegionStructure)
def rent_region_structure(
    db: Session = Depends(get_rent_db),
    addr1: str = Query(...),
    addr2: str = Query(...),
    window_years: int = Query(5, ge=1, le=7),
):
    conn = db.connection()
    as_of = latest_as_of(conn)
    if as_of is None:
        return RentRegionStructure()
    return RentRegionStructure(**detect_rent_structure(conn, as_of, window_years, addr1, addr2))


@router.get("/regions/leaf", response_model=list[RentRegionOption])
def rent_leaf(
    db: Session = Depends(get_rent_db),
    addr1: str = Query(...),
    addr2: str = Query(...),
    window_years: int = Query(5, ge=1, le=7),
    addr3_list: list[str] = Query(default=[]),
    asset_type: list[str] = Query(default=[]),
):
    conn = db.connection()
    as_of = latest_as_of(conn)
    if as_of is None:
        return []
    kinds = [a for a in asset_type if a in ASSET_TYPES]
    return [
        RentRegionOption(name=n, count=c, parent=p)
        for n, c, p in list_addr4(conn, as_of, window_years, addr1, addr2, addr3_list, kinds)
    ]


@router.get("/regions/addr3", response_model=list[RentRegionOption])
def rent_addr3(
    db: Session = Depends(get_rent_db),
    addr1: str = Query(...),
    addr2: str = Query(...),
    window_years: int = Query(5, ge=1, le=7),
    asset_type: list[str] = Query(default=[]),
):
    conn = db.connection()
    as_of = latest_as_of(conn)
    if as_of is None:
        return []
    kinds = [a for a in asset_type if a in ASSET_TYPES]
    return [
        RentRegionOption(name=n, count=c)
        for n, c in list_addr3(conn, as_of, window_years, addr1, addr2, kinds)
    ]


@router.get("/conversion-rates", response_model=RentConversionCompareResponse)
def rent_conversion_compare(
    db: Session = Depends(get_rent_db),
    addr1: str = Query(...),
    asset_type: list[str] = Query(default=[]),
    window_years: list[int] = Query(default=[]),
):
    conn = db.connection()
    as_of = latest_as_of(conn)
    if as_of is None:
        raise HTTPException(503, "임대 마트가 없습니다.")
    kinds = [a for a in asset_type if a in ASSET_TYPES]
    windows = [w for w in window_years if w in (3, 5, 7)]
    items = list_conversion_compare(
        conn,
        as_of=as_of,
        addr1=addr1,
        asset_types=kinds,
        window_years=windows or None,
    )
    return RentConversionCompareResponse(as_of_month=as_of, items=items)


@router.get("/conversion-validate")
def rent_conversion_validate() -> dict[str, Any]:
    if not _VALIDATE_JSON.is_file():
        raise HTTPException(
            404,
            "검증 리포트가 없습니다. py pipeline/rent/validate_conversion.py 를 실행하세요.",
        )
    return json.loads(_VALIDATE_JSON.read_text(encoding="utf-8"))


@router.get("/rb-distribution")
def rent_rb_distribution() -> dict[str, Any]:
    if not _RB_DIST_JSON.is_file():
        raise HTTPException(
            404,
            "r_b 분포 리포트가 없습니다. py pipeline/rent/report_rb_distribution.py 를 실행하세요.",
        )
    return json.loads(_RB_DIST_JSON.read_text(encoding="utf-8"))


@router.get("/buildings", response_model=RentBuildingListResponse)
def rent_buildings(
    db: Session = Depends(get_rent_db),
    addr1: str = Query(...),
    addr2: str = Query(...),
    addr3: Optional[str] = None,
    addr3_list: list[str] = Query(default=[]),
    addr4_list: list[str] = Query(default=[]),
    asset_type: list[str] = Query(default=[]),
    window_years: int = Query(5, ge=1, le=7),
    sort: str = Query("jeonse_median"),
):
    if sort not in SORT_KEYS:
        raise HTTPException(400, f"sort must be one of {', '.join(SORT_KEYS)}")
    conn = db.connection()
    as_of = latest_as_of(conn)
    if as_of is None:
        raise HTTPException(503, "임대 마트가 없습니다. pipeline/rent/build_building_stats.py 를 실행하세요.")
    kinds = [a for a in asset_type if a in ASSET_TYPES] or ["apartment"]
    items, ps, pe, rates = list_buildings(
        db,
        as_of=as_of,
        window_years=window_years,
        addr1=addr1,
        addr2=addr2,
        addr3=addr3,
        addr3_list=addr3_list,
        addr4_list=addr4_list,
        asset_types=kinds,
        sort=sort,
    )
    applied = any(r.gate_passed and r.r_selected for r in rates)
    method = rates[0].method_selected if rates else "mean_simple"
    single_dong = addr3 or (addr3_list[0] if len(addr3_list) == 1 else None)
    scope = "dong" if single_dong and any(r.scope == "dong" and not r.fallback for r in rates) else "sigungu"
    fallback = bool(single_dong) and any(r.fallback for r in rates)
    if sort == "jeonse_equiv_median" and applied:
        items.sort(
            key=lambda x: (
                -(x.jeonse_equiv.median or -1),
                -(x.jeonse_equiv.n),
            )
        )
    return RentBuildingListResponse(
        items=items,
        total=len(items),
        as_of_month=as_of,
        window_years=window_years,
        period_start=ps,
        period_end=pe,
        stats_as_of_label=_as_of_label(as_of),
        conversion_rates=rates,
        conversion_applied=applied,
        conversion_method=method,
        conversion_scope=scope,
        conversion_fallback=fallback,
    )


@router.get("/sale-join", response_model=RentSaleJoinResponse)
def rent_sale_join(
    db: Session = Depends(get_rent_db),
    sale_building_key: str = Query(..., min_length=8),
    asset_type: str = Query(...),
    window_years: int = Query(5, ge=1, le=7),
):
    if asset_type not in JOIN_ASSETS and asset_type != "presale":
        raise HTTPException(400, "invalid asset_type")
    return sale_join(
        db,
        sale_building_key=sale_building_key.strip(),
        asset_type=asset_type,
        window_years=window_years,
    )


@router.get("/buildings/{building_key}/rolling", response_model=RentRollingResponse)
def rent_building_rolling(
    building_key: str,
    db: Session = Depends(get_rent_db),
    asset_type: str = Query("apartment"),
    window_years: int = Query(5, ge=1, le=7),
):
    if asset_type not in ASSET_TYPES:
        raise HTTPException(400, "invalid asset_type")
    conn = db.connection()
    as_of = latest_as_of(conn)
    if as_of is None:
        raise HTTPException(503, "임대 마트가 없습니다.")
    points = building_rolling(
        db,
        building_key=building_key,
        asset_type=asset_type,
        as_of=as_of,
        window_years=window_years,
    )
    return RentRollingResponse(
        building_key=building_key,
        asset_type=asset_type,
        window_years=window_years,
        points=points,
    )


@router.get("/regions/resolve-codes", response_model=RentMapResolveCodesResponse)
def rent_resolve_codes(
    db: Session = Depends(get_rent_db),
    addr1: Optional[str] = None,
    addr2: Optional[str] = None,
    gu: list[str] = Query(default=[]),
    leaf: list[str] = Query(default=[]),
):
    return RentMapResolveCodesResponse(
        **resolve_rent_map_codes(
            db.connection(),
            addr1=addr1,
            addr2=addr2,
            gu_list=gu,
            leaf_list=leaf,
        )
    )


@router.post("/buildings/geocode", response_model=RentBuildingGeocodeResponse)
def rent_geocode_building(body: RentBuildingGeocodeRequest):
    key = (settings.vworld_api_key or "").strip()
    if not key:
        raise HTTPException(503, "VWORLD_API_KEY가 설정되지 않았습니다.")
    result = geocode_collective_building(
        api_key=key,
        addr1=body.addr1,
        addr2=body.addr2,
        jibun_address=body.jibun_address,
        road_address=body.road_address,
    )
    label = (body.label or body.jibun_address or body.road_address or "").strip() or None
    return RentBuildingGeocodeResponse(
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


@router.post("/buildings/map-points", response_model=RentBuildingMapPointsResponse)
def rent_map_points(
    body: RentBuildingMapPointsRequest,
    db: Session = Depends(get_rent_db),
):
    key = (settings.vworld_api_key or "").strip()
    if not key:
        raise HTTPException(503, "VWORLD_API_KEY가 설정되지 않았습니다.")
    items = [item.model_dump() for item in body.buildings[:100]]
    try:
        points, unresolved = resolve_building_map_points(
            db.connection(),
            api_key=key,
            buildings=items,
            table_name="rent_building_geocodes",
        )
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc
    return RentBuildingMapPointsResponse(points=points, unresolved=unresolved)


@router.get("/buildings/{building_key}/transactions", response_model=RentTransactionListResponse)
def rent_building_transactions(
    building_key: str,
    db: Session = Depends(get_rent_db),
    asset_type: Optional[str] = None,
    contract_date_from: Optional[date] = None,
    contract_date_to: Optional[date] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    total, rows = list_building_transactions(
        db,
        building_key=building_key,
        asset_type=asset_type,
        contract_date_from=contract_date_from,
        contract_date_to=contract_date_to,
        page=page,
        page_size=page_size,
    )
    return RentTransactionListResponse(
        total=total,
        items=[RentTransactionRow(**r) for r in rows],
    )


@router.post("/buildings/{building_key}/regression/run", response_model=CollectiveRegressionResponse)
def rent_building_regression(
    building_key: str,
    body: CollectiveRegressionRequest,
    db: Session = Depends(get_rent_db),
    asset_type: Optional[str] = None,
    contract_date_from: Optional[date] = None,
    contract_date_to: Optional[date] = None,
    lease_kind: str = Query("jeonse"),
):
    import pandas as pd

    keys = [building_key]
    rows = fetch_regression_rows(
        db,
        building_keys=keys,
        asset_type=asset_type,
        contract_date_from=contract_date_from,
        contract_date_to=contract_date_to,
        lease_kind=lease_kind,
    )
    if len(rows) < 8:
        raise HTTPException(400, "회귀 표본이 부족합니다. 전세 거래가 더 있는 건물을 선택하세요.")
    df = pd.DataFrame(rows)
    name = str(df["display_name"].dropna().iloc[0]) if "display_name" in df.columns else building_key
    return run_building_regression(df, building_key, name, body)


@router.post("/regression/run", response_model=CollectiveRegressionResponse)
def rent_cohort_regression(
    body: CollectiveRegressionRequest,
    db: Session = Depends(get_rent_db),
    building_key: list[str] = Query(default=[]),
    asset_type: Optional[str] = None,
    contract_date_from: Optional[date] = None,
    contract_date_to: Optional[date] = None,
    lease_kind: str = Query("jeonse"),
):
    import pandas as pd

    keys = [k for k in building_key if k]
    if len(keys) < 1:
        raise HTTPException(400, "building_key가 필요합니다.")
    rows = fetch_regression_rows(
        db,
        building_keys=keys,
        asset_type=asset_type,
        contract_date_from=contract_date_from,
        contract_date_to=contract_date_to,
        lease_kind=lease_kind,
    )
    if len(rows) < 8:
        raise HTTPException(400, "회귀 표본이 부족합니다.")
    df = pd.DataFrame(rows)
    if len(keys) == 1:
        name = str(df["display_name"].dropna().iloc[0]) if len(df) else keys[0]
        return run_building_regression(df, keys[0], name, body)
    names = {
        str(r["building_key"]): str(r.get("display_name") or r["building_key"])
        for r in rows
        if r.get("building_key")
    }
    return run_cohort_regression(df, keys, f"{len(keys)}동", body, building_display_names=names)


def _sangkwon_ready(conn) -> bool:
    try:
        return import_meta(conn) is not None
    except Exception:  # noqa: BLE001
        return False


@router.get("/profile-yearly", response_model=RentProfileYearlyResponse)
def rent_profile_yearly(
    db: Session = Depends(get_rent_db),
    region_level: str = Query(...),
    region_code: str = Query(...),
    window_years: int = Query(3, ge=1, le=5),
    years: list[int] = Query(default=[]),
):
    """지역프로필용 주거 전월세 달력 연간. 건수·보증금 합·월세 합(만/월). 환산 없음."""
    conn = db.connection()
    ys = sorted({int(y) for y in years if 1990 <= int(y) <= 2100})
    if not ys:
        as_of = latest_as_of(conn)
        if as_of is None:
            as_of = date.today()
        ys = completed_calendar_years(as_of, window_years)
    try:
        payload = build_profile_yearly_payload(
            conn,
            region_level=region_level,
            region_code=region_code,
            years=ys,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RentProfileYearlyResponse(**payload)


@router.get("/sangkwon/polygons", response_model=SangkwonPolygonsResponse)
def rent_sangkwon_polygons(
    db: Session = Depends(get_rent_db),
    sido: Optional[str] = Query(None),
):
    conn = db.connection()
    if not _sangkwon_ready(conn):
        return SangkwonPolygonsResponse()
    meta = import_meta(conn) or {}
    features = []
    for row in list_polygons(conn, sido=sido):
        geom = row.get("geom_geojson")
        if isinstance(geom, str):
            geom = json.loads(geom)
        if not geom:
            continue
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "sec_seq": row["sec_seq"],
                    "sec_nm": row["sec_nm"],
                    "sido": row["sido"],
                    "buld_nm": row["buld_nm"],
                },
                "geometry": geom,
            }
        )
    return SangkwonPolygonsResponse(
        features=features,
        latest_year=meta.get("latest_year"),
        source_file=meta.get("source_file") or "",
    )


@router.get("/sangkwon/annual", response_model=SangkwonAnnualResponse)
def rent_sangkwon_annual(
    db: Session = Depends(get_rent_db),
    name: str = Query(..., min_length=1),
    year: Optional[int] = Query(None, ge=2013, le=2100),
):
    conn = db.connection()
    if not _sangkwon_ready(conn):
        return SangkwonAnnualResponse(sec_nm=name)
    return SangkwonAnnualResponse(**annual_table(conn, sec_nm=name.strip(), year=year))


@router.get("/sangkwon/series", response_model=SangkwonSeriesResponse)
def rent_sangkwon_series(
    db: Session = Depends(get_rent_db),
    name: str = Query(..., min_length=1),
    from_year: int = Query(2019, ge=2013, le=2100),
):
    conn = db.connection()
    if not _sangkwon_ready(conn):
        return SangkwonSeriesResponse(sec_nm=name, from_year=from_year)
    return SangkwonSeriesResponse(**series_table(conn, sec_nm=name.strip(), from_year=from_year))
