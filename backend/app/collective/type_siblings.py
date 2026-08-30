"""같은 지번 아파트·오피스텔 sibling.

키·중앙값은 합치지 않는다. 목록 칩·모달 비교·장기 추세 overlay 용.
비주거(도로 cluster)는 지번 단지가 아니라 여기 없다.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.collective.building_stats_query import _table_exists
from app.collective.schemas import BuildingStatsRow, TypeSibling

SIBLING_ASSETS = frozenset({"apartment", "officetel"})
_OTHER = {"apartment": "officetel", "officetel": "apartment"}


def lot_key(bj: object, lot: object) -> tuple[str, str] | None:
    b = str(bj or "").strip()
    l = str(lot or "").strip()
    if not b or not l:
        return None
    return b, l


def siblings_on_lot(
    *,
    asset_type: str,
    building_key: str,
    lot_rows: list[dict[str, Any]],
) -> list[TypeSibling]:
    other = _OTHER.get((asset_type or "").strip())
    if not other:
        return []
    out: list[TypeSibling] = []
    seen: set[str] = set()
    for r in lot_rows:
        at = str(r.get("asset_type") or "").strip()
        bk = str(r.get("building_key") or "").strip()
        if at != other or not bk or bk == building_key or bk in seen:
            continue
        seen.add(bk)
        cnt = int(r.get("count") or 0)
        med = r.get("median")
        mean = r.get("mean")
        out.append(
            TypeSibling(
                asset_type=at,
                building_key=bk,
                display_name=str(r.get("display_name") or ""),
                count=cnt,
                median=float(med) if med is not None else None,
                mean=float(mean) if mean is not None else None,
            )
        )
    out.sort(key=lambda s: (-s.count, s.display_name))
    return out


def attach_type_siblings(
    conn: Connection,
    items: list[BuildingStatsRow],
    *,
    as_of_month: date | None = None,
    window_years: int | None = None,
    year_override: bool = False,
    contract_year_from: int | None = None,
    contract_year_to: int | None = None,
    contract_date_from: date | None = None,
    contract_date_to: date | None = None,
) -> None:
    """목록 페이지 행에 같은 지번 다른 유형을 붙인다. 없으면 그대로."""
    targets = [it for it in items if it.asset_type in SIBLING_ASSETS and it.building_key]
    if not targets:
        return
    keys = list({it.building_key for it in targets})
    rows: list[dict[str, Any]] = []
    use_mart = (
        not year_override
        and as_of_month is not None
        and window_years is not None
        and _table_exists(conn, "public.collective_building_stats")
    )
    if use_mart:
        rows = _fetch_mart_lot_stats(conn, keys, as_of_month, int(window_years))
    if not rows:
        rows = _fetch_live_lot_stats(
            conn,
            keys,
            contract_year_from=contract_year_from,
            contract_year_to=contract_year_to,
            contract_date_from=contract_date_from,
            contract_date_to=contract_date_to,
        )
    if not rows:
        return

    by_pair: dict[tuple[str, str], tuple[str, str]] = {}
    by_lot: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for r in rows:
        lk = lot_key(r.get("bj"), r.get("lot"))
        if lk is None:
            continue
        bk = str(r.get("building_key") or "")
        at = str(r.get("asset_type") or "")
        if bk:
            by_pair[(bk, at)] = lk
        by_lot.setdefault(lk, []).append(r)

    for i, it in enumerate(items):
        if it.asset_type not in SIBLING_ASSETS:
            continue
        lk = by_pair.get((it.building_key, it.asset_type))
        if lk is None:
            continue
        sibs = siblings_on_lot(
            asset_type=it.asset_type,
            building_key=it.building_key,
            lot_rows=by_lot.get(lk, []),
        )
        if not sibs:
            continue
        items[i] = it.model_copy(update={"type_siblings": sibs, "scale_scope": "complex"})


def _fetch_mart_lot_stats(
    conn: Connection,
    keys: list[str],
    as_of_month: date,
    window_years: int,
) -> list[dict[str, Any]]:
    rows = conn.execute(
        text(
            """
            WITH lots AS (
              SELECT DISTINCT
                     btrim(beopjungri_code::text) AS bj,
                     btrim(lot_number) AS lot
              FROM collective_building_stats
              WHERE as_of_month = :as_of
                AND window_years = :wy
                AND building_key = ANY(:keys)
                AND asset_type IN ('apartment', 'officetel')
                AND beopjungri_code IS NOT NULL
                AND lot_number IS NOT NULL
                AND btrim(lot_number) <> ''
            )
            SELECT m.building_key, m.asset_type, m.display_name,
                   m.count, m.median, m.mean,
                   btrim(m.beopjungri_code::text) AS bj,
                   btrim(m.lot_number) AS lot
            FROM collective_building_stats m
            JOIN lots
              ON btrim(m.beopjungri_code::text) = lots.bj
             AND btrim(m.lot_number) = lots.lot
            WHERE m.as_of_month = :as_of
              AND m.window_years = :wy
              AND m.asset_type IN ('apartment', 'officetel')
            """
        ),
        {"as_of": as_of_month, "wy": window_years, "keys": keys},
    ).mappings().all()
    return [dict(r) for r in rows]


def _fetch_live_lot_stats(
    conn: Connection,
    keys: list[str],
    *,
    contract_year_from: int | None = None,
    contract_year_to: int | None = None,
    contract_date_from: Optional[date] = None,
    contract_date_to: Optional[date] = None,
) -> list[dict[str, Any]]:
    extra = ""
    params: dict[str, Any] = {"keys": keys}
    if contract_date_from is not None and contract_date_to is not None:
        extra += " AND t.contract_date >= :cd_from AND t.contract_date <= :cd_to"
        params["cd_from"] = contract_date_from
        params["cd_to"] = contract_date_to
    else:
        if contract_year_from is not None:
            extra += " AND t.contract_year >= :cy_from"
            params["cy_from"] = contract_year_from
        if contract_year_to is not None:
            extra += " AND t.contract_year <= :cy_to"
            params["cy_to"] = contract_year_to
    rows = conn.execute(
        text(
            f"""
            WITH lots AS (
              SELECT DISTINCT
                     btrim(beopjungri_code::text) AS bj,
                     btrim(lot_number) AS lot
              FROM collective_transactions
              WHERE building_key = ANY(:keys)
                AND asset_type IN ('apartment', 'officetel')
                AND is_valid = true
                AND beopjungri_code IS NOT NULL
                AND lot_number IS NOT NULL
                AND btrim(lot_number) <> ''
            )
            SELECT t.building_key, t.asset_type,
                   MAX(t.display_name) AS display_name,
                   COUNT(*)::int AS count,
                   percentile_cont(0.5) WITHIN GROUP (ORDER BY t.unit_price) AS median,
                   AVG(t.unit_price) AS mean,
                   btrim(MAX(t.beopjungri_code)::text) AS bj,
                   MAX(btrim(t.lot_number)) AS lot
            FROM collective_transactions t
            JOIN lots
              ON btrim(t.beopjungri_code::text) = lots.bj
             AND btrim(t.lot_number) = lots.lot
            WHERE t.asset_type IN ('apartment', 'officetel')
              AND t.is_valid = true
              AND t.unit_price IS NOT NULL
              AND t.unit_price > 0
              {extra}
            GROUP BY t.building_key, t.asset_type
            """
        ),
        params,
    ).mappings().all()
    return [dict(r) for r in rows]
