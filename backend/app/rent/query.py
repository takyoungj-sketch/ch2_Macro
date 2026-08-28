"""rent_building_stats 조회. 원장 핫패스 없음 — 마트만."""

from __future__ import annotations

from datetime import date
from typing import Any, Optional

from sqlalchemy import bindparam, text
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session

from app.collective.address import format_jibun_address
from app.flat_sido_region import (
    FLAT_SIDO_ADDR2_TOKEN,
    apply_addr2_scope,
    flat_sido_addr2_sql,
    is_flat_sido_addr2,
)
from app.rent.conversion_query import fetch_building_converted, get_region_rates
from app.rent.schemas import (
    LeaseMetric,
    MixedLeaseMetric,
    RentBuildingRow,
    RentRollingPoint,
)

ASSET_TYPES = ("apartment", "rowhouse", "officetel", "detached")
# 매매 칩과 동일: 괄호 = 거래 건수 (건물 수·동 수가 아님)
_TX_N = "COALESCE(SUM(jeonse_n + mixed_n + monthly_n), 0)::int"
SORT_KEYS = {
    "jeonse_median": "jeonse_median DESC NULLS LAST, jeonse_n DESC",
    "jeonse_equiv_median": "jeonse_median DESC NULLS LAST, jeonse_n DESC",
    "mixed_n": "mixed_n DESC, mixed_monthly_median DESC NULLS LAST",
    "monthly_n": "monthly_n DESC, monthly_median DESC NULLS LAST",
    "name": "display_name ASC",
    "total_n": "(jeonse_n + mixed_n + monthly_n) DESC",
}


def _table_exists(conn: Connection, table: str) -> bool:
    row = conn.execute(
        text("SELECT to_regclass(:t) IS NOT NULL AS ok"),
        {"t": table},
    ).mappings().first()
    return bool(row and row["ok"])


def latest_as_of(conn: Connection) -> date | None:
    if not _table_exists(conn, "public.rent_building_stats"):
        return None
    return conn.execute(
        text("SELECT max(as_of_month) FROM rent_building_stats")
    ).scalar()


def _metric(n, mean, median, lo, hi) -> LeaseMetric:
    return LeaseMetric(
        n=int(n or 0),
        mean=float(mean) if mean is not None else None,
        median=float(median) if median is not None else None,
        ci_lower=float(lo) if lo is not None else None,
        ci_upper=float(hi) if hi is not None else None,
    )


def _jibun(r: dict) -> str:
    """매매 목록과 동일: 읍·면·동 + 리(addr5) + 번지."""
    return format_jibun_address(
        addr3=r.get("addr3"),
        addr4=r.get("addr4"),
        addr5=r.get("addr5"),
        lot_number=r.get("lot_number"),
    )


def detect_rent_structure(
    conn: Connection,
    as_of: date,
    window_years: int,
    addr1: str,
    addr2: str,
) -> dict[str, Any]:
    """청주·수원 등 addr3=구, addr4=동."""
    clauses = ["as_of_month = :as_of", "window_years = :w", "addr1 = :a1"]
    params: dict[str, Any] = {"as_of": as_of, "w": window_years, "a1": addr1.strip()}
    if is_flat_sido_addr2(addr2):
        clauses.append(flat_sido_addr2_sql())
    else:
        clauses.append("addr2 = :a2")
        params["a2"] = addr2.strip()
    row = conn.execute(
        text(
            f"""
            SELECT COUNT(*)::int AS total,
                   COUNT(*) FILTER (
                       WHERE addr3 IS NOT NULL AND btrim(addr3::text) <> '' AND addr3 LIKE '%구'
                   )::int AS gu_like,
                   COUNT(*) FILTER (
                       WHERE addr4 IS NOT NULL AND btrim(addr4::text) <> ''
                   )::int AS has_a4
            FROM rent_building_stats
            WHERE {" AND ".join(clauses)}
            """
        ),
        params,
    ).one()
    total = int(row.total or 0)
    if total == 0:
        return {"has_intermediate": False, "intermediate_label": None, "leaf_level": "addr3"}
    if int(row.gu_like or 0) / total >= 0.85 and int(row.has_a4 or 0) / total >= 0.25:
        return {"has_intermediate": True, "intermediate_label": "구", "leaf_level": "addr4"}
    return {"has_intermediate": False, "intermediate_label": None, "leaf_level": "addr3"}


def list_addr4(
    conn: Connection,
    as_of: date,
    window_years: int,
    addr1: str,
    addr2: str,
    gu_list: Optional[list[str]] = None,
    asset_types: Optional[list[str]] = None,
) -> list[tuple[str, int, str]]:
    """구-동 구조의 읍면동. (name, count, parent_gu)."""
    clauses = [
        "as_of_month = :as_of",
        "window_years = :w",
        "addr1 = :a1",
        "addr4 IS NOT NULL AND btrim(addr4::text) <> ''",
    ]
    params: dict[str, Any] = {"as_of": as_of, "w": window_years, "a1": addr1}
    if is_flat_sido_addr2(addr2):
        clauses.append(flat_sido_addr2_sql())
    else:
        clauses.append("addr2 = :a2")
        params["a2"] = addr2
    gus = [g.strip() for g in (gu_list or []) if g and str(g).strip()]
    expand = False
    if gus:
        clauses.append("addr3 IN :gus")
        params["gus"] = gus
        expand = True
    assets = [a for a in (asset_types or []) if a in ASSET_TYPES]
    if len(assets) == 1:
        clauses.append("asset_type = :asset_type")
        params["asset_type"] = assets[0]
    elif len(assets) > 1:
        clauses.append("asset_type IN :asset_types")
        params["asset_types"] = assets
        expand = True
    stmt = text(
        f"""
        SELECT addr4 AS name, addr3 AS parent, {_TX_N} AS n
        FROM rent_building_stats
        WHERE {" AND ".join(clauses)}
        GROUP BY addr4, addr3
        ORDER BY addr3, 3 DESC, addr4
        """
    )
    binds = []
    if gus:
        binds.append(bindparam("gus", expanding=True))
    if len(assets) > 1:
        binds.append(bindparam("asset_types", expanding=True))
    if binds:
        stmt = stmt.bindparams(*binds)
    return [(str(r[0]), int(r[2]), str(r[1] or "")) for r in conn.execute(stmt, params)]


def row_from_mart(r: dict) -> RentBuildingRow:
    return RentBuildingRow(
        building_key=str(r["building_key"]).strip(),
        asset_type=r["asset_type"] or "",
        display_name=r["display_name"] or "",
        jibun_address=_jibun(r),
        road_address=(r.get("road_name") or "").strip(),
        building_year=int(r["building_year"]) if r.get("building_year") is not None else None,
        addr3=(r.get("addr3") or "").strip(),
        jeonse=_metric(
            r.get("jeonse_n"),
            r.get("jeonse_mean"),
            r.get("jeonse_median"),
            r.get("jeonse_ci_lower"),
            r.get("jeonse_ci_upper"),
        ),
        mixed=MixedLeaseMetric(
            n=int(r.get("mixed_n") or 0),
            deposit=_metric(
                r.get("mixed_n"),
                r.get("mixed_deposit_mean"),
                r.get("mixed_deposit_median"),
                r.get("mixed_deposit_ci_lower"),
                r.get("mixed_deposit_ci_upper"),
            ),
            monthly=_metric(
                r.get("mixed_n"),
                r.get("mixed_monthly_mean"),
                r.get("mixed_monthly_median"),
                r.get("mixed_monthly_ci_lower"),
                r.get("mixed_monthly_ci_upper"),
            ),
        ),
        monthly=_metric(
            r.get("monthly_n"),
            r.get("monthly_mean"),
            r.get("monthly_median"),
            r.get("monthly_ci_lower"),
            r.get("monthly_ci_upper"),
        ),
    )


def _bucket_label(start: date, end: date) -> str:
    return f"{start.year % 100:02d}.{start.month:02d}~{end.year % 100:02d}.{end.month:02d}"


def list_addr1(conn: Connection, as_of: date, window_years: int) -> list[str]:
    rows = conn.execute(
        text(
            """
            SELECT DISTINCT addr1
            FROM rent_building_stats
            WHERE as_of_month = :as_of AND window_years = :w
              AND addr1 IS NOT NULL AND btrim(addr1) <> ''
            ORDER BY 1
            """
        ),
        {"as_of": as_of, "w": window_years},
    ).fetchall()
    return [str(r[0]) for r in rows]


def list_addr2(conn: Connection, as_of: date, window_years: int, addr1: str) -> list[tuple[str, int]]:
    rows = conn.execute(
        text(
            f"""
            SELECT addr2, {_TX_N} AS n
            FROM rent_building_stats
            WHERE as_of_month = :as_of AND window_years = :w AND addr1 = :a1
              AND addr2 IS NOT NULL AND btrim(addr2) <> ''
            GROUP BY 1
            ORDER BY 1
            """
        ),
        {"as_of": as_of, "w": window_years, "a1": addr1},
    ).fetchall()
    if rows:
        return [(str(r[0]), int(r[1])) for r in rows]
    n = conn.execute(
        text(
            f"""
            SELECT {_TX_N}
            FROM rent_building_stats
            WHERE as_of_month = :as_of AND window_years = :w AND addr1 = :a1
              AND {flat_sido_addr2_sql()}
              AND addr3 IS NOT NULL AND btrim(addr3::text) <> ''
            """
        ),
        {"as_of": as_of, "w": window_years, "a1": addr1},
    ).scalar()
    if int(n or 0) > 0:
        return [(FLAT_SIDO_ADDR2_TOKEN, int(n))]
    return []


def list_addr3(
    conn: Connection,
    as_of: date,
    window_years: int,
    addr1: str,
    addr2: str,
    asset_types: Optional[list[str]] = None,
) -> list[tuple[str, int]]:
    clauses = [
        "as_of_month = :as_of",
        "window_years = :w",
        "addr1 = :a1",
        "addr3 IS NOT NULL AND btrim(addr3::text) <> ''",
    ]
    params: dict[str, Any] = {"as_of": as_of, "w": window_years, "a1": addr1}
    if is_flat_sido_addr2(addr2):
        clauses.append(flat_sido_addr2_sql())
    else:
        clauses.append("addr2 = :a2")
        params["a2"] = addr2
    assets = [a for a in (asset_types or []) if a in ASSET_TYPES]
    expand = False
    if len(assets) == 1:
        clauses.append("asset_type = :asset_type")
        params["asset_type"] = assets[0]
    elif len(assets) > 1:
        clauses.append("asset_type IN :asset_types")
        params["asset_types"] = assets
        expand = True
    stmt = text(
        f"""
        SELECT addr3, {_TX_N} AS n
        FROM rent_building_stats
        WHERE {" AND ".join(clauses)}
        GROUP BY 1
        ORDER BY 1
        """
    )
    if expand:
        stmt = stmt.bindparams(bindparam("asset_types", expanding=True))
    rows = conn.execute(stmt, params).fetchall()
    return [(str(r[0]), int(r[1])) for r in rows]


def list_buildings(
    db: Session,
    *,
    as_of: date,
    window_years: int,
    addr1: str,
    addr2: str,
    addr3: Optional[str],
    asset_types: list[str],
    sort: str,
    addr3_list: Optional[list[str]] = None,
    addr4_list: Optional[list[str]] = None,
) -> tuple[list[RentBuildingRow], Optional[date], Optional[date], list]:
    order = SORT_KEYS.get(sort, SORT_KEYS["jeonse_median"])
    clauses = [
        "as_of_month = :as_of",
        "window_years = :w",
    ]
    params: dict[str, Any] = {
        "as_of": as_of,
        "w": window_years,
    }
    apply_addr2_scope(clauses, params, addr1=addr1, addr2=addr2)
    leaves = [x.strip() for x in (addr3_list or []) if x and str(x).strip()]
    dongs = [x.strip() for x in (addr4_list or []) if x and str(x).strip()]
    if leaves:
        clauses.append("addr3 IN :addr3s")
        params["addr3s"] = leaves
    elif addr3:
        clauses.append("addr3 = :addr3")
        params["addr3"] = addr3
    if dongs:
        clauses.append("addr4 IN :addr4s")
        params["addr4s"] = dongs
    assets = [a for a in asset_types if a in ASSET_TYPES]
    if not assets:
        assets = ["apartment"]
    if len(assets) == 1:
        clauses.append("asset_type = :asset_type")
        params["asset_type"] = assets[0]
        expand = False
    else:
        clauses.append("asset_type IN :asset_types")
        params["asset_types"] = assets
        expand = True

    sql = f"""
        SELECT *
        FROM rent_building_stats
        WHERE {" AND ".join(clauses)}
        ORDER BY (jeonse_n > 0) DESC, {order}, display_name
    """
    stmt = text(sql)
    binds = []
    if expand:
        binds.append(bindparam("asset_types", expanding=True))
    if leaves:
        binds.append(bindparam("addr3s", expanding=True))
    if dongs:
        binds.append(bindparam("addr4s", expanding=True))
    if binds:
        stmt = stmt.bindparams(*binds)
    rows = db.execute(stmt, params).mappings().all()
    conn = db.connection()
    period = rows[0] if rows else None
    ps = period["period_start"] if period else None
    pe = period["period_end"] if period else None
    rate_addr3 = leaves[0] if len(leaves) == 1 else (None if leaves else addr3)
    rates = get_region_rates(
        conn,
        as_of=as_of,
        window_years=window_years,
        addr1=addr1,
        addr2=addr2,
        asset_types=assets,
        addr3=rate_addr3,
    )
    converted: dict[tuple[str, str], tuple[LeaseMetric, LeaseMetric]] = {}
    if ps and pe and any(r.gate_passed and r.r_selected for r in rates.values()):
        converted = fetch_building_converted(
            conn,
            as_of=as_of,
            window_years=window_years,
            addr1=addr1,
            addr2=addr2,
            addr3=rate_addr3,
            asset_types=assets,
            period_start=ps,
            period_end=pe,
            rates=rates,
        )
    items: list[RentBuildingRow] = []
    for r in rows:
        row = row_from_mart(dict(r))
        key = (row.building_key, row.asset_type)
        if key in converted:
            j_eq, m_eq = converted[key]
            row = row.model_copy(update={"jeonse_equiv": j_eq, "monthly_equiv": m_eq})
        items.append(row)
    return items, ps, pe, list(rates.values())


def building_rolling(
    db: Session,
    *,
    building_key: str,
    asset_type: str,
    as_of: date,
    window_years: int,
) -> list[RentRollingPoint]:
    rows = db.execute(
        text(
            """
            SELECT *
            FROM rent_building_rolling_stats
            WHERE building_key = :k
              AND asset_type = :a
              AND as_of_month = :as_of
              AND window_years = :w
            ORDER BY bucket_index
            """
        ),
        {"k": building_key, "a": asset_type, "as_of": as_of, "w": window_years},
    ).mappings().all()
    out: list[RentRollingPoint] = []
    for r in rows:
        d = dict(r)
        ps, pe = d["period_start"], d["period_end"]
        row = row_from_mart(d)
        out.append(
            RentRollingPoint(
                bucket_index=int(d["bucket_index"]),
                period_start=ps,
                period_end=pe,
                label=_bucket_label(ps, pe),
                jeonse=row.jeonse,
                mixed=row.mixed,
                monthly=row.monthly,
            )
        )
    return out
