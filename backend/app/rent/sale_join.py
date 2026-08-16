"""집합 매매 건물 → 임대 조인 뷰. 맵·마트 조회만. 원장 WRITE 없음."""

from __future__ import annotations

from datetime import date
from typing import Optional

from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session

from app.rent.conversion_query import fetch_building_converted, get_region_rates
from app.rent.query import latest_as_of, row_from_mart
from app.rent.schemas import (
    LeaseMetric,
    RentBuildingRow,
    RentConversionRate,
    RentSaleJoinResponse,
)

JOIN_ASSETS = ("apartment", "rowhouse", "officetel")


def _table_exists(conn: Connection, table: str) -> bool:
    row = conn.execute(
        text("SELECT to_regclass(:t) IS NOT NULL AS ok"),
        {"t": table},
    ).mappings().first()
    return bool(row and row["ok"])


def lookup_rent_key(conn: Connection, *, sale_building_key: str, asset_type: str) -> Optional[str]:
    if not _table_exists(conn, "public.rent_sale_building_map"):
        return None
    row = conn.execute(
        text(
            """
            SELECT rent_building_key
            FROM rent_sale_building_map
            WHERE sale_building_key = :k AND asset_type = :a AND tier = 'exact'
            """
        ),
        {"k": sale_building_key, "a": asset_type},
    ).mappings().first()
    if not row:
        return None
    return str(row["rent_building_key"]).strip() or None


def _mart_row(
    conn: Connection,
    *,
    building_key: str,
    asset_type: str,
    as_of: date,
    window_years: int,
) -> Optional[dict]:
    row = conn.execute(
        text(
            """
            SELECT *
            FROM rent_building_stats
            WHERE building_key = :k
              AND asset_type = :a
              AND as_of_month = :as_of
              AND window_years = :w
            """
        ),
        {"k": building_key, "a": asset_type, "as_of": as_of, "w": window_years},
    ).mappings().first()
    return dict(row) if row else None


def sale_join(
    db: Session,
    *,
    sale_building_key: str,
    asset_type: str,
    window_years: int,
) -> RentSaleJoinResponse:
    if asset_type not in JOIN_ASSETS:
        return RentSaleJoinResponse(joined=False, reason="asset_not_in_scope", window_years=window_years)
    conn = db.connection()
    if not _table_exists(conn, "public.rent_sale_building_map"):
        return RentSaleJoinResponse(joined=False, reason="map_missing", window_years=window_years)
    rent_key = lookup_rent_key(conn, sale_building_key=sale_building_key, asset_type=asset_type)
    if not rent_key:
        return RentSaleJoinResponse(joined=False, reason="no_join", window_years=window_years)
    as_of = latest_as_of(conn)
    if as_of is None:
        return RentSaleJoinResponse(
            joined=False,
            reason="no_rent_stats",
            rent_building_key=rent_key,
            window_years=window_years,
        )
    mart = _mart_row(
        conn,
        building_key=rent_key,
        asset_type=asset_type,
        as_of=as_of,
        window_years=window_years,
    )
    if not mart:
        return RentSaleJoinResponse(
            joined=False,
            reason="no_rent_stats",
            rent_building_key=rent_key,
            as_of_month=as_of,
            window_years=window_years,
        )
    building = row_from_mart(mart)
    addr1 = (mart.get("addr1") or "").strip()
    addr2 = (mart.get("addr2") or "").strip()
    addr3 = (mart.get("addr3") or "").strip() or None
    rates = get_region_rates(
        conn,
        as_of=as_of,
        window_years=window_years,
        addr1=addr1,
        addr2=addr2,
        asset_types=[asset_type],
        addr3=addr3,
    )
    rate = rates.get(asset_type)
    ps, pe = mart.get("period_start"), mart.get("period_end")
    if ps and pe and rate and rate.gate_passed and rate.r_selected:
        converted = fetch_building_converted(
            conn,
            as_of=as_of,
            window_years=window_years,
            addr1=addr1,
            addr2=addr2,
            addr3=addr3,
            asset_types=[asset_type],
            period_start=ps,
            period_end=pe,
            rates=rates,
            building_key=rent_key,
        )
        pair = converted.get((rent_key, asset_type))
        if pair:
            j_eq, m_eq = pair
            building = building.model_copy(update={"jeonse_equiv": j_eq, "monthly_equiv": m_eq})
    return RentSaleJoinResponse(
        joined=True,
        reason="exact",
        sale_building_key=sale_building_key,
        rent_building_key=rent_key,
        asset_type=asset_type,
        as_of_month=as_of,
        window_years=window_years,
        period_start=ps,
        period_end=pe,
        building=building,
        conversion=rate,
        conversion_applied=bool(rate and rate.gate_passed and rate.r_selected),
        conversion_fallback=bool(rate and rate.fallback),
    )
