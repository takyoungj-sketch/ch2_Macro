"""복합부동산 built_stats API."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.built.db import get_built_db
from app.built.filters import (
    apply_addr3_filter,
    apply_addr4_filter,
    apply_ri_filter,
    apply_sample_filters,
)
from app.built.region_structure import detect_region_structure
from app.built.regression.engine import predict_regression, run_regression
from app.built.schemas import (
    BuiltFilterMetaResponse,
    BuiltTransactionListResponse,
    BuiltTransactionRow,
    CategoryCountOption,
    NumericRangeHint,
    RegionOption,
    RegionStructureResponse,
    RegressionPredictRequest,
    RegressionPredictResponse,
    RegressionRunRequest,
    RegressionRunResponse,
    RiPick,
    ScopeSampleFilterResponse,
)

router = APIRouter(prefix="/built", tags=["복합부동산(연구)"])


def _parse_ri_picks(raw: list[str]) -> list[RiPick]:
    out: list[RiPick] = []
    for s in raw:
        if "|" not in s:
            continue
        eup, ri = s.split("|", 1)
        eup, ri = eup.strip(), ri.strip()
        if eup and ri:
            out.append(RiPick(eup=eup, ri=ri))
    return out


def _transaction_where(
    *,
    asset_type: Optional[str] = None,
    addr1: Optional[str] = None,
    addr2: Optional[str] = None,
    addr3: Optional[str] = None,
    addr3_list: list[str] | None = None,
    addr4_list: list[str] | None = None,
    ri_pick: list[str] | None = None,
    contract_year_from: Optional[int] = None,
    contract_year_to: Optional[int] = None,
    zone_types: list[str] | None = None,
    building_uses: list[str] | None = None,
    gross_area_min: Optional[float] = None,
    gross_area_max: Optional[float] = None,
    land_area_min: Optional[float] = None,
    land_area_max: Optional[float] = None,
    building_age_min: Optional[float] = None,
    building_age_max: Optional[float] = None,
    road_code_min: Optional[float] = None,
    road_code_max: Optional[float] = None,
) -> tuple[str, dict]:
    clauses = ["is_valid = true"]
    params: dict = {}
    if asset_type:
        clauses.append("asset_type = :asset_type")
        params["asset_type"] = asset_type
    if addr1:
        clauses.append("addr1 = :addr1")
        params["addr1"] = addr1
    if addr2:
        clauses.append("addr2 = :addr2")
        params["addr2"] = addr2
    apply_addr3_filter(clauses, params, addr3, addr3_list or [])
    apply_addr4_filter(clauses, params, None, addr4_list or [])
    apply_ri_filter(clauses, params, _parse_ri_picks(ri_pick or []))
    if contract_year_from is not None:
        clauses.append("contract_year >= :cyf")
        params["cyf"] = contract_year_from
    if contract_year_to is not None:
        clauses.append("contract_year <= :cyt")
        params["cyt"] = contract_year_to
    apply_sample_filters(
        clauses,
        params,
        zone_types=zone_types or None,
        building_uses=building_uses or None,
        gross_area_min=gross_area_min,
        gross_area_max=gross_area_max,
        land_area_min=land_area_min,
        land_area_max=land_area_max,
        building_age_min=building_age_min,
        building_age_max=building_age_max,
        road_code_min=road_code_min,
        road_code_max=road_code_max,
    )
    return " AND ".join(clauses), params


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
    return BuiltFilterMetaResponse(
        asset_types=_distinct("asset_type"),
        contract_years=[int(r.y) for r in years],
        zone_types=_distinct("zone_type"),
        building_uses=_distinct("building_use"),
        addr1_list=_distinct("addr1"),
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
    contract_year_from: Optional[int] = None,
    contract_year_to: Optional[int] = None,
):
    """현재 지역·연도 scope 내 표본 필터 옵션(건수·연속 min/max)."""
    where, params = _transaction_where(
        asset_type=asset_type,
        addr1=addr1,
        addr2=addr2,
        addr3_list=addr3_list,
        addr4_list=addr4_list,
        ri_pick=ri_pick,
        contract_year_from=contract_year_from,
        contract_year_to=contract_year_to,
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
    cont: list[NumericRangeHint] = []
    for col in ("gross_area", "land_area", "building_age", "road_code"):
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
    contract_year_from: Optional[int] = None,
    contract_year_to: Optional[int] = None,
    zone_types: list[str] = Query(default=[]),
    building_uses: list[str] = Query(default=[]),
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
    where, params = _transaction_where(
        asset_type=asset_type,
        addr1=addr1,
        addr2=addr2,
        addr3=addr3,
        addr3_list=addr3_list,
        addr4_list=addr4_list,
        ri_pick=ri_pick,
        contract_year_from=contract_year_from,
        contract_year_to=contract_year_to,
        zone_types=zone_types or None,
        building_uses=building_uses or None,
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
                   trade_year_label, contract_year, zone_type, building_use,
                   building_scale, land_scale, age_bucket, price,
                   gross_area, land_area, building_age, road_code
            FROM built_transactions
            WHERE {where}
            ORDER BY id
            LIMIT :limit OFFSET :offset
            """
        ),
        params,
    ).mappings().all()
    items = [BuiltTransactionRow(**dict(r)) for r in rows]
    return BuiltTransactionListResponse(
        total=int(total or 0),
        page=page,
        page_size=page_size,
        items=items,
    )


@router.get("/regions/addr2")
def list_addr2(db: Session = Depends(get_built_db), addr1: str = Query(...)):
    rows = db.execute(
        text(
            """
            SELECT DISTINCT addr2 AS v FROM built_transactions
            WHERE addr1 = :a1 AND addr2 IS NOT NULL AND btrim(addr2) <> ''
            ORDER BY 1
            """
        ),
        {"a1": addr1},
    ).fetchall()
    return [r.v for r in rows]


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
):
    """flat 시군구: 읍면동 목록. 구가 있는 시: 구 목록."""
    clauses = [
        "addr1 = :a1",
        "addr2 = :a2",
        "addr3 IS NOT NULL",
        "btrim(addr3::text) <> ''",
        "is_valid = true",
    ]
    params: dict = {"a1": addr1, "a2": addr2}
    if asset_type:
        clauses.append("asset_type = :asset_type")
        params["asset_type"] = asset_type
    where = " AND ".join(clauses)
    if with_counts:
        rows = db.execute(
            text(
                f"""
                SELECT addr3 AS name, COUNT(*)::int AS count
                FROM built_transactions
                WHERE {where}
                GROUP BY addr3
                ORDER BY addr3
                """
            ),
            params,
        ).mappings().all()
        return [dict(r) for r in rows]
    rows = db.execute(
        text(
            f"""
            SELECT DISTINCT addr3 AS v FROM built_transactions
            WHERE {where}
            ORDER BY 1
            """
        ),
        params,
    ).fetchall()
    return [r.v for r in rows]


@router.get("/regions/leaf", response_model=list[RegionOption])
def list_leaf_regions(
    db: Session = Depends(get_built_db),
    addr1: str = Query(...),
    addr2: str = Query(...),
    addr3_list: list[str] = Query(default=[]),
    asset_type: Optional[str] = Query(None),
):
    """구-읍면동 2단계 시군구: addr4(읍면동) 목록. addr3_list로 구 필터."""
    clauses = [
        "addr1 = :a1",
        "addr2 = :a2",
        "addr4 IS NOT NULL",
        "btrim(addr4::text) <> ''",
        "is_valid = true",
    ]
    params: dict = {"a1": addr1, "a2": addr2}
    if asset_type:
        clauses.append("asset_type = :asset_type")
        params["asset_type"] = asset_type
    if addr3_list:
        clauses.append("addr3 = ANY(:addr3_list)")
        params["addr3_list"] = addr3_list
    where = " AND ".join(clauses)
    rows = db.execute(
        text(
            f"""
            SELECT addr4 AS name, addr3 AS parent, COUNT(*)::int AS count
            FROM built_transactions
            WHERE {where}
            GROUP BY addr4, addr3
            ORDER BY addr3, addr4
            """
        ),
        params,
    ).mappings().all()
    return [RegionOption(**dict(r)) for r in rows]


@router.get("/regions/ri", response_model=list[RegionOption])
def list_ri_regions(
    db: Session = Depends(get_built_db),
    addr1: str = Query(...),
    addr2: str = Query(...),
    addr3_list: list[str] = Query(default=[]),
    addr4_list: list[str] = Query(default=[]),
    leaf_level: str = Query("addr3", description="addr3=flat 시군구, addr4=구-동 구조"),
    asset_type: Optional[str] = Query(None),
):
    """선택 읍·면·동 하위 리(addr5) 목록. parent=상위 읍·면."""
    clauses = [
        "addr1 = :a1",
        "addr2 = :a2",
        "addr5 IS NOT NULL",
        "btrim(addr5::text) <> ''",
        "is_valid = true",
    ]
    params: dict = {"a1": addr1, "a2": addr2}
    if asset_type:
        clauses.append("asset_type = :asset_type")
        params["asset_type"] = asset_type
    if leaf_level == "addr4" and addr4_list:
        clauses.append("addr4 = ANY(:leaf_list)")
        params["leaf_list"] = addr4_list
    elif addr3_list:
        clauses.append("addr3 = ANY(:leaf_list)")
        params["leaf_list"] = addr3_list
    elif addr4_list:
        clauses.append("addr4 = ANY(:leaf_list)")
        params["leaf_list"] = addr4_list
    where = " AND ".join(clauses)
    rows = db.execute(
        text(
            f"""
            SELECT
                addr5 AS name,
                COALESCE(
                    NULLIF(btrim(addr4::text), ''),
                    NULLIF(btrim(addr3::text), '')
                ) AS parent,
                COUNT(*)::int AS count
            FROM built_transactions
            WHERE {where}
            GROUP BY addr5,
                COALESCE(
                    NULLIF(btrim(addr4::text), ''),
                    NULLIF(btrim(addr3::text), '')
                )
            HAVING COALESCE(
                    NULLIF(btrim(addr4::text), ''),
                    NULLIF(btrim(addr3::text), '')
                ) IS NOT NULL
            ORDER BY parent, addr5
            """
        ),
        params,
    ).mappings().all()
    return [RegionOption(**dict(r)) for r in rows]


@router.post("/regression/run", response_model=RegressionRunResponse)
def regression_run(body: RegressionRunRequest, db: Session = Depends(get_built_db)):
    try:
        return run_regression(db.connection(), body)
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
