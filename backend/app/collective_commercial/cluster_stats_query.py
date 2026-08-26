"""collective_commercial_cluster_stats mart 조회 + live fallback."""

from __future__ import annotations

from datetime import date
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.collective.asset_scope import COMMERCIAL_ASSET_TYPES, apply_asset_type_filter
from app.collective.building_stats_query import (
    _rolling_bucket_label,
    _table_exists,
    stats_as_of_label,
    stats_reference_date,
)
from app.collective.filters import apply_region_filters
from app.collective_commercial.schemas import CommercialClusterRow
from app.stats_utils import compute_stats
from app.v2_stats_windows import (
    default_as_of_month_for_service,
    iter_rolling_year_buckets_old_first,
    period_bounds_for_window,
)


def latest_mart_snapshot(conn: Connection) -> tuple[date | None, int | None]:
    if not _table_exists(conn, "public.collective_commercial_cluster_stats"):
        return None, None
    row = conn.execute(
        text(
            """
            SELECT as_of_month, window_years
            FROM collective_commercial_cluster_stats
            ORDER BY as_of_month DESC, window_years DESC
            LIMIT 1
            """
        )
    ).mappings().first()
    if not row:
        return None, None
    return row["as_of_month"], int(row["window_years"])


def _mart_region_where(
    conn: Connection,
    *,
    asset_type: Optional[str],
    addr1: Optional[str],
    addr2: Optional[str],
    addr3_list: list[str] | None,
    addr4_list: list[str] | None,
    col_prefix: str = "m",
) -> tuple[str, dict]:
    clauses = ["1=1"]
    params: dict[str, Any] = {}
    # collective_commercial_cluster_stats 는 사전집계 마트 테이블이므로
    # beopjungri_code 컬럼이 없다 → conn=None 으로 addr 텍스트 필터만 사용.
    apply_region_filters(
        clauses,
        params,
        conn=None,
        table="collective_commercial_cluster_stats",
        addr1=addr1,
        addr2=addr2,
        addr3=addr3_list[0] if addr3_list and len(addr3_list) == 1 else None,
        addr3_list=addr3_list,
        addr4_list=addr4_list,
        asset_type=None,
        col_prefix=col_prefix,
        valid_sql=None,
    )
    apply_asset_type_filter(
        clauses,
        params,
        asset_type,
        allowed=COMMERCIAL_ASSET_TYPES,
        col_prefix=col_prefix,
    )
    return " AND ".join(clauses), params


def _cluster_row_from_parts(r: dict) -> CommercialClusterRow:
    return CommercialClusterRow(
        cluster_key=r["cluster_key"],
        display_label=r.get("display_label") or "",
        asset_type=r.get("asset_type") or "",
        road_name=r.get("road_name"),
        addr3=r.get("addr3"),
        addr4=r.get("addr4"),
        resolution_mode=r.get("resolution_mode"),
        zone_type=r.get("zone_type"),
        building_use=r.get("building_use"),
        building_year=int(r["building_year"]) if r.get("building_year") is not None else None,
        area_bucket_label=r.get("area_bucket_label"),
        confidence_tier=r.get("confidence_tier"),
        count=int(r["count"] or 0),
        mean=float(r["mean"]) if r.get("mean") is not None else None,
        median=float(r["median"]) if r.get("median") is not None else None,
        ci_lower=float(r["ci_lower"]) if r.get("ci_lower") is not None else None,
        ci_upper=float(r["ci_upper"]) if r.get("ci_upper") is not None else None,
        is_reliable=int(r["count"] or 0) >= 15,
    )


def list_clusters_from_mart(
    conn: Connection,
    *,
    asset_type: Optional[str],
    addr1: Optional[str],
    addr2: Optional[str],
    addr3_list: list[str] | None,
    addr4_list: list[str] | None,
    window_years: int,
    as_of_month: date | None,
    contract_year_from: Optional[int],
    contract_year_to: Optional[int],
    region_codes: list[str] | None = None,
    region_addrs: list[str] | None = None,
) -> tuple[list[CommercialClusterRow], dict[str, Any]] | None:
    if contract_year_from is not None or contract_year_to is not None:
        return None
    # cluster mart 는 행정코드·addr5 없음 — 교차 시군구는 live
    if region_codes or region_addrs:
        return None
    if as_of_month is None or not _table_exists(conn, "public.collective_commercial_cluster_stats"):
        return None

    region_sql, params = _mart_region_where(
        conn,
        asset_type=asset_type,
        addr1=addr1,
        addr2=addr2,
        addr3_list=addr3_list,
        addr4_list=addr4_list,
    )
    params["as_of"] = as_of_month
    params["window_years"] = window_years

    rows = conn.execute(
        text(
            f"""
            SELECT m.cluster_key, m.display_label, m.asset_type,
                   m.road_name, m.addr3, m.addr4,
                   m.resolution_mode, m.zone_type, m.building_use,
                   m.building_year, m.area_bucket_label, m.confidence_tier,
                   m.count, m.mean, m.median, m.ci_lower, m.ci_upper
            FROM collective_commercial_cluster_stats m
            WHERE m.as_of_month = :as_of
              AND m.window_years = :window_years
              AND {region_sql}
            """
        ),
        params,
    ).mappings().all()

    items = [_cluster_row_from_parts(dict(r)) for r in rows]
    meta: dict[str, Any] = {
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


def list_clusters_live(
    conn: Connection,
    where: str,
    params: dict,
) -> list[CommercialClusterRow]:
    rows = conn.execute(
        text(
            f"""
            SELECT t.cluster_key,
                   MAX(c.display_label) AS display_label,
                   MAX(t.asset_type) AS asset_type,
                   MAX(c.road_name) AS road_name,
                   MAX(t.addr3) AS addr3,
                   MAX(t.addr4) AS addr4,
                   MAX(c.resolution_mode) AS resolution_mode,
                   MAX(t.zone_type) AS zone_type,
                   MAX(t.building_use) AS building_use,
                   MAX(t.building_year) AS building_year,
                   MAX(t.area_bucket_label) AS area_bucket_label,
                   MAX(c.confidence_tier) AS confidence_tier,
                   array_agg(t.unit_price ORDER BY t.unit_price) AS prices
            FROM collective_commercial_transactions t
            JOIN commercial_clusters c ON c.id = t.cluster_id
            WHERE {where}
            GROUP BY t.cluster_key
            """
        ),
        params,
    ).mappings().all()

    items: list[CommercialClusterRow] = []
    for r in rows:
        prices = [float(x) for x in (r["prices"] or []) if x is not None]
        st = compute_stats(prices)
        items.append(
            _cluster_row_from_parts(
                {
                    **dict(r),
                    "count": st["count"],
                    "mean": st["mean"],
                    "median": st["median"],
                    "ci_lower": st["ci_lower"],
                    "ci_upper": st["ci_upper"],
                }
            )
        )
    return items


def cluster_yearly_from_mart(
    conn: Connection,
    cluster_key: str,
) -> tuple[str, list[dict], str] | None:
    if not _table_exists(conn, "public.collective_commercial_cluster_annual_stats"):
        return None
    rows = conn.execute(
        text(
            """
            SELECT display_label, contract_year, count, mean, median
            FROM collective_commercial_cluster_annual_stats
            WHERE cluster_key = :ck
            ORDER BY contract_year
            """
        ),
        {"ck": cluster_key},
    ).mappings().all()
    if not rows:
        return None
    display_label = rows[0]["display_label"] or ""
    points = [
        {
            "year": int(r["contract_year"]),
            "count": int(r["count"] or 0),
            "mean": round(float(r["mean"]), 1) if r["mean"] is not None else None,
            "median": round(float(r["median"]), 1) if r.get("median") is not None else None,
        }
        for r in rows
    ]
    return display_label, points, "mart"


def cluster_yearly_live(
    conn: Connection,
    cluster_key: str,
) -> tuple[str, list[dict], str] | None:
    rows = conn.execute(
        text(
            """
            SELECT MAX(c.display_label) AS display_label,
                   t.contract_year AS year,
                   COUNT(*)::int AS count,
                   AVG(t.unit_price)::float AS mean,
                   PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY t.unit_price)::float AS median
            FROM collective_commercial_transactions t
            LEFT JOIN commercial_clusters c ON c.id = t.cluster_id
            WHERE t.cluster_key = :ck
              AND t.is_valid = true
              AND t.unit_price IS NOT NULL
              AND t.unit_price > 0
              AND t.contract_year IS NOT NULL
            GROUP BY t.contract_year
            ORDER BY t.contract_year
            """
        ),
        {"ck": cluster_key},
    ).mappings().all()
    if not rows:
        return None
    display_label = rows[0]["display_label"] or ""
    points = [
        {
            "year": int(r["year"]),
            "count": int(r["count"] or 0),
            "mean": round(float(r["mean"]), 1) if r["mean"] is not None else None,
            "median": round(float(r["median"]), 1) if r.get("median") is not None else None,
        }
        for r in rows
    ]
    return display_label, points, "live"


def cluster_yearly_resolved(
    conn: Connection,
    cluster_key: str,
) -> tuple[str, list[dict], str] | None:
    mart = cluster_yearly_from_mart(conn, cluster_key)
    live = cluster_yearly_live(conn, cluster_key)
    if mart is None and live is None:
        return None
    if mart is None:
        return live
    if live is None:
        return mart

    display_label = mart[0] or live[0]
    by_year: dict[int, dict] = {int(p["year"]): p for p in mart[1]}
    for p in live[1]:
        yr = int(p["year"])
        if yr not in by_year:
            by_year[yr] = p
    points = [by_year[y] for y in sorted(by_year)]
    mart_years = {int(p["year"]) for p in mart[1]}
    source: str = "mart" if all(int(p["year"]) in mart_years for p in points) else "live"
    return display_label, points, source


def cluster_rolling_from_mart(
    conn: Connection,
    cluster_key: str,
    *,
    window_years: int,
    as_of_month: date | None,
) -> tuple[str, list[dict], str] | None:
    if as_of_month is None or not _table_exists(conn, "public.collective_commercial_cluster_rolling_stats"):
        return None
    rows = conn.execute(
        text(
            """
            SELECT display_label, bucket_index, period_start, period_end,
                   count, mean
            FROM collective_commercial_cluster_rolling_stats
            WHERE cluster_key = :ck
              AND as_of_month = :as_of
              AND window_years = :wy
            ORDER BY bucket_index
            """
        ),
        {"ck": cluster_key, "as_of": as_of_month, "wy": window_years},
    ).mappings().all()
    if not rows:
        return None
    display_label = rows[0]["display_label"] or ""
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
    return display_label, points, "mart"


def cluster_rolling_live(
    conn: Connection,
    cluster_key: str,
    *,
    window_years: int,
    as_of_month: date | None = None,
) -> tuple[str, list[dict], str] | None:
    as_of = as_of_month
    if as_of is None:
        as_of, _ = latest_mart_snapshot(conn)
    if as_of is None:
        as_of = default_as_of_month_for_service()

    _, period_end = period_bounds_for_window(as_of, window_years)
    buckets = iter_rolling_year_buckets_old_first(period_end, window_years)

    meta = conn.execute(
        text(
            """
            SELECT COALESCE(MAX(c.display_label), MAX(t.road_name), :ck) AS display_label
            FROM collective_commercial_transactions t
            LEFT JOIN commercial_clusters c ON c.id = t.cluster_id
            WHERE t.cluster_key = :ck AND t.is_valid = true
            """
        ),
        {"ck": cluster_key},
    ).mappings().first()
    if not meta:
        return None
    display_label = meta["display_label"] or ""

    points: list[dict] = []
    for ps, pe, bidx in buckets:
        row = conn.execute(
            text(
                """
                SELECT array_agg(unit_price ORDER BY unit_price) AS prices
                FROM collective_commercial_transactions
                WHERE cluster_key = :ck
                  AND is_valid = true
                  AND unit_price IS NOT NULL
                  AND unit_price > 0
                  AND contract_date IS NOT NULL
                  AND contract_date >= :ps
                  AND contract_date <= :pe
                """
            ),
            {"ck": cluster_key, "ps": ps, "pe": pe},
        ).mappings().first()
        prices_raw = (row or {}).get("prices") or []
        prices = [float(x) for x in prices_raw if x is not None]
        if not prices:
            continue
        st = compute_stats(prices)
        if st["count"] <= 0:
            continue
        points.append(
            {
                "bucket_index": bidx,
                "period_start": ps.isoformat(),
                "period_end": pe.isoformat(),
                "label": _rolling_bucket_label(ps, pe),
                "count": st["count"],
                "mean": round(float(st["mean"]), 1) if st["mean"] is not None else None,
            }
        )
    if not points:
        return None
    return display_label, points, "live"
