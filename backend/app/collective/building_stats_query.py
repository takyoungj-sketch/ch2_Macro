"""collective_building_stats mart 조회 + live fallback."""

from __future__ import annotations

from datetime import date
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.collective.address import split_building_addresses
from app.collective.analysis_gates import count_recent_transactions, evaluate_analysis_gates
from app.collective.filters import apply_region_filters
from app.collective.schemas import AnalysisFeatures, BuildingStatsRow
from app.stats_utils import compute_stats
from app.v2_stats_windows import period_bounds_for_window

ASSET_TYPE_ORDER = ("apartment", "rowhouse", "officetel", "presale")


def normalize_asset_type(asset_type: Optional[str]) -> Optional[str]:
    if not asset_type or asset_type == "all":
        return None
    return asset_type


def asset_type_sort_key(asset_type: str | None) -> int:
    if not asset_type:
        return 99
    try:
        return ASSET_TYPE_ORDER.index(asset_type)
    except ValueError:
        return 98


def _stats_row_from_parts(
    r: dict,
    *,
    asset_type: Optional[str],
    gates: AnalysisFeatures,
) -> BuildingStatsRow:
    jibun, road, legacy = split_building_addresses(
        addr3=r.get("addr3"),
        addr4=r.get("addr4"),
        addr5=r.get("addr5"),
        lot_number=r.get("lot_number"),
        road_name=r.get("road_name"),
    )
    return BuildingStatsRow(
        building_key=r["building_key"],
        display_name=r["display_name"] or "",
        address=legacy,
        jibun_address=jibun,
        road_address=road,
        building_year=int(r["building_year"]) if r.get("building_year") is not None else None,
        asset_type=r["asset_type"] or asset_type or "",
        count=int(r["count"] or 0),
        mean=float(r["mean"]) if r.get("mean") is not None else None,
        median=float(r["median"]) if r.get("median") is not None else None,
        ci_lower=float(r["ci_lower"]) if r.get("ci_lower") is not None else None,
        ci_upper=float(r["ci_upper"]) if r.get("ci_upper") is not None else None,
        is_reliable=int(r["count"] or 0) >= 15,
        analysis=gates,
    )


def _stats_row_from_live(
    r: dict,
    st: dict,
    *,
    asset_type: Optional[str],
    gates: AnalysisFeatures,
) -> BuildingStatsRow:
    jibun, road, legacy = split_building_addresses(
        addr3=r.get("addr3"),
        addr4=r.get("addr4"),
        addr5=r.get("addr5"),
        lot_number=r.get("lot_number"),
        road_name=r.get("road_name"),
    )
    return BuildingStatsRow(
        building_key=r["building_key"],
        display_name=r["display_name"] or "",
        address=legacy,
        jibun_address=jibun,
        road_address=road,
        building_year=int(r["building_year"]) if r.get("building_year") is not None else None,
        asset_type=r["asset_type"] or asset_type or "",
        count=st["count"],
        mean=st["mean"],
        median=st["median"],
        ci_lower=st["ci_lower"],
        ci_upper=st["ci_upper"],
        is_reliable=st["is_reliable"],
        analysis=gates,
    )


def _mart_has_addr5(conn: Connection) -> bool:
    row = conn.execute(
        text(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'collective_building_stats'
              AND column_name = 'addr5'
            LIMIT 1
            """
        )
    ).scalar()
    return bool(row)


def _rolling_bucket_label(period_start: date, period_end: date) -> str:
    return (
        f"{period_start.year % 100:02d}.{period_start.month:02d}"
        f"~{period_end.year % 100:02d}.{period_end.month:02d}"
    )


def _table_exists(conn: Connection, table: str) -> bool:
    row = conn.execute(
        text("SELECT to_regclass(:t) IS NOT NULL AS ok"),
        {"t": table},
    ).mappings().first()
    return bool(row and row["ok"])


def latest_mart_snapshot(conn: Connection) -> tuple[date | None, int | None]:
    if not _table_exists(conn, "public.collective_building_stats"):
        return None, None
    row = conn.execute(
        text(
            """
            SELECT as_of_month, window_years
            FROM collective_building_stats
            ORDER BY as_of_month DESC, window_years DESC
            LIMIT 1
            """
        )
    ).mappings().first()
    if not row:
        return None, None
    return row["as_of_month"], int(row["window_years"])


def stats_reference_date(as_of_month: date) -> date:
    if as_of_month.month == 12:
        return date(as_of_month.year + 1, 1, 1)
    return date(as_of_month.year, as_of_month.month + 1, 1)


def stats_as_of_label(as_of_month: date | None) -> str | None:
    if as_of_month is None:
        return None
    return f"{as_of_month.year}년 {as_of_month.month}월 말 기준"


def _mart_region_where(
    conn: Connection,
    *,
    asset_type: Optional[str],
    addr1: Optional[str],
    addr2: Optional[str],
    addr3: Optional[str],
    addr3_list: list[str] | None,
    addr4_list: list[str] | None,
    col_prefix: str = "m",
) -> tuple[str, dict]:
    clauses = ["1=1"]
    params: dict[str, Any] = {}
    apply_region_filters(
        clauses,
        params,
        conn=conn,
        table="collective_building_stats",
        addr1=addr1,
        addr2=addr2,
        addr3=addr3,
        addr3_list=addr3_list,
        addr4_list=addr4_list,
        asset_type=asset_type,
        col_prefix=col_prefix,
        valid_sql=None,
    )
    if asset_type:
        clauses.append(f"{col_prefix}.asset_type = :asset_type")
        params["asset_type"] = asset_type
    return " AND ".join(clauses), params


def _fetch_annual_years(conn: Connection, building_keys: list[str]) -> dict[str, list[int]]:
    if not building_keys or not _table_exists(conn, "public.collective_building_annual_stats"):
        return {}
    rows = conn.execute(
        text(
            """
            SELECT building_key, contract_year, count
            FROM collective_building_annual_stats
            WHERE building_key = ANY(:keys)
            """
        ),
        {"keys": building_keys},
    ).mappings().all()
    out: dict[str, list[int]] = {}
    for r in rows:
        bk = r["building_key"]
        cy = int(r["contract_year"])
        cnt = int(r["count"] or 0)
        out.setdefault(bk, [])
        for _ in range(max(cnt, 1)):
            out[bk].append(cy)
    return out


def list_buildings_from_mart(
    conn: Connection,
    *,
    asset_type: Optional[str],
    addr1: Optional[str],
    addr2: Optional[str],
    addr3: Optional[str],
    addr3_list: list[str] | None,
    addr4_list: list[str] | None,
    window_years: int,
    as_of_month: date | None,
    contract_year_from: Optional[int],
    contract_year_to: Optional[int],
) -> tuple[list[BuildingStatsRow], dict[str, Any]] | None:
    if contract_year_from is not None or contract_year_to is not None:
        return None
    if as_of_month is None or not _table_exists(conn, "public.collective_building_stats"):
        return None

    region_sql, params = _mart_region_where(
        conn,
        asset_type=asset_type,
        addr1=addr1,
        addr2=addr2,
        addr3=addr3,
        addr3_list=addr3_list,
        addr4_list=addr4_list,
    )
    params["as_of"] = as_of_month
    params["window_years"] = window_years
    addr5_col = "m.addr5" if _mart_has_addr5(conn) else "NULL::varchar AS addr5"

    rows = conn.execute(
        text(
            f"""
            SELECT m.building_key, m.display_name, m.asset_type,
                   m.addr3, m.addr4, {addr5_col}, m.lot_number, m.road_name, m.building_year,
                   m.count, m.mean, m.median, m.ci_lower, m.ci_upper
            FROM collective_building_stats m
            WHERE m.as_of_month = :as_of
              AND m.window_years = :window_years
              AND {region_sql}
            """
        ),
        params,
    ).mappings().all()

    years_by_key = _fetch_annual_years(conn, [r["building_key"] for r in rows])
    items: list[BuildingStatsRow] = []
    for r in rows:
        bk = r["building_key"]
        years = years_by_key.get(bk, [])
        cnt_recent = count_recent_transactions(
            years,
            contract_year_from=contract_year_from,
            contract_year_to=contract_year_to,
        )
        gates = evaluate_analysis_gates(int(r["count"] or 0), cnt_recent)
        items.append(
            _stats_row_from_parts(
                dict(r),
                asset_type=asset_type,
                gates=AnalysisFeatures(
                    floor_index=gates.floor_index_eligible,
                    regression=gates.regression_eligible,
                    count_total=gates.count_total,
                    count_recent=gates.count_recent,
                    messages=gates.messages,
                ),
            )
        )

    meta = {
        "data_source": "mart",
        "as_of_month": as_of_month.isoformat(),
        "stats_reference_date": stats_reference_date(as_of_month).isoformat(),
        "stats_as_of_label": stats_as_of_label(as_of_month),
        "window_years": window_years,
    }
    ps, pe = period_bounds_for_window(as_of_month, window_years)
    meta["period_start"] = ps.isoformat()
    meta["period_end"] = pe.isoformat()
    return items, meta


def building_yearly_from_mart(
    conn: Connection,
    building_key: str,
) -> tuple[str, list[dict], str] | None:
    """(display_name, points, data_source) — mart 없으면 None."""
    if not _table_exists(conn, "public.collective_building_annual_stats"):
        return None
    rows = conn.execute(
        text(
            """
            SELECT display_name, contract_year, count, mean
            FROM collective_building_annual_stats
            WHERE building_key = :bk
            ORDER BY contract_year
            """
        ),
        {"bk": building_key},
    ).mappings().all()
    if not rows:
        return None
    display_name = rows[0]["display_name"] or ""
    points = [
        {
            "year": int(r["contract_year"]),
            "count": int(r["count"] or 0),
            "mean": round(float(r["mean"]), 1) if r["mean"] is not None else None,
        }
        for r in rows
    ]
    return display_name, points, "mart"


def list_buildings_live(
    conn: Connection,
    where: str,
    params: dict,
    *,
    asset_type: Optional[str],
) -> list[BuildingStatsRow]:
    rows = conn.execute(
        text(
            f"""
            SELECT building_key,
                   MAX(display_name) AS display_name,
                   MAX(asset_type) AS asset_type,
                   MAX(addr3) AS addr3,
                   MAX(addr4) AS addr4,
                   MAX(addr5) AS addr5,
                   MAX(lot_number) AS lot_number,
                   MAX(road_name) AS road_name,
                   MAX(building_year) AS building_year,
                   array_agg(unit_price ORDER BY unit_price) AS prices,
                   array_agg(contract_year) AS years
            FROM collective_transactions
            WHERE {where}
            GROUP BY building_key, asset_type
            """
        ),
        params,
    ).mappings().all()

    items: list[BuildingStatsRow] = []
    for r in rows:
        prices = [float(x) for x in (r["prices"] or []) if x is not None]
        years = [int(y) for y in (r["years"] or []) if y is not None]
        st = compute_stats(prices)
        cnt_recent = count_recent_transactions(
            years,
            contract_year_from=params.get("cy_from"),
            contract_year_to=params.get("cy_to"),
        )
        gates = evaluate_analysis_gates(st["count"], cnt_recent)
        items.append(
            _stats_row_from_live(
                dict(r),
                st,
                asset_type=asset_type,
                gates=AnalysisFeatures(
                    floor_index=gates.floor_index_eligible,
                    regression=gates.regression_eligible,
                    count_total=gates.count_total,
                    count_recent=gates.count_recent,
                    messages=gates.messages,
                ),
            )
        )
    return items


def building_rolling_from_mart(
    conn: Connection,
    building_key: str,
    *,
    window_years: int,
    as_of_month: date | None,
) -> tuple[str, list[dict], str] | None:
    if as_of_month is None or not _table_exists(conn, "public.collective_building_rolling_stats"):
        return None
    rows = conn.execute(
        text(
            """
            SELECT display_name, bucket_index, period_start, period_end,
                   count, mean
            FROM collective_building_rolling_stats
            WHERE building_key = :bk
              AND as_of_month = :as_of
              AND window_years = :wy
            ORDER BY bucket_index
            """
        ),
        {"bk": building_key, "as_of": as_of_month, "wy": window_years},
    ).mappings().all()
    if not rows:
        return None
    display_name = rows[0]["display_name"] or ""
    points = [
        {
            "bucket_index": int(r["bucket_index"]),
            "period_start": r["period_start"].isoformat() if r["period_start"] else "",
            "period_end": r["period_end"].isoformat() if r["period_end"] else "",
            "label": _rolling_bucket_label(r["period_start"], r["period_end"]),
            "count": int(r["count"] or 0),
            "mean": round(float(r["mean"]), 1) if r["mean"] is not None else None,
        }
        for r in rows
    ]
    return display_name, points, "mart"
