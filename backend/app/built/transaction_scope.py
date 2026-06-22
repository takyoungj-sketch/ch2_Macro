"""거래 목록·회귀·지역 칩 건수 공통 WHERE."""

from __future__ import annotations

from typing import Optional

from sqlalchemy.engine import Connection

from app.built.asset_scope import apply_asset_type_filter
from app.built.filters import (
    apply_addr3_filter,
    apply_addr4_filter,
    apply_ri_filter,
    apply_sample_filters,
)
from app.built.schemas import RiPick
from app.built.time_scope import apply_contract_date_window, parse_as_of_month
from app.flat_sido_region import apply_addr2_scope
from app.region_scope import apply_region_scope


def parse_ri_picks(raw: list[str]) -> list[RiPick]:
    out: list[RiPick] = []
    for s in raw:
        if "|" not in s:
            continue
        eup, ri = s.split("|", 1)
        eup, ri = eup.strip(), ri.strip()
        if eup and ri:
            out.append(RiPick(eup=eup, ri=ri))
    return out


def build_transaction_where(
    *,
    conn: Connection | None = None,
    asset_type: Optional[str] = None,
    addr1: Optional[str] = None,
    addr2: Optional[str] = None,
    addr3: Optional[str] = None,
    addr3_list: list[str] | None = None,
    addr4_list: list[str] | None = None,
    ri_pick: list[str] | None = None,
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
) -> tuple[str, dict]:
    clauses = ["is_valid = true"]
    params: dict = {}
    apply_asset_type_filter(clauses, params, asset_type)
    ri_parsed = parse_ri_picks(ri_pick or [])
    if addr1 and addr2:
        apply_region_scope(
            clauses,
            params,
            conn=conn,
            table="built_transactions",
            addr1=addr1,
            addr2=addr2,
            addr3=addr3,
            addr3_list=addr3_list,
            addr4_list=addr4_list,
            ri_list=ri_parsed,
            asset_type=asset_type,
        )
    elif addr1:
        clauses.append("addr1 = :addr1")
        params["addr1"] = addr1
        apply_addr3_filter(clauses, params, addr3, addr3_list or [])
        apply_addr4_filter(clauses, params, None, addr4_list or [])
        apply_ri_filter(clauses, params, ri_parsed)
    elif addr2:
        apply_addr2_scope(clauses, params, addr1=addr1, addr2=addr2)
    if contract_year_from is not None:
        clauses.append("contract_year >= :cyf")
        params["cyf"] = contract_year_from
    if contract_year_to is not None:
        clauses.append("contract_year <= :cyt")
        params["cyt"] = contract_year_to
    if as_of_month and window_years:
        apply_contract_date_window(
            clauses,
            params,
            as_of_month=parse_as_of_month(as_of_month),
            window_years=window_years,
        )
    apply_sample_filters(
        clauses,
        params,
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
    return " AND ".join(clauses), params
