"""collective_cluster_stats mart lookup + live fallback."""

from __future__ import annotations

from datetime import date
from typing import Optional

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.collective.filters import apply_region_filters
from app.collective_commercial.schemas import CommercialClusterRow


def _table_exists(conn: Connection, table: str) -> bool:
    row = conn.execute(
        text("SELECT to_regclass(:t) IS NOT NULL AS ok"),
        {"t": table},
    ).mappings().first()
    return bool(row and row["ok"])


def latest_mart_snapshot(conn: Connection) -> tuple[date | None, int | None]:
    if not _table_exists(conn, "public.collective_cluster_stats"):
        return None, None
    row = conn.execute(
        text(
            """
            SELECT as_of_month, window_years
            FROM collective_cluster_stats
            ORDER BY as_of_month DESC, window_years DESC
            LIMIT 1
            """
        )
    ).mappings().first()
    if not row:
        return None, None
    return row["as_of_month"], int(row["window_years"])


def _rolling_bucket_label(period_start: date, period_end: date) -> str:
    return (
        f"{period_start.year % 100:02d}.{period_start.month:02d}"
        f"~{period_end.year % 100:02d}.{period_end.month:02d}"
    )


def list_clusters_mart(
    conn: Connection,
    *,
    asset_type: Optional[str],
    addr1: Optional[str],
    addr2: str,
    addr3_list: list[str] | None,
    addr4_list: list[str] | None,
    window_years: int,
    as_of_month: date | None = None,
) -> list[CommercialClusterRow]:
    if as_of_month is None:
        as_of_month, default_w = latest_mart_snapshot(conn)
        if as_of_month is None:
            return []
        if window_years != default_w:
            pass
    clauses = [
        "s.as_of_month = :as_of",
        "s.window_years = :window_years",
        "s.addr2 = :addr2",
    ]
    params: dict = {"as_of": as_of_month, "window_years": window_years, "addr2": addr2}
    if asset_type:
        clauses.append("s.asset_type = :asset_type")
        params["asset_type"] = asset_type
    if addr1:
        clauses.append("s.addr1 = :addr1")
        params["addr1"] = addr1
    apply_region_filters(clauses, params, addr3_list=addr3_list, addr4_list=addr4_list, col_prefix="s")
    rows = conn.execute(
        text(
            f"""
            SELECT s.cluster_key, s.display_label, s.asset_type, s.road_name,
                   s.addr3, s.addr4, s.zone_type, s.building_use, s.building_year,
                   s.area_bucket_label, s.confidence_tier,
                   s.count, s.mean, s.median, s.ci_lower, s.ci_upper
            FROM collective_cluster_stats s
            WHERE {" AND ".join(clauses)}
            """
        ),
        params,
    ).mappings().all()
    items: list[CommercialClusterRow] = []
    for r in rows:
        cnt = int(r["count"] or 0)
        items.append(
            CommercialClusterRow(
                cluster_key=r["cluster_key"],
                display_label=r["display_label"] or "",
                asset_type=r["asset_type"] or "",
                road_name=r["road_name"],
                addr3=r["addr3"],
                addr4=r["addr4"],
                resolution_mode="road",
                zone_type=r["zone_type"],
                building_use=r["building_use"],
                building_year=int(r["building_year"]) if r["building_year"] is not None else None,
                area_bucket_label=r["area_bucket_label"],
                confidence_tier=r["confidence_tier"],
                count=cnt,
                mean=float(r["mean"]) if r["mean"] is not None else None,
                median=float(r["median"]) if r["median"] is not None else None,
                ci_lower=float(r["ci_lower"]) if r["ci_lower"] is not None else None,
                ci_upper=float(r["ci_upper"]) if r["ci_upper"] is not None else None,
                is_reliable=cnt >= 15,
            )
        )
    return items


def fetch_cluster_rolling(
    conn: Connection,
    cluster_key: str,
    *,
    window_years: int = 5,
    as_of_month: date | None = None,
) -> tuple[list[dict], date | None, str]:
    if not _table_exists(conn, "public.collective_cluster_rolling_stats"):
        return [], None, "live"
    if as_of_month is None:
        as_of_month, _ = latest_mart_snapshot(conn)
    if as_of_month is None:
        return [], None, "live"
    rows = conn.execute(
        text(
            """
            SELECT bucket_index, period_start, period_end, count, mean, median
            FROM collective_cluster_rolling_stats
            WHERE cluster_key = :ck AND as_of_month = :as_of AND window_years = :w
              AND bucket_index <= :w
            ORDER BY bucket_index
            """
        ),
        {"ck": cluster_key, "as_of": as_of_month, "w": window_years},
    ).mappings().all()
    if not rows:
        return [], as_of_month, "live"
    points = [
        {
            "bucket_index": int(r["bucket_index"]),
            "period_start": r["period_start"],
            "period_end": r["period_end"],
            "label": _rolling_bucket_label(r["period_start"], r["period_end"]),
            "count": int(r["count"]),
            "mean": float(r["mean"]) if r["mean"] is not None else None,
        }
        for r in rows
    ]
    return points, as_of_month, "mart"


def cluster_yearly_from_mart(
    conn: Connection,
    cluster_key: str,
) -> tuple[str, list[dict], str] | None:
    """(display_label, points, data_source) — mart 없으면 None."""
    if not _table_exists(conn, "public.collective_cluster_annual_stats"):
        return None
    rows = conn.execute(
        text(
            """
            SELECT display_label, contract_year, count, mean
            FROM collective_cluster_annual_stats
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
        }
        for r in rows
    ]
    return display_label, points, "mart"
