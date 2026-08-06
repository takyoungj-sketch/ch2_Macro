"""복합부동산 built_stats API."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.built.db import get_built_db
from app.built.region_counts import (
    list_gu_options_scoped,
    list_leaf_options_scoped,
    list_ri_options_scoped,
)
from app.built.transaction_scope import build_transaction_where
from app.built.time_scope import resolve_latest_as_of
from app.flat_sido_region import list_addr2_for_sido
from app.built.region_structure import detect_region_structure
from app.built.regression.engine import predict_regression, run_regression
from app.built.regression.selection.service import compare_regression, suggest_regression
from app.recommendation.adapters.built import recommend_built_regression
from app.recommendation.scope import resolve_built_analysis_scope
from app.built.transaction_export import (
    MAX_BUILT_TX_EXPORT,
    built_csv_response,
    built_transactions_csv_bytes,
    export_filename,
)
from app.built.schemas import (
    BuiltFilterMetaResponse,
    BuiltMapResolveCodesResponse,
    BuiltScopeStatsRow,
    BuiltTransactionListResponse,
    BuiltTransactionRow,
    CategoryCountOption,
    NumericRangeHint,
    RegionOption,
    RegionStructureResponse,
    RegressionPredictRequest,
    RegressionPredictResponse,
    RegressionCompareResponse,
    RegressionRunRequest,
    RegressionRunResponse,
    RegressionScopeResponse,
    RegressionRecommendResponse,
    RecommendationStage1,
    RecommendationSatisfaction,
    RegressionSelectionRequest,
    RegressionSuggestResponse,
    ScopeSampleFilterResponse,
)
from app.built.resolve_codes import resolve_built_map_codes

router = APIRouter(prefix="/built", tags=["복합부동산(연구)"])

_RECOMMEND_SUCCESSOR = "/api/built/regression/recommend"


def _mark_regression_deprecated(response: Response) -> None:
    response.headers["Deprecation"] = "true"
    response.headers["Link"] = f'<{_RECOMMEND_SUCCESSOR}>; rel="successor-version"'


def _serialize_tx_row(row) -> BuiltTransactionRow:
    data = dict(row)
    cd = data.get("contract_date")
    if cd is not None and hasattr(cd, "isoformat"):
        data["contract_date"] = cd.isoformat()
    return BuiltTransactionRow(**data)


def _chip_scope_kwargs(
    *,
    contract_year_from: Optional[int] = None,
    contract_year_to: Optional[int] = None,
    as_of_month: Optional[str] = None,
    window_years: Optional[int] = None,
    zone_types: list[str] | None = None,
    building_uses: list[str] | None = None,
    road_width_labels: list[str] | None = None,
    gross_area_min: Optional[float] = None,
    gross_area_max: Optional[float] = None,
    land_area_min: Optional[float] = None,
    land_area_max: Optional[float] = None,
    building_age_min: Optional[float] = None,
    building_age_max: Optional[float] = None,
    road_code_min: Optional[float] = None,
    road_code_max: Optional[float] = None,
) -> dict:
    return {
        "contract_year_from": contract_year_from,
        "contract_year_to": contract_year_to,
        "as_of_month": as_of_month,
        "window_years": window_years,
        "zone_types": zone_types or None,
        "building_uses": building_uses or None,
        "road_width_labels": road_width_labels or None,
        "gross_area_min": gross_area_min,
        "gross_area_max": gross_area_max,
        "land_area_min": land_area_min,
        "land_area_max": land_area_max,
        "building_age_min": building_age_min,
        "building_age_max": building_age_max,
        "road_code_min": road_code_min,
        "road_code_max": road_code_max,
    }


@router.get("/meta/filters", response_model=BuiltFilterMetaResponse)
def filter_meta(db: Session = Depends(get_built_db)):
    def _distinct(col: str) -> list:
        rows = db.execute(
            text(
                f"""
                SELECT DISTINCT {col} AS v FROM built_transactions
                WHERE {col} IS NOT NULL AND btrim({col}::text) <> ''
                ORDER BY 1
                """
            )
        ).fetchall()
        return [r.v for r in rows]

    years = db.execute(
        text(
            """
            SELECT DISTINCT contract_year AS y FROM built_transactions
            WHERE contract_year IS NOT NULL ORDER BY 1
            """
        )
    ).fetchall()
    conn = db.connection()
    as_of = resolve_latest_as_of(conn)
    asset_types = _distinct("asset_type")
    if "all" not in asset_types:
        asset_types = ["all", *asset_types]
    return BuiltFilterMetaResponse(
        asset_types=asset_types,
        contract_years=[int(r.y) for r in years],
        zone_types=_distinct("zone_type"),
        building_uses=_distinct("building_use"),
        road_width_labels=_distinct("road_width_label"),
        addr1_list=_distinct("addr1"),
        as_of_month=as_of.strftime("%Y-%m"),
        default_window_years=3,
    )


@router.get("/filters/scope", response_model=ScopeSampleFilterResponse)
def scope_sample_filters(
    db: Session = Depends(get_built_db),
    asset_type: Optional[str] = Query(None),
    addr1: Optional[str] = None,
    addr2: Optional[str] = None,
    addr3_list: list[str] = Query(default=[]),
    addr4_list: list[str] = Query(default=[]),
    ri_pick: list[str] = Query(default=[]),
    region_codes: list[str] = Query(default=[]),
    region_code_level: Optional[str] = None,
    region_addrs: list[str] = Query(default=[], description="시도|시군구|읍면동"),
    contract_year_from: Optional[int] = None,
    contract_year_to: Optional[int] = None,
    as_of_month: Optional[str] = None,
    window_years: Optional[int] = None,
):
    """현재 지역·연도 scope 내 표본 필터 옵션(건수·연속 min/max)."""
    where, params = build_transaction_where(
        conn=db.connection(),
        asset_type=asset_type,
        addr1=addr1,
        addr2=addr2,
        addr3_list=addr3_list,
        addr4_list=addr4_list,
        ri_pick=ri_pick,
        region_codes=region_codes,
        region_code_level=region_code_level,
        region_addrs=region_addrs,
        contract_year_from=contract_year_from,
        contract_year_to=contract_year_to,
        as_of_month=as_of_month,
        window_years=window_years,
    )
    total = int(db.execute(text(f"SELECT COUNT(*) FROM built_transactions WHERE {where}"), params).scalar() or 0)
    zone_rows = db.execute(
        text(
            f"""
            SELECT zone_type AS name, COUNT(*)::int AS count
            FROM built_transactions
            WHERE {where}
              AND zone_type IS NOT NULL AND btrim(zone_type::text) <> ''
            GROUP BY zone_type
            ORDER BY count DESC, zone_type
            """
        ),
        params,
    ).mappings().all()
    use_rows = db.execute(
        text(
            f"""
            SELECT building_use AS name, COUNT(*)::int AS count
            FROM built_transactions
            WHERE {where}
              AND building_use IS NOT NULL AND btrim(building_use::text) <> ''
            GROUP BY building_use
            ORDER BY count DESC, building_use
            """
        ),
        params,
    ).mappings().all()
    road_rows = db.execute(
        text(
            f"""
            SELECT road_width_label AS name, COUNT(*)::int AS count
            FROM built_transactions
            WHERE {where}
              AND road_width_label IS NOT NULL AND btrim(road_width_label::text) <> ''
            GROUP BY road_width_label
            ORDER BY count DESC, road_width_label
            """
        ),
        params,
    ).mappings().all()
    cont: list[NumericRangeHint] = []
    for col in ("gross_area", "land_area", "building_age"):
        row = db.execute(
            text(
                f"""
                SELECT MIN({col})::float AS lo, MAX({col})::float AS hi
                FROM built_transactions
                WHERE {where} AND {col} IS NOT NULL
                """
            ),
            params,
        ).one()
        if row.lo is not None and row.hi is not None:
            cont.append(NumericRangeHint(name=col, min=float(row.lo), max=float(row.hi)))
    return ScopeSampleFilterResponse(
        total=total,
        zone_types=[CategoryCountOption(**dict(r)) for r in zone_rows],
        building_uses=[CategoryCountOption(**dict(r)) for r in use_rows],
        road_width_labels=[CategoryCountOption(**dict(r)) for r in road_rows],
        continuous=cont,
    )


@router.get("/transactions", response_model=BuiltTransactionListResponse)
def list_transactions(
    db: Session = Depends(get_built_db),
    asset_type: Optional[str] = Query(None),
    addr1: Optional[str] = None,
    addr2: Optional[str] = None,
    addr3: Optional[str] = None,
    addr3_list: list[str] = Query(default=[]),
    addr4_list: list[str] = Query(default=[]),
    ri_pick: list[str] = Query(default=[], description="eup|ri 형식"),
    region_codes: list[str] = Query(default=[]),
    region_code_level: Optional[str] = None,
    region_addrs: list[str] = Query(default=[], description="시도|시군구|읍면동"),
    contract_year_from: Optional[int] = None,
    contract_year_to: Optional[int] = None,
    as_of_month: Optional[str] = None,
    window_years: Optional[int] = None,
    zone_types: list[str] = Query(default=[]),
    building_uses: list[str] = Query(default=[]),
    road_width_labels: list[str] = Query(default=[]),
    gross_area_min: Optional[float] = None,
    gross_area_max: Optional[float] = None,
    land_area_min: Optional[float] = None,
    land_area_max: Optional[float] = None,
    building_age_min: Optional[float] = None,
    building_age_max: Optional[float] = None,
    road_code_min: Optional[float] = None,
    road_code_max: Optional[float] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
):
    where, params = build_transaction_where(
        conn=db.connection(),
        asset_type=asset_type,
        addr1=addr1,
        addr2=addr2,
        addr3=addr3,
        addr3_list=addr3_list,
        addr4_list=addr4_list,
        ri_pick=ri_pick,
        region_codes=region_codes,
        region_code_level=region_code_level,
        region_addrs=region_addrs,
        contract_year_from=contract_year_from,
        contract_year_to=contract_year_to,
        as_of_month=as_of_month,
        window_years=window_years,
        zone_types=zone_types or None,
        building_uses=building_uses or None,
        road_width_labels=road_width_labels or None,
        gross_area_min=gross_area_min,
        gross_area_max=gross_area_max,
        land_area_min=land_area_min,
        land_area_max=land_area_max,
        building_age_min=building_age_min,
        building_age_max=building_age_max,
        road_code_min=road_code_min,
        road_code_max=road_code_max,
    )
    total = db.execute(text(f"SELECT COUNT(*) FROM built_transactions WHERE {where}"), params).scalar()
    params.update({"limit": page_size, "offset": (page - 1) * page_size})
    rows = db.execute(
        text(
            f"""
            SELECT id, asset_type, addr1, addr2, addr3, addr4, addr5, lot_number,
                   display_address, road_name, road_width_label, deal_type,
                   trade_year_label, contract_year, contract_month, contract_date,
                   zone_type, building_use,
                   building_scale, land_scale, age_bucket, price,
                   gross_area, land_area, building_age, road_code
            FROM built_transactions
            WHERE {where}
            ORDER BY contract_date DESC NULLS LAST, id DESC
            LIMIT :limit OFFSET :offset
            """
        ),
        params,
    ).mappings().all()
    items = [_serialize_tx_row(r) for r in rows]
    return BuiltTransactionListResponse(
        total=int(total or 0),
        page=page,
        page_size=page_size,
        items=items,
    )


_TX_SELECT = """
    SELECT id, asset_type, addr1, addr2, addr3, addr4, addr5, lot_number,
           display_address, road_name, road_width_label, deal_type,
           trade_year_label, contract_year, contract_month, contract_date,
           zone_type, building_use,
           building_scale, land_scale, age_bucket, price,
           gross_area, land_area, building_age, road_code
    FROM built_transactions
"""


@router.get("/transactions/export")
def export_transactions(
    db: Session = Depends(get_built_db),
    asset_type: Optional[str] = Query(None),
    addr1: Optional[str] = None,
    addr2: Optional[str] = None,
    addr3: Optional[str] = None,
    addr3_list: list[str] = Query(default=[]),
    addr4_list: list[str] = Query(default=[]),
    ri_pick: list[str] = Query(default=[], description="eup|ri 형식"),
    region_codes: list[str] = Query(default=[]),
    region_code_level: Optional[str] = None,
    region_addrs: list[str] = Query(default=[], description="시도|시군구|읍면동"),
    contract_year_from: Optional[int] = None,
    contract_year_to: Optional[int] = None,
    as_of_month: Optional[str] = None,
    window_years: Optional[int] = None,
    zone_types: list[str] = Query(default=[]),
    building_uses: list[str] = Query(default=[]),
    road_width_labels: list[str] = Query(default=[]),
    gross_area_min: Optional[float] = None,
    gross_area_max: Optional[float] = None,
    land_area_min: Optional[float] = None,
    land_area_max: Optional[float] = None,
    building_age_min: Optional[float] = None,
    building_age_max: Optional[float] = None,
    road_code_min: Optional[float] = None,
    road_code_max: Optional[float] = None,
):
    """목록 API와 동일 필터로 전체 거래를 CSV(UTF-8 BOM)로 반환."""
    where, params = build_transaction_where(
        conn=db.connection(),
        asset_type=asset_type,
        addr1=addr1,
        addr2=addr2,
        addr3=addr3,
        addr3_list=addr3_list,
        addr4_list=addr4_list,
        ri_pick=ri_pick,
        region_codes=region_codes,
        region_code_level=region_code_level,
        region_addrs=region_addrs,
        contract_year_from=contract_year_from,
        contract_year_to=contract_year_to,
        as_of_month=as_of_month,
        window_years=window_years,
        zone_types=zone_types or None,
        building_uses=building_uses or None,
        road_width_labels=road_width_labels or None,
        gross_area_min=gross_area_min,
        gross_area_max=gross_area_max,
        land_area_min=land_area_min,
        land_area_max=land_area_max,
        building_age_min=building_age_min,
        building_age_max=building_age_max,
        road_code_min=road_code_min,
        road_code_max=road_code_max,
    )
    total = int(db.execute(text(f"SELECT COUNT(*) FROM built_transactions WHERE {where}"), params).scalar() or 0)
    if total > MAX_BUILT_TX_EXPORT:
        raise HTTPException(
            413,
            detail=(
                f"내보내기 상한({MAX_BUILT_TX_EXPORT:,}건)을 초과했습니다. "
                "지역·연도·표본 필터 범위를 줄여 주세요."
            ),
        )
    rows = db.execute(
        text(
            f"""
            {_TX_SELECT}
            WHERE {where}
            ORDER BY contract_date DESC NULLS LAST, id DESC
            """
        ),
        params,
    ).mappings().all()
    scope_label = "_".join(filter(None, [addr1, addr2])) or "built"
    payload = built_transactions_csv_bytes([dict(r) for r in rows], asset_type=asset_type)
    return built_csv_response(payload, export_filename(scope_label=scope_label))


@router.get("/stats/scope", response_model=list[BuiltScopeStatsRow])
def list_scope_stats(
    db: Session = Depends(get_built_db),
    asset_type: Optional[str] = Query(None),
    addr1: Optional[str] = None,
    addr2: Optional[str] = None,
    as_of_month: Optional[str] = None,
    window_years: Optional[int] = Query(None),
):
    """사전집계 mart(built_scope_stats) 조회."""
    clauses = ["1=1"]
    params: dict = {}
    from app.built.asset_scope import apply_asset_type_filter

    apply_asset_type_filter(clauses, params, asset_type)
    if addr1:
        clauses.append("addr1 = :addr1")
        params["addr1"] = addr1
    if addr2 is not None:
        clauses.append("addr2 = :addr2")
        params["addr2"] = addr2
    if as_of_month:
        clauses.append("as_of_month = :as_of_month")
        params["as_of_month"] = parse_as_of_month(as_of_month)
    if window_years is not None:
        clauses.append("window_years = :window_years")
        params["window_years"] = window_years
    where = " AND ".join(clauses)
    try:
        rows = db.execute(
            text(
                f"""
                SELECT asset_type, addr1, addr2,
                       to_char(as_of_month, 'YYYY-MM') AS as_of_month,
                       window_years, tx_count, median_price, mean_price
                FROM built_scope_stats
                WHERE {where}
                ORDER BY addr1, addr2, asset_type, window_years
                """
            ),
            params,
        ).mappings().all()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"built_scope_stats unavailable: {exc}") from exc
    return [BuiltScopeStatsRow(**dict(r)) for r in rows]


@router.get("/regions/addr2")
def list_addr2(
    db: Session = Depends(get_built_db),
    addr1: str = Query(...),
    asset_type: Optional[str] = Query(None),
):
    return list_addr2_for_sido(
        db.connection(),
        table="built_transactions",
        addr1=addr1,
        asset_type=asset_type,
        valid_sql="is_valid = true",
    )


@router.get("/regions/structure", response_model=RegionStructureResponse)
def region_structure(
    db: Session = Depends(get_built_db),
    addr1: str = Query(...),
    addr2: str = Query(...),
    asset_type: Optional[str] = Query(None),
):
    info = detect_region_structure(db.connection(), addr1, addr2, asset_type)
    return RegionStructureResponse(**info)


@router.get("/regions/addr3")
def list_addr3(
    db: Session = Depends(get_built_db),
    addr1: str = Query(...),
    addr2: str = Query(...),
    asset_type: Optional[str] = Query(None),
    with_counts: bool = Query(False),
    contract_year_from: Optional[int] = None,
    contract_year_to: Optional[int] = None,
    as_of_month: Optional[str] = None,
    window_years: Optional[int] = None,
    zone_types: list[str] = Query(default=[]),
    building_uses: list[str] = Query(default=[]),
    road_width_labels: list[str] = Query(default=[]),
    gross_area_min: Optional[float] = None,
    gross_area_max: Optional[float] = None,
    land_area_min: Optional[float] = None,
    land_area_max: Optional[float] = None,
    building_age_min: Optional[float] = None,
    building_age_max: Optional[float] = None,
    road_code_min: Optional[float] = None,
    road_code_max: Optional[float] = None,
):
    """flat 시군구: 읍면동 목록. 구가 있는 시: 구 목록. 건수는 거래목록과 동일 scope."""
    conn = db.connection()
    info = detect_region_structure(conn, addr1, addr2, asset_type)
    scope = _chip_scope_kwargs(
        contract_year_from=contract_year_from,
        contract_year_to=contract_year_to,
        as_of_month=as_of_month,
        window_years=window_years,
        zone_types=zone_types,
        building_uses=building_uses,
        road_width_labels=road_width_labels,
        gross_area_min=gross_area_min,
        gross_area_max=gross_area_max,
        land_area_min=land_area_min,
        land_area_max=land_area_max,
        building_age_min=building_age_min,
        building_age_max=building_age_max,
        road_code_min=road_code_min,
        road_code_max=road_code_max,
    )
    if info.get("has_intermediate"):
        opts = list_gu_options_scoped(
            conn,
            addr1=addr1,
            addr2=addr2,
            asset_type=asset_type,
            **scope,
        )
    else:
        opts = list_leaf_options_scoped(
            conn,
            addr1=addr1,
            addr2=addr2,
            gu_list=[],
            asset_type=asset_type,
            leaf_level=info.get("leaf_level", "addr3"),
            **scope,
        )
    if with_counts:
        return opts
    return [o["name"] for o in opts]


@router.get("/regions/leaf", response_model=list[RegionOption])
def list_leaf_regions(
    db: Session = Depends(get_built_db),
    addr1: str = Query(...),
    addr2: str = Query(...),
    addr3_list: list[str] = Query(default=[]),
    asset_type: Optional[str] = Query(None),
    contract_year_from: Optional[int] = None,
    contract_year_to: Optional[int] = None,
    as_of_month: Optional[str] = None,
    window_years: Optional[int] = None,
    zone_types: list[str] = Query(default=[]),
    building_uses: list[str] = Query(default=[]),
    road_width_labels: list[str] = Query(default=[]),
    gross_area_min: Optional[float] = None,
    gross_area_max: Optional[float] = None,
    land_area_min: Optional[float] = None,
    land_area_max: Optional[float] = None,
    building_age_min: Optional[float] = None,
    building_age_max: Optional[float] = None,
    road_code_min: Optional[float] = None,
    road_code_max: Optional[float] = None,
):
    """구-읍면동 2단계 시군구: addr4(읍면동) 목록. addr3_list로 구 필터."""
    conn = db.connection()
    info = detect_region_structure(conn, addr1, addr2, asset_type)
    leaf_level = info.get("leaf_level", "addr4")
    scope = _chip_scope_kwargs(
        contract_year_from=contract_year_from,
        contract_year_to=contract_year_to,
        as_of_month=as_of_month,
        window_years=window_years,
        zone_types=zone_types,
        building_uses=building_uses,
        road_width_labels=road_width_labels,
        gross_area_min=gross_area_min,
        gross_area_max=gross_area_max,
        land_area_min=land_area_min,
        land_area_max=land_area_max,
        building_age_min=building_age_min,
        building_age_max=building_age_max,
        road_code_min=road_code_min,
        road_code_max=road_code_max,
    )
    opts = list_leaf_options_scoped(
        conn,
        addr1=addr1,
        addr2=addr2,
        gu_list=addr3_list,
        asset_type=asset_type,
        leaf_level=leaf_level,
        **scope,
    )
    return [RegionOption(**o) for o in opts]


@router.get("/regions/ri", response_model=list[RegionOption])
def list_ri_regions(
    db: Session = Depends(get_built_db),
    addr1: str = Query(...),
    addr2: str = Query(...),
    addr3_list: list[str] = Query(default=[]),
    addr4_list: list[str] = Query(default=[]),
    leaf_level: str = Query("addr3", description="addr3=flat 시군구, addr4=구-동 구조"),
    asset_type: Optional[str] = Query(None),
    contract_year_from: Optional[int] = None,
    contract_year_to: Optional[int] = None,
    as_of_month: Optional[str] = None,
    window_years: Optional[int] = None,
    zone_types: list[str] = Query(default=[]),
    building_uses: list[str] = Query(default=[]),
    road_width_labels: list[str] = Query(default=[]),
    gross_area_min: Optional[float] = None,
    gross_area_max: Optional[float] = None,
    land_area_min: Optional[float] = None,
    land_area_max: Optional[float] = None,
    building_age_min: Optional[float] = None,
    building_age_max: Optional[float] = None,
    road_code_min: Optional[float] = None,
    road_code_max: Optional[float] = None,
):
    """선택 읍·면·동 하위 리(addr5) 목록. parent=상위 읍·면."""
    conn = db.connection()
    info = detect_region_structure(conn, addr1, addr2, asset_type)
    # has_ri 메타가 틀려도 leaf 하위 addr5 는 조회 (원장에 있으면 표시)
    effective_leaf = leaf_level or info.get("leaf_level", "addr3")
    leaf_list = addr4_list if effective_leaf == "addr4" else addr3_list
    if not leaf_list and addr4_list:
        leaf_list = addr4_list
    if not leaf_list:
        return []
    scope = _chip_scope_kwargs(
        contract_year_from=contract_year_from,
        contract_year_to=contract_year_to,
        as_of_month=as_of_month,
        window_years=window_years,
        zone_types=zone_types,
        building_uses=building_uses,
        road_width_labels=road_width_labels,
        gross_area_min=gross_area_min,
        gross_area_max=gross_area_max,
        land_area_min=land_area_min,
        land_area_max=land_area_max,
        building_age_min=building_age_min,
        building_age_max=building_age_max,
        road_code_min=road_code_min,
        road_code_max=road_code_max,
    )
    opts = list_ri_options_scoped(
        conn,
        addr1=addr1,
        addr2=addr2,
        gu_list=addr3_list,
        leaf_list=leaf_list,
        leaf_level=effective_leaf,
        asset_type=asset_type,
        **scope,
    )
    return [RegionOption(**o) for o in opts]


@router.get("/regions/resolve-codes", response_model=BuiltMapResolveCodesResponse)
def resolve_region_codes_for_map(
    db: Session = Depends(get_built_db),
    asset_type: Optional[str] = Query(None),
    addr1: Optional[str] = Query(None),
    addr2: Optional[str] = Query(None),
    gu: list[str] = Query(default=[], description="구(addr3) 이름"),
    leaf: list[str] = Query(default=[], description="읍·면·동 이름"),
    ri_pick: list[str] = Query(default=[], description="eup|ri 형식"),
):
    """좌측 addr 칩 → VWorld 지도용 행정코드 (Built-M1)."""
    result = resolve_built_map_codes(
        db.connection(),
        asset_type=asset_type,
        addr1=addr1,
        addr2=addr2,
        gu_list=gu,
        leaf_list=leaf,
        ri_pick=ri_pick,
    )
    return BuiltMapResolveCodesResponse(**result)


@router.get("/regions/lookup-code")
def lookup_region_code(
    db: Session = Depends(get_built_db),
    addr1: Optional[str] = Query(None),
    addr2: Optional[str] = Query(None),
    leaf: Optional[str] = Query(None, description="읍·면·동 또는 리 이름"),
    code: Optional[str] = Query(None, description="VWorld/지도 행정코드 — 있으면 원장에서 역조회"),
    level: str = Query("eupmyeondong"),
    eup: Optional[str] = Query(None, description="리 조회 시 상위 읍·면"),
    asset_type: Optional[str] = Query(None),
):
    """지도 추가 시 VWorld 코드 ↔ 원장 행정코드 정합용.

    원장 historical code를 조회한 뒤 반드시 canonical로 정규화해 반환한다(D-028).
    """
    from app.built.asset_scope import apply_asset_type_filter
    from app.region_canonical import expand_to_ledger_codes, normalize_code, resolve_to_canonical

    conn = db.connection()

    def _response(
        *,
        raw: str | None,
        level: str,
        addr1_val: str | None = None,
        addr2_val: str | None = None,
        leaf_val: str | None = None,
    ) -> dict:
        return {
            "code": normalize_code(conn, raw),
            "level": level,
            "addr1": addr1_val,
            "addr2": addr2_val,
            "leaf": leaf_val,
        }

    lv = (level or "eupmyeondong").strip().lower()
    params: dict = {}
    asset_clauses: list[str] = []
    apply_asset_type_filter(asset_clauses, params, asset_type)
    asset_sql = f" AND {' AND '.join(asset_clauses)}" if asset_clauses else ""

    # 코드만으로 원장 역조회 (시군구명 없을 때)
    raw_code = (code or "").strip()
    if raw_code and not (addr1 and addr2 and leaf):
        canonical = resolve_to_canonical(conn, [raw_code])
        canon = canonical[0] if canonical else raw_code
        ledger_codes = expand_to_ledger_codes(conn, [canon]) or [raw_code]
        emd_set = sorted({c[:8] if len(c) >= 8 else c for c in ledger_codes})
        if lv == "beopjungri":
            row = conn.execute(
                text(
                    f"""
                    SELECT btrim(beopjungri_code::text) AS code,
                           addr1, addr2, addr5 AS leaf, addr4, addr3
                    FROM built_transactions
                    WHERE is_valid
                      AND btrim(beopjungri_code::text) = ANY(:codes)
                      {asset_sql}
                    LIMIT 1
                    """
                ),
                {**params, "codes": ledger_codes},
            ).mappings().first()
        else:
            row = conn.execute(
                text(
                    f"""
                    SELECT btrim(eupmyeondong_code::text) AS code,
                           addr1, addr2,
                           COALESCE(NULLIF(btrim(addr4), ''), NULLIF(btrim(addr3), '')) AS leaf
                    FROM built_transactions
                    WHERE is_valid
                      AND (
                        btrim(eupmyeondong_code::text) = ANY(:emds)
                        OR LEFT(btrim(COALESCE(beopjungri_code::text, '')), 8) = ANY(:emds)
                      )
                      {asset_sql}
                    LIMIT 1
                    """
                ),
                {**params, "emds": emd_set},
            ).mappings().first()
        if not row:
            return _response(raw=None, level=lv)
        return _response(
            raw=str(row["code"]) if row.get("code") else None,
            level=lv,
            addr1_val=row.get("addr1"),
            addr2_val=row.get("addr2"),
            leaf_val=row.get("leaf"),
        )

    a1 = (addr1 or "").strip()
    a2 = (addr2 or "").strip()
    leaf_name = (leaf or "").strip()
    if not a1 or not a2 or not leaf_name:
        return _response(raw=None, level=lv)
    params.update({"a1": a1, "a2": a2, "leaf": leaf_name})
    if lv == "beopjungri":
        eup_sql = ""
        if eup and eup.strip():
            eup_sql = " AND (addr3 = :eup OR addr4 = :eup)"
            params["eup"] = eup.strip()
        row = conn.execute(
            text(
                f"""
                SELECT btrim(beopjungri_code::text) AS code
                FROM built_transactions
                WHERE is_valid
                  AND addr1 = :a1 AND addr2 = :a2
                  AND addr5 = :leaf
                  AND beopjungri_code IS NOT NULL
                  AND btrim(beopjungri_code::text) <> ''
                  {eup_sql}{asset_sql}
                GROUP BY 1
                ORDER BY COUNT(*) DESC
                LIMIT 1
                """
            ),
            params,
        ).first()
        code = str(row.code).strip() if row and row.code else None
        if not code:
            # NULL beopjungri 원장 → active region_codes
            from app.region_canonical import lookup_active_beopjungri_by_ri_picks

            eup_name = (eup or "").strip() or None
            if not eup_name:
                # addr3/4 중 하나를 eup으로 추론하지 못하면 leaf만으로 조회
                rc = conn.execute(
                    text(
                        """
                        SELECT btrim(beopjungri_code::text) AS code
                        FROM region_codes
                        WHERE COALESCE(is_active, TRUE)
                          AND btrim(sido_name::text) = :a1
                          AND btrim(sigungu_name::text) = :a2
                          AND btrim(beopjungri_name::text) = :leaf
                          AND beopjungri_code IS NOT NULL
                          AND btrim(beopjungri_code::text) <> ''
                        ORDER BY beopjungri_code
                        LIMIT 1
                        """
                    ),
                    {"a1": a1, "a2": a2, "leaf": leaf_name},
                ).first()
                code = str(rc.code).strip() if rc and rc.code else None
            else:
                found = lookup_active_beopjungri_by_ri_picks(
                    conn,
                    sido_name=a1,
                    sigungu_name=a2,
                    picks=[(eup_name, leaf_name)],
                )
                code = found[0][0] if found else None
        return _response(
            raw=code,
            level="beopjungri",
            addr1_val=a1,
            addr2_val=a2,
            leaf_val=leaf_name,
        )

    row = conn.execute(
        text(
            f"""
            SELECT btrim(eupmyeondong_code::text) AS code
            FROM built_transactions
            WHERE is_valid
              AND addr1 = :a1 AND addr2 = :a2
              AND (addr3 = :leaf OR addr4 = :leaf)
              AND eupmyeondong_code IS NOT NULL
              AND btrim(eupmyeondong_code::text) <> ''
              {asset_sql}
            GROUP BY 1
            ORDER BY COUNT(*) DESC
            LIMIT 1
            """
        ),
        params,
    ).first()
    if not (row and row.code) and leaf_name.endswith(("읍", "면")) and len(leaf_name) >= 2:
        alt = leaf_name[:-1] + ("면" if leaf_name.endswith("읍") else "읍")
        params_alt = {**params, "leaf": alt}
        row = conn.execute(
            text(
                f"""
                SELECT btrim(eupmyeondong_code::text) AS code
                FROM built_transactions
                WHERE is_valid
                  AND addr1 = :a1 AND addr2 = :a2
                  AND (addr3 = :leaf OR addr4 = :leaf)
                  AND eupmyeondong_code IS NOT NULL
                  AND btrim(eupmyeondong_code::text) <> ''
                  {asset_sql}
                GROUP BY 1
                ORDER BY COUNT(*) DESC
                LIMIT 1
                """
            ),
            params_alt,
        ).first()
    if not (row and row.code):
        # region_codes 마스터 (면↔읍 포함)
        rc = conn.execute(
            text(
                """
                SELECT btrim(eupmyeondong_code::text) AS code
                FROM region_codes
                WHERE COALESCE(is_active, true)
                  AND sido_name = :a1 AND sigungu_name = :a2
                  AND (
                    eupmyeondong_name = :leaf
                    OR (
                      right(:leaf, 1) IN ('읍','면')
                      AND left(eupmyeondong_name, greatest(length(:leaf)-1, 0))
                          = left(:leaf, greatest(length(:leaf)-1, 0))
                      AND right(eupmyeondong_name, 1) IN ('읍','면')
                    )
                  )
                ORDER BY CASE WHEN eupmyeondong_name = :leaf THEN 0 ELSE 1 END
                LIMIT 1
                """
            ),
            {"a1": a1, "a2": a2, "leaf": leaf_name},
        ).first()
        if rc and rc.code:
            return _response(
                raw=str(rc.code),
                level="eupmyeondong",
                addr1_val=a1,
                addr2_val=a2,
                leaf_val=leaf_name,
            )
    return _response(
        raw=str(row.code) if row and row.code else None,
        level="eupmyeondong",
        addr1_val=a1,
        addr2_val=a2,
        leaf_val=leaf_name,
    )

@router.post("/regression/run", response_model=RegressionRunResponse)
def regression_run(body: RegressionRunRequest, db: Session = Depends(get_built_db)):
    try:
        return run_regression(db.connection(), body)
    except ImportError as e:
        raise HTTPException(status_code=500, detail=f"statsmodels 필요: {e}") from e


@router.post("/regression/scope", response_model=RegressionScopeResponse)
def regression_scope(body: RegressionRunRequest, db: Session = Depends(get_built_db)):
    """analysis_scope SSOT — 기본 통계·모형 추천 공통 지역·기간·필터 메타."""
    try:
        return RegressionScopeResponse(
            analysis_scope=resolve_built_analysis_scope(db.connection(), body)
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/regression/recommend", response_model=RegressionRecommendResponse)
def regression_recommend(body: RegressionSelectionRequest, db: Session = Depends(get_built_db)):
    """단계형 모형 탐색 — SSOT 풀 1단계; Twin 2단계는 run_stage2=true(사용자 opt-in)."""
    try:
        return recommend_built_regression(db.connection(), body)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except ImportError as e:
        raise HTTPException(status_code=500, detail=f"statsmodels 필요: {e}") from e


@router.post("/regression/suggest", response_model=RegressionSuggestResponse)
def regression_suggest(
    body: RegressionSelectionRequest,
    response: Response,
    db: Session = Depends(get_built_db),
):
    _mark_regression_deprecated(response)
    try:
        return suggest_regression(db.connection(), body)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except ImportError as e:
        raise HTTPException(status_code=500, detail=f"statsmodels 필요: {e}") from e


@router.post("/regression/compare", response_model=RegressionCompareResponse)
def regression_compare(
    body: RegressionSelectionRequest,
    response: Response,
    db: Session = Depends(get_built_db),
):
    _mark_regression_deprecated(response)
    try:
        return compare_regression(db.connection(), body)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except ImportError as e:
        raise HTTPException(status_code=500, detail=f"statsmodels 필요: {e}") from e


@router.post("/regression/predict", response_model=RegressionPredictResponse)
def regression_predict(body: RegressionPredictRequest, db: Session = Depends(get_built_db)):
    try:
        return predict_regression(db.connection(), body)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except ImportError as e:
        raise HTTPException(status_code=500, detail=f"statsmodels 필요: {e}") from e
