"""전환율 조회·건물 환산 (분석층)."""

from __future__ import annotations

from datetime import date
from typing import Any, Optional

from sqlalchemy import bindparam, text
from sqlalchemy.engine import Connection

from app.flat_sido_region import apply_addr2_scope, is_flat_sido_addr2
from app.rent.schemas import LeaseMetric, RentConversionCompareRow, RentConversionRate
from app.rent.sql_fragments import building_key_sql

ASSET_TYPES = ("apartment", "rowhouse", "officetel", "detached")


def _table_exists(conn: Connection, table: str) -> bool:
    row = conn.execute(
        text("SELECT to_regclass(:t) IS NOT NULL AS ok"),
        {"t": table},
    ).mappings().first()
    return bool(row and row["ok"])


def _has_addr3(conn: Connection) -> bool:
    row = conn.execute(
        text(
            """
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'rent_conversion_rates'
              AND column_name = 'addr3'
            """
        )
    ).first()
    return bool(row)


def _rate_from_row(d: dict, *, scope: str, fallback: bool = False) -> RentConversionRate:
    return RentConversionRate(
        asset_type=d["asset_type"],
        r_selected=float(d["r_selected"]) if d.get("r_selected") is not None else None,
        method_selected=d.get("method_selected") or "mean_simple",
        gate_passed=bool(d.get("gate_passed")),
        n_buildings=int(d.get("n_buildings") or 0),
        n_jeonse=int(d.get("n_jeonse") or 0),
        n_mixed=int(d.get("n_mixed") or 0),
        r_mean_simple=_f(d.get("r_mean_simple")),
        r_mean_weighted=_f(d.get("r_mean_weighted")),
        r_ols_origin=_f(d.get("r_ols_origin")),
        r_ols_weighted=_f(d.get("r_ols_weighted")),
        scope=scope,
        addr3=(d.get("addr3") or "") if scope == "dong" else "",
        fallback=fallback,
    )


def _fetch_rate_rows(
    conn: Connection,
    *,
    as_of: date,
    window_years: int,
    addr1: str,
    addr2: str,
    assets: list[str],
    addr3: str,
) -> list[dict]:
    has3 = _has_addr3(conn)
    extra = "AND addr3 = :a3" if has3 else ""
    if is_flat_sido_addr2(addr2):
        addr2_sql = "AND (addr2 = '' OR addr2 IS NULL)"
    else:
        addr2_sql = "AND addr2 = :a2"
    sql = text(
        f"""
        SELECT *
        FROM rent_conversion_rates
        WHERE as_of_month = :as_of
          AND window_years = :w
          AND addr1 = :a1
          {addr2_sql}
          AND asset_type IN :assets
          {extra}
        """
    ).bindparams(bindparam("assets", expanding=True))
    params: dict[str, Any] = {
        "as_of": as_of,
        "w": window_years,
        "a1": addr1,
        "assets": assets,
    }
    if not is_flat_sido_addr2(addr2):
        params["a2"] = addr2
    if has3:
        params["a3"] = addr3
    return [dict(r) for r in conn.execute(sql, params).mappings().all()]


def get_region_rates(
    conn: Connection,
    *,
    as_of: date,
    window_years: int,
    addr1: str,
    addr2: str,
    asset_types: list[str],
    addr3: Optional[str] = None,
) -> dict[str, RentConversionRate]:
    if not _table_exists(conn, "public.rent_conversion_rates"):
        return {}
    assets = [a for a in asset_types if a in ASSET_TYPES]
    if not assets:
        return {}
    want_dong = bool(addr3 and str(addr3).strip())
    sigungu_rows = _fetch_rate_rows(
        conn,
        as_of=as_of,
        window_years=window_years,
        addr1=addr1,
        addr2=addr2,
        assets=assets,
        addr3="",
    )
    sigungu = {d["asset_type"]: _rate_from_row(d, scope="sigungu") for d in sigungu_rows}
    if not want_dong:
        return sigungu
    dong_rows = _fetch_rate_rows(
        conn,
        as_of=as_of,
        window_years=window_years,
        addr1=addr1,
        addr2=addr2,
        assets=assets,
        addr3=str(addr3).strip(),
    )
    dong = {d["asset_type"]: _rate_from_row(d, scope="dong") for d in dong_rows}
    out: dict[str, RentConversionRate] = {}
    for at in assets:
        d = dong.get(at)
        if d and d.gate_passed and d.r_selected:
            out[at] = d
        elif at in sigungu:
            s = sigungu[at]
            out[at] = s.model_copy(update={"fallback": True, "addr3": str(addr3).strip()})
        elif d:
            out[at] = d
    return out


def _f(v) -> Optional[float]:
    return float(v) if v is not None else None


def list_conversion_compare(
    conn: Connection,
    *,
    as_of: date,
    addr1: str,
    asset_types: list[str],
    window_years: list[int] | None = None,
) -> list[RentConversionCompareRow]:
    if not _table_exists(conn, "public.rent_conversion_rates"):
        return []
    assets = [a for a in asset_types if a in ASSET_TYPES]
    if not assets:
        assets = [a for a in ASSET_TYPES if a != "detached"]
    windows = [w for w in (window_years or [3, 5, 7]) if w in (3, 5, 7)]
    if not windows:
        windows = [3, 5, 7]
    addr3_clause = "AND (addr3 = '' OR addr3 IS NULL)" if _has_addr3(conn) else ""
    sql = text(
        f"""
        SELECT *
        FROM rent_conversion_rates
        WHERE as_of_month = :as_of
          AND addr1 = :a1
          AND asset_type IN :assets
          AND window_years IN :windows
          {addr3_clause}
        ORDER BY addr2, asset_type, window_years
        """
    ).bindparams(
        bindparam("assets", expanding=True),
        bindparam("windows", expanding=True),
    )
    rows = conn.execute(
        sql,
        {"as_of": as_of, "a1": addr1, "assets": assets, "windows": windows},
    ).mappings().all()
    out: list[RentConversionCompareRow] = []
    for r in rows:
        d = dict(r)
        out.append(
            RentConversionCompareRow(
                addr1=d.get("addr1") or "",
                addr2=d.get("addr2") or "",
                asset_type=d.get("asset_type") or "",
                window_years=int(d["window_years"]),
                n_buildings=int(d.get("n_buildings") or 0),
                n_jeonse=int(d.get("n_jeonse") or 0),
                n_mixed=int(d.get("n_mixed") or 0),
                r_mean_simple=_f(d.get("r_mean_simple")),
                r_mean_weighted=_f(d.get("r_mean_weighted")),
                r_ols_origin=_f(d.get("r_ols_origin")),
                r_ols_weighted=_f(d.get("r_ols_weighted")),
                r_selected=_f(d.get("r_selected")),
                method_selected=d.get("method_selected") or "mean_simple",
                gate_passed=bool(d.get("gate_passed")),
            )
        )
    return out


def rate_case_sql(active: dict[str, float], *, col: str = "t.asset_type") -> str:
    """CASE WHEN asset_type = 'apartment' THEN r/100 ... END (whitelist only)."""
    parts: list[str] = []
    for at in ASSET_TYPES:
        r = active.get(at)
        if r is None or r <= 0:
            continue
        parts.append(f"WHEN {col} = '{at}' THEN {float(r) / 100.0:.8f}")
    if not parts:
        return "NULL"
    return "CASE " + " ".join(parts) + " END"


def fetch_building_converted(
    conn: Connection,
    *,
    as_of: date,
    window_years: int,
    addr1: str,
    addr2: str,
    addr3: Optional[str],
    asset_types: list[str],
    period_start: date,
    period_end: date,
    rates: dict[str, RentConversionRate],
    building_key: Optional[str] = None,
) -> dict[tuple[str, str], tuple[LeaseMetric, LeaseMetric]]:
    """building_key, asset_type → (전세환산, 월세환산) P50."""
    active = {
        at: r.r_selected
        for at, r in rates.items()
        if r.gate_passed and r.r_selected is not None and r.r_selected > 0
    }
    if not active:
        return {}
    assets = [a for a in asset_types if a in active]
    if not assets:
        return {}

    clauses = [
        "t.is_valid = true",
        "t.contract_date >= :p_start",
        "t.contract_date <= :p_end",
        "t.asset_type IN :assets",
        "t.deposit_per_m2 IS NOT NULL",
    ]
    params: dict[str, Any] = {
        "p_start": period_start,
        "p_end": period_end,
        "assets": assets,
    }
    apply_addr2_scope(clauses, params, addr1=addr1, addr2=addr2, col_prefix="t")
    if addr3:
        clauses.append("t.addr3 = :addr3")
        params["addr3"] = addr3
    if building_key:
        clauses.append("NULLIF(btrim(t.building_key::text), '') = :bk")
        params["bk"] = building_key

    rate_sql = rate_case_sql(active)
    bkey = building_key_sql("t")
    sql = f"""
        WITH tagged AS (
            SELECT
                {bkey} AS building_key,
                t.asset_type,
                t.deposit_per_m2 AS dep,
                COALESCE(t.monthly_per_m2, 0) AS mon,
                {rate_sql} AS r_frac
            FROM rent_transactions t
            WHERE {" AND ".join(clauses)}
        ),
        conv AS (
            SELECT
                building_key,
                asset_type,
                CASE
                    WHEN mon <= 0 THEN dep
                    WHEN dep > 0 THEN dep + 12.0 * mon / r_frac
                    ELSE 12.0 * mon / r_frac
                END AS jeonse_equiv,
                CASE
                    WHEN mon <= 0 AND dep > 0 THEN dep * r_frac / 12.0
                    WHEN mon <= 0 THEN NULL
                    WHEN dep <= 0 THEN mon
                    ELSE mon + dep * r_frac / 12.0
                END AS monthly_equiv
            FROM tagged
            WHERE r_frac IS NOT NULL AND r_frac > 0
        )
        SELECT
            building_key,
            asset_type,
            COUNT(*)::int AS n,
            percentile_cont(0.5) WITHIN GROUP (ORDER BY jeonse_equiv) AS jeonse_median,
            percentile_cont(0.5) WITHIN GROUP (ORDER BY monthly_equiv) AS monthly_median
        FROM conv
        WHERE jeonse_equiv IS NOT NULL OR monthly_equiv IS NOT NULL
        GROUP BY building_key, asset_type
    """
    stmt = text(sql).bindparams(bindparam("assets", expanding=True))
    rows = conn.execute(stmt, params).mappings().all()
    out: dict[tuple[str, str], tuple[LeaseMetric, LeaseMetric]] = {}
    for r in rows:
        key = (str(r["building_key"]).strip(), r["asset_type"])
        n = int(r["n"] or 0)
        j_med = float(r["jeonse_median"]) if r.get("jeonse_median") is not None else None
        m_med = float(r["monthly_median"]) if r.get("monthly_median") is not None else None
        out[key] = (
            LeaseMetric(n=n, median=j_med, mean=None, ci_lower=None, ci_upper=None),
            LeaseMetric(n=n, median=m_med, mean=None, ci_lower=None, ci_upper=None),
        )
    return out
