"""지역 칩 건수 — 거래 목록과 동일 scope(롤링·연도·표본 필터)."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.built.transaction_scope import build_transaction_where
from app.region_catalog import _option_row


def _scope_where(
    conn: Connection,
    *,
    addr1: str,
    addr2: str,
    asset_type: str | None,
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
    return build_transaction_where(
        conn=conn,
        asset_type=asset_type,
        addr1=addr1,
        addr2=addr2,
        addr3_list=[],
        addr4_list=[],
        ri_pick=[],
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


def list_gu_options_scoped(
    conn: Connection,
    *,
    addr1: str,
    addr2: str,
    asset_type: str | None,
    **scope,
) -> list[dict]:
    where, params = _scope_where(conn, addr1=addr1, addr2=addr2, asset_type=asset_type, **scope)
    rows = conn.execute(
        text(
            f"""
            SELECT addr3 AS name, COUNT(*)::int AS count
            FROM built_transactions
            WHERE {where}
              AND addr3 IS NOT NULL AND btrim(addr3::text) <> ''
              AND addr3 LIKE '%구'
            GROUP BY addr3
            ORDER BY count DESC, addr3
            """
        ),
        params,
    ).mappings().all()
    return [_option_row(r, check_density=False) for r in rows]


def list_leaf_options_scoped(
    conn: Connection,
    *,
    addr1: str,
    addr2: str,
    gu_list: list[str],
    asset_type: str | None,
    leaf_level: str,
    **scope,
) -> list[dict]:
    where, params = _scope_where(conn, addr1=addr1, addr2=addr2, asset_type=asset_type, **scope)
    gu_sql = ""
    if gu_list:
        gu_sql = "AND addr3 = ANY(:gu_list)"
        params["gu_list"] = gu_list

    if leaf_level == "addr4":
        rows = conn.execute(
            text(
                f"""
                SELECT addr4 AS name, addr3 AS parent, COUNT(*)::int AS count
                FROM built_transactions
                WHERE {where}
                  {gu_sql}
                  AND addr4 IS NOT NULL AND btrim(addr4::text) <> ''
                GROUP BY addr4, addr3
                ORDER BY addr3, count DESC, addr4
                """
            ),
            params,
        ).mappings().all()
    else:
        rows = conn.execute(
            text(
                f"""
                SELECT addr3 AS name, NULL::text AS parent, COUNT(*)::int AS count
                FROM built_transactions
                WHERE {where}
                  AND addr3 IS NOT NULL AND btrim(addr3::text) <> ''
                GROUP BY addr3
                ORDER BY count DESC, addr3
                """
            ),
            params,
        ).mappings().all()
    return [_option_row(r, parent=r.get("parent"), check_density=False) for r in rows]


def list_ri_options_scoped(
    conn: Connection,
    *,
    addr1: str,
    addr2: str,
    gu_list: list[str],
    leaf_list: list[str],
    leaf_level: str,
    asset_type: str | None,
    **scope,
) -> list[dict]:
    if not leaf_list:
        return []
    where, params = _scope_where(conn, addr1=addr1, addr2=addr2, asset_type=asset_type, **scope)

    if leaf_level == "addr4":
        params["leaf_list"] = leaf_list
        leaf_sql = "AND addr4 = ANY(:leaf_list)"
        if gu_list:
            params["gu_list"] = gu_list
            leaf_sql += " AND addr3 = ANY(:gu_list)"
    else:
        params["leaf_list"] = leaf_list
        leaf_sql = "AND addr3 = ANY(:leaf_list)"

    rows = conn.execute(
        text(
            f"""
            SELECT
                addr5 AS name,
                COALESCE(NULLIF(btrim(addr4::text), ''), NULLIF(btrim(addr3::text), '')) AS parent,
                COUNT(*)::int AS count
            FROM built_transactions
            WHERE {where}
              {leaf_sql}
              AND addr5 IS NOT NULL AND btrim(addr5::text) <> ''
            GROUP BY addr5,
                COALESCE(NULLIF(btrim(addr4::text), ''), NULLIF(btrim(addr3::text), ''))
            ORDER BY parent, count DESC, addr5
            """
        ),
        params,
    ).mappings().all()
    return [_option_row(r, parent=r.get("parent"), check_density=False) for r in rows]
