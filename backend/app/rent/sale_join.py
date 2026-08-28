"""집합 매매 건물 → 임대 조인 뷰. 맵·마트 조회만. 원장 WRITE 없음."""

from __future__ import annotations

import logging
from datetime import date
from typing import Optional

from sqlalchemy import bindparam, text
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

log = logging.getLogger(__name__)

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


def jeonse_to_sale_pct(jeonse_mean: float | None, sale_mean: float | None) -> float | None:
    """전세전환 평균 / 매매 평균 × 100."""
    if jeonse_mean is None or sale_mean is None or sale_mean <= 0:
        return None
    return round(float(jeonse_mean) / float(sale_mean) * 100.0, 1)


def apply_sale_metrics(
    items: list[RentBuildingRow],
    sale_by_key: dict[tuple[str, str], tuple[int, float | None]],
) -> list[RentBuildingRow]:
    """(rent_key, asset_type) → (n, mean) 을 목록 행에 붙인다."""
    out: list[RentBuildingRow] = []
    for row in items:
        key = (row.building_key, row.asset_type)
        hit = sale_by_key.get(key)
        if not hit:
            out.append(row)
            continue
        n, mean = hit
        sale = LeaseMetric(n=n, mean=mean)
        out.append(
            row.model_copy(
                update={
                    "sale": sale,
                    "jeonse_to_sale_pct": jeonse_to_sale_pct(row.jeonse_equiv.mean, mean),
                }
            )
        )
    return out


def attach_sale_list_metrics(
    rent_conn: Connection,
    items: list[RentBuildingRow],
    *,
    window_years: int,
) -> list[RentBuildingRow]:
    """정확 키 맵 + 집합 마트 평균. 실패해도 목록은 그대로."""
    if not items:
        return items
    pairs = [
        (row.building_key, row.asset_type)
        for row in items
        if row.asset_type in JOIN_ASSETS and row.building_key
    ]
    if not pairs or not _table_exists(rent_conn, "public.rent_sale_building_map"):
        return items
    keys = sorted({k for k, _ in pairs})
    assets = sorted({a for _, a in pairs})
    try:
        stmt = text(
            """
            SELECT rent_building_key, sale_building_key, asset_type
            FROM rent_sale_building_map
            WHERE tier = 'exact'
              AND rent_building_key IN :keys
              AND asset_type IN :assets
            """
        ).bindparams(
            bindparam("keys", expanding=True),
            bindparam("assets", expanding=True),
        )
        map_rows = rent_conn.execute(stmt, {"keys": keys, "assets": assets}).mappings().all()
    except Exception:
        log.exception("rent_sale_building_map lookup failed")
        return items
    want = set(pairs)
    sale_keys: dict[tuple[str, str], str] = {}
    for r in map_rows:
        rent_k = str(r["rent_building_key"]).strip()
        asset = r["asset_type"] or ""
        if (rent_k, asset) not in want:
            continue
        sale_k = str(r["sale_building_key"]).strip()
        if sale_k:
            sale_keys[(rent_k, asset)] = sale_k
    if not sale_keys:
        return items

    try:
        from app.collective.db import get_collective_engine

        eng = get_collective_engine()
    except Exception:
        log.exception("collective engine missing")
        return items
    if eng is None:
        return items

    coll_keys = sorted(set(sale_keys.values()))
    coll_assets = sorted({a for _, a in sale_keys})
    try:
        with eng.connect() as cconn:
            as_of = cconn.execute(
                text(
                    """
                    SELECT max(as_of_month)
                    FROM collective_building_stats
                    WHERE window_years = :w
                    """
                ),
                {"w": window_years},
            ).scalar()
            if as_of is None:
                return items
            stmt = text(
                """
                SELECT building_key, asset_type, count, mean
                FROM collective_building_stats
                WHERE as_of_month = :as_of
                  AND window_years = :w
                  AND building_key IN :keys
                  AND asset_type IN :assets
                """
            ).bindparams(
                bindparam("keys", expanding=True),
                bindparam("assets", expanding=True),
            )
            stats = cconn.execute(
                stmt,
                {"as_of": as_of, "w": window_years, "keys": coll_keys, "assets": coll_assets},
            ).mappings().all()
    except Exception:
        log.exception("collective_building_stats lookup failed")
        return items

    by_sale: dict[tuple[str, str], tuple[int, float | None]] = {}
    for r in stats:
        sk = str(r["building_key"]).strip()
        at = r["asset_type"] or ""
        mean = float(r["mean"]) if r.get("mean") is not None else None
        by_sale[(sk, at)] = (int(r["count"] or 0), mean)

    sale_by_rent: dict[tuple[str, str], tuple[int, float | None]] = {}
    for rent_pair, sale_k in sale_keys.items():
        hit = by_sale.get((sale_k, rent_pair[1]))
        if hit:
            sale_by_rent[rent_pair] = hit
    return apply_sale_metrics(items, sale_by_rent)


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
